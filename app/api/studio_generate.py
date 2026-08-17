"""관리자 탭 ⑥ QA 생성 — **studio 전용**.

운영(serve)에는 GPU가 없어 이 기능이 동작할 수 없다. 그래서 전 구간이 403이다. 화면도 탭을
감추지만(`<body data-mode>`), API를 직접 부르는 경로가 있으므로 서버에서도 세운다 —
문서 편집(`app/api/admin_docs.py`)과 같은 방식이다.

생성은 수십 분이 걸린다. 요청 하나로 끝내지 않고 **시작 → 폴링 → (중지) → 검토 → 반영**
다섯 단계로 나눈 이유가 그것이다.

```
POST   /api/studio/generate           시작 (이미 실행 중이면 409)
GET    /api/studio/generate/progress  진행률 — 화면이 폴링
POST   /api/studio/generate/stop      중지 (지금까지 만든 초안은 남는다)
GET    /api/studio/generate/result    초안 목록 (아직 QA 인덱스에 없음)
POST   /api/studio/generate/apply     선택한 초안을 pending 으로 반영
```

`apply` 는 `pending` 으로만 넣는다. 승인은 검수 화면(탭 ④)에서 사람이 한다.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import require_admin
from app.core.categories import find_category, load_categories
from app.core.config import get_settings, is_studio
from app.core.logging import get_logger, log_event
from app.models.schemas import StudioApplyRequest, StudioGenerateRequest, StudioVariantRequest
from app.studio import runner
from app.studio.generate import QaDraft, make_variants
from app.studio.llm import StudioLlm, installed_models
from app.studio.runner import ApplyResult, JobProgress

logger = get_logger("api.studio_generate")

router = APIRouter(
    prefix="/api/studio/generate", tags=["studio-generate"], dependencies=[Depends(require_admin)]
)


def _require_studio() -> None:
    if not is_studio():
        raise HTTPException(
            status_code=403,
            detail="운영에서는 QA를 생성할 수 없습니다. 생성은 스튜디오에서 진행하고 결과 파일을 배포합니다.",
        )


def _resolve_questions(request: StudioGenerateRequest) -> list[str]:
    """`category` 대상이면 그 카테고리의 추천 질문을 꺼내 온다.

    추천 질문은 챗봇 인트로에 실제로 노출되는 문구다. 그 질문에 답이 없으면 사용자가 칩을
    누르자마자 `unresolved` 를 보게 되므로, QA를 만들 대상으로 가장 우선순위가 높다.
    """
    if request.source != "category":
        return request.questions

    if not request.category_id:
        raise HTTPException(status_code=400, detail="카테고리를 선택해 주세요.")
    category = find_category(load_categories(), request.category_id)
    if not category:
        raise HTTPException(status_code=404, detail="카테고리를 찾을 수 없습니다.")
    if not category.questions:
        raise HTTPException(status_code=400, detail=f"'{category.name}' 에 등록된 추천 질문이 없습니다.")
    return category.questions


@router.post("", response_model=JobProgress)
def start_generation(request: StudioGenerateRequest) -> JobProgress:
    _require_studio()
    questions = _resolve_questions(request)
    if request.source != "docs" and not questions:
        raise HTTPException(status_code=400, detail="답변을 만들 질문이 없습니다.")

    try:
        progress = runner.get_job().start(
            source=request.source,
            doc_ids=request.doc_ids,
            questions=questions,
            category_id=request.category_id,
            question_model=request.question_model or request.model,
            answer_model=request.answer_model or request.model,
            judge_model=request.judge_model,
            items_per_chunk=request.items_per_chunk,
            variant_count=request.variant_count,
            max_items=request.max_items,
        )
    except RuntimeError as exc:
        # 두 배치가 같은 문서를 동시에 돌면 같은 질문이 두 번 나오고, 로컬 GPU를 나눠 써 둘 다 느려진다.
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    log_event(logger, "generation started", source=request.source, model=progress.model)
    return progress


@router.get("/models", response_model=dict)
def available_models() -> dict:
    """화면의 모델 선택을 채운다 — 설치돼 있는 것만 고를 수 있게 한다.

    Ollama 가 꺼져 있으면 목록이 비어 온다. 그때도 화면은 떠야 하므로 오류로 만들지 않는다.
    """
    _require_studio()
    settings = get_settings()
    return {
        "models": installed_models(),
        # 아무것도 안 고르면 서버가 쓸 값. 화면이 선택 상태를 이 값에 맞춘다.
        "question_default": settings.ollama_question_model or settings.ollama_llm_model,
        "answer_default": settings.ollama_answer_model or settings.ollama_llm_model,
        # 채점은 기본이 '안 함'이다 — 빈 값이 정상이고, 화면도 그렇게 보여준다.
        "judge_default": settings.ollama_judge_model,
        "apply_min_score": settings.qa_apply_min_score,
    }


@router.post("/variants", response_model=list[str])
def generate_variants(request: StudioVariantRequest) -> list[str]:
    """대표 질문 하나로 변형 질문만 만든다 — 검수 화면의 `[자동 생성]` 버튼.

    배치(위의 시작/폴링)와 달리 한 번의 LLM 호출로 끝나므로 요청 안에서 처리한다.
    검수자가 답변은 손으로 쓰고 변형 질문만 채우고 싶어 하는 경우가 흔하다.
    """
    _require_studio()
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="대표 질문을 입력해 주세요.")

    variants = make_variants(StudioLlm(model=request.model), question, request.count)
    log_event(logger, "variants generated", question=question[:40], produced=len(variants))
    return variants


@router.get("/progress", response_model=JobProgress)
def generation_progress() -> JobProgress:
    _require_studio()
    return runner.get_job().progress()


@router.post("/stop", response_model=JobProgress)
def stop_generation() -> JobProgress:
    _require_studio()
    return runner.get_job().request_stop()


@router.get("/result", response_model=list[QaDraft])
def generation_result() -> list[QaDraft]:
    """검수 전 초안 목록. 아직 `qa_index.json` 에 들어가지 않은 상태다."""
    _require_studio()
    return runner.get_job().drafts()


@router.post("/apply", response_model=ApplyResult)
def apply_generation(request: StudioApplyRequest) -> ApplyResult:
    _require_studio()
    return runner.apply_drafts(request.draft_ids or None, min_score=request.min_score)
