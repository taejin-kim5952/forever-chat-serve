"""챗봇 화면의 `AI 답변` 스위치 — **studio 전용**.

```
스위치 끔 →  POST /api/ask         검수된 QA 에서만 (지금까지와 같음)
스위치 켬 →  POST /api/studio/ask  문서에서 찾아 AI가 정리 + 참고 자료
```

### 왜 라우터를 따로 두는가

`app/api/ask.py` 는 **운영 경로**다. 거기에 이 엔드포인트를 두면 운영 컨트롤러가
`app/studio/` 를 import 하게 되고, 그 방향이 열리는 순간 "운영에서 LLM을 부르지 않는다"는
전제가 코드 구조에서 사라진다. 파일을 나눠 두면 운영에 반입할 때 이 파일 하나만 봐도 된다.

### 왜 관리자 인증이 없는가

챗봇 화면에는 로그인이 없다. 그래서 `/api/admin/*` 과 달리 인증을 걸지 않고, 대신
**`APP_MODE=studio` 에서만** 열린다 — studio 는 사내 작업 PC라는 것이 이 제품의 전제다
(운영에서는 403). 인터넷에 닿는 서버를 studio 로 띄우지 않는 것이 전제의 다른 쪽이다.

### 질문 이력에 남기지 않는다

검수자가 문서를 시험하며 던지는 질문이라 실사용 통계가 아니다. 이력에 섞으면 '무엇을 자주
묻는가'가 검수자의 시험 질문으로 오염된다 — 채널을 `web`/`auto` 로 나눠 둔 것과 같은 이유다.
"""

import time

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings, is_studio
from app.core.logging import get_logger, log_event
from app.core.runtime_config import load_runtime_config
from app.models.schemas import RelatedDoc, StudioAskRequest, StudioAskResponse
from app.pipeline.retrieve import get_retriever
from app.studio import ask as studio_ask

logger = get_logger("api.studio_ask")

router = APIRouter(prefix="/api/studio", tags=["studio-ask"])


def _require_studio() -> None:
    if not is_studio():
        raise HTTPException(
            status_code=403,
            detail="운영에서는 AI 답변을 만들 수 없습니다. 검수된 답변만 나갑니다.",
        )


@router.post("/ask", response_model=StudioAskResponse)
def ask_with_ai(request: StudioAskRequest) -> StudioAskResponse:
    _require_studio()
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="질문을 입력해 주세요.")

    started = time.perf_counter()
    config = load_runtime_config()

    # **문서만 본다.** QA 인덱스를 섞으면 스위치의 뜻이 흐려진다 — 켜면 AI가 정리한 답,
    # 끄면 검수된 답. 어느 쪽인지 화면을 보는 사람이 늘 알 수 있어야 한다.
    hits = get_retriever().doc_index.search(question, config.doc_top_k)
    related = [h for h in hits if h["similarity"] >= config.related_docs_floor]

    if not related:
        # 임계값은 관리자 화면(탭 ⑧)의 그 값이다. 여기서 따로 정하면 설정을 내려도
        # 이쪽만 그대로여서 "왜 여기서는 안 걸리지"가 된다.
        return _response(
            "unresolved", started,
            message="관련 있는 문서를 찾지 못했습니다. 문서를 먼저 등록해 주세요.",
            similarity=max([h["similarity"] for h in hits], default=None),
        )

    # **후보는 넓게, 카드는 좁게.** AI 에게는 8건까지 주고(`ai_answer_source_count`) 그중
    # 무엇을 쓸지 고르게 한다. 3건만 주면 4번째로 걸린 문서에 답이 있어도 AI 는 본 적이
    # 없게 된다. 화면에 나가는 것은 AI 가 실제로 근거로 쓴 것뿐이다.
    #
    # `category_id` 는 문서 검색에 쓰지 않는다. 운영 경로와 같은 판단이다 — 사용자가 주제를
    # 잘못 골랐을 때 맞는 문서를 통째로 못 찾게 되는 편이 더 나쁘다.
    candidates = related[: get_settings().ai_answer_source_count]
    answer, model, sources = studio_ask.compose(question, candidates)

    log_event(
        logger, "ai answer served",
        grounded=bool(answer), candidates=len(candidates), shown=len(sources),
        similarity=round(candidates[0]["similarity"], 3),
    )
    if not answer:
        # 답을 못 만들었으면 찾은 문서라도 보여 준다. 이때는 AI 의 선택이 없으므로
        # 화면 카드 수(`related_docs_count`)를 따른다.
        sources = candidates[: config.related_docs_count]
    return _response(
        "ai_answer" if answer else "related_docs", started,
        answer=answer, docs=sources, model=model, similarity=candidates[0]["similarity"],
    )


def _response(result_type: str, started: float, *, answer: str | None = None,
              docs: list[dict] | None = None, message: str | None = None,
              model: str = "", similarity: float | None = None) -> StudioAskResponse:
    return StudioAskResponse(
        result_type=result_type,                                       # type: ignore[arg-type]
        answer=answer,
        related_docs=[
            RelatedDoc(
                doc_id=hit["doc_id"],
                chunk_id=hit.get("chunk_id", ""),
                title=hit["title"],
                section=hit["section"],
                excerpt=hit["excerpt"],
                url_or_ref=hit.get("url", ""),
                similarity=hit["similarity"],
            )
            for hit in (docs or [])
        ],
        message=message,
        model=model,
        similarity=similarity,
        response_time_ms=int((time.perf_counter() - started) * 1000),
    )
