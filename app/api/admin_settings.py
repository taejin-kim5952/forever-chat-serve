"""관리자 탭 ⑧ 설정 + 카테고리(탭 ③) + 모드 정보."""

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import require_admin
from app.core.categories import CategoryStore, QUICK_LIMIT, load_categories, save_categories, sorted_store
from app.core.config import get_settings
from app.core.logging import get_logger, log_event
from app.core.runtime_config import RuntimeConfig, load_runtime_config, reset_runtime_config, save_runtime_config
from app.models.schemas import AdminSettings, ModeResponse
from app.qa import store as qa_store
from app.qa.index import QaIndex

logger = get_logger("api.admin_settings")

router = APIRouter(prefix="/api/admin", tags=["admin-settings"], dependencies=[Depends(require_admin)])


@router.get("/mode", response_model=ModeResponse)
def mode() -> ModeResponse:
    """화면이 <body data-mode> 를 정하고 탭을 감추는 데 쓴다."""
    settings = get_settings()
    return ModeResponse(
        mode=settings.app_mode,
        embed_model=settings.ollama_embed_model,
        llm_model=settings.ollama_llm_model if settings.app_mode == "studio" else None,
        qa_serving=len(qa_store.serving_items()),
        qa_vectors=QaIndex().count(),
    )


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
