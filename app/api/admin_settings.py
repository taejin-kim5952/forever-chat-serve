"""관리자 탭 ⑧ 설정 + 카테고리(탭 ③) + 모드 정보."""

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import require_admin
from app.core.categories import CategoryStore, QUICK_LIMIT, load_categories, save_categories, sorted_store
from app.core.config import get_settings
from app.core.logging import get_logger, log_event
from app.core.profile import Profile, load_profile, save_profile
from app.core.runtime_config import RuntimeConfig, load_runtime_config, reset_runtime_config, save_runtime_config
from app.ingestion.vector_store import embed_model_name
from app.models.schemas import AdminSettings, ModeResponse
from app.qa import store as qa_store
from app.qa.index import QaIndex

logger = get_logger("api.admin_settings")

router = APIRouter(prefix="/api/admin", tags=["admin-settings"], dependencies=[Depends(require_admin)])


@router.get("/mode", response_model=ModeResponse)
def mode() -> ModeResponse:
    """화면이 <body data-mode> 를 정하고 탭을 감추는 데 쓴다."""
    settings = get_settings()
    studio = settings.app_mode == "studio"
    return ModeResponse(
        mode=settings.app_mode,
        embed_model=embed_model_name(),
        llm_model=settings.ollama_llm_model if studio else None,
        qa_serving=len(qa_store.serving_items()),
        qa_vectors=QaIndex().count(),
        # 역할별 모델은 비어 있을 수 있다(그때는 OLLAMA_LLM_MODEL 을 쓴다). 화면이 "무엇이
        # 실제로 쓰이는지"를 보여줘야 하므로 여기서 그 대체까지 마쳐서 내려보낸다.
        question_model=(settings.ollama_question_model or settings.ollama_llm_model) if studio else None,
        answer_model=(settings.ollama_answer_model or settings.ollama_llm_model) if studio else None,
        # 채점 모델만은 대체하지 않는다 — 비어 있는 것이 '채점 안 함'이라는 뜻이다.
        judge_model=(settings.ollama_judge_model or None) if studio else None,
        num_ctx=settings.ollama_num_ctx if studio else 0,
        num_predict=settings.ollama_num_predict if studio else 0,
        # 문서 길이 기준은 임베딩 쪽 값이라 serve 에서도 내려보낸다.
        embed_warn_chars=settings.embed_warn_chars,
    )


@router.get("/profile", response_model=Profile)
def get_profile() -> Profile:
    """설정 → 납품처. 파일이 없으면 기본값이 온다(화면은 그것을 그대로 보여준다)."""
    return load_profile()


@router.put("/profile", response_model=Profile)
def put_profile(payload: Profile) -> Profile:
    """조직 이름이 비면 로고 자리가 빈 사각형이 된다 — 그건 저장 실패보다 알아채기 어렵다."""
    if not payload.organization.strip() or not payload.service_name.strip():
        raise HTTPException(status_code=400, detail="조직 이름과 서비스 이름은 비울 수 없습니다.")
    save_profile(payload)
    return load_profile()


@router.get("/settings", response_model=AdminSettings)
def get_admin_settings() -> AdminSettings:
    return AdminSettings(**load_runtime_config().model_dump())


@router.put("/settings", response_model=AdminSettings)
def put_admin_settings(payload: AdminSettings) -> AdminSettings:
    try:
        config = RuntimeConfig(**payload.model_dump())
    except ValueError as exc:
        # 화면도 막지만 API로 직접 넣는 경로가 있으므로 서버에서도 세운다.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    save_runtime_config(config)
    log_event(logger, "settings saved", **config.model_dump())
    return AdminSettings(**config.model_dump())


@router.post("/settings/reset", response_model=AdminSettings)
def reset_admin_settings() -> AdminSettings:
    return AdminSettings(**reset_runtime_config().model_dump())


# ─────────────────────────────────────────────────────────── 카테고리


@router.get("/categories", response_model=CategoryStore)
def get_categories() -> CategoryStore:
    """관리자는 미사용 항목까지 본다 — 그래야 다시 켤 수 있다."""
    return sorted_store(load_categories(), enabled_only=False)


@router.put("/categories", response_model=CategoryStore)
def put_categories(store: CategoryStore) -> CategoryStore:
    ids = [c.category_id for g in store.groups for c in g.categories]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        # 중복 id 가 있으면 챗봇이 어느 주제를 고른 것인지 알 수 없게 된다.
        raise HTTPException(status_code=400, detail=f"카테고리 ID가 중복됩니다: {', '.join(sorted(duplicates))}")

    unknown = [cid for cid in store.quick_category_ids if cid not in ids]
    if unknown:
        raise HTTPException(status_code=400, detail=f"없는 카테고리가 자주 찾는 주제에 있습니다: {', '.join(unknown)}")
    if len(store.quick_category_ids) > QUICK_LIMIT:
        raise HTTPException(status_code=400, detail=f"자주 찾는 주제는 최대 {QUICK_LIMIT}개입니다.")

    # group_id 를 하위 카테고리에 채워 넣는다 — 화면은 트리 구조로만 보내므로 비어 올 수 있다.
    for group in store.groups:
        for category in group.categories:
            category.group_id = group.group_id

    save_categories(store)
    log_event(logger, "categories saved", groups=len(store.groups), categories=len(ids))
    return sorted_store(store, enabled_only=False)
