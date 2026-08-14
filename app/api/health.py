"""상태 확인. 인증 없이 열어둔다 — 컨테이너 헬스체크와 로드밸런서가 호출한다."""

import ollama
from fastapi import APIRouter

from app.core.config import get_settings
from app.qa import store as qa_store

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/health/ready")
def ready() -> dict:
    """답할 준비가 됐는지. 프로세스가 떠 있는 것과 답할 수 있는 것은 다르다 —
    임베딩 모델이 없거나 QA 인덱스가 비어 있으면 화면은 뜨는데 모든 질문이 unresolved 가 된다."""
    settings = get_settings()
    checks: dict = {"mode": settings.app_mode}

    try:
        names = [m.get("model") or m.get("name") for m in ollama.Client(host=settings.ollama_host).list()["models"]]
        checks["ollama"] = "ok"
        checks["embed_model"] = "ok" if settings.ollama_embed_model in names else "missing"
    except Exception as exc:   # noqa: BLE001 - 원인이 무엇이든 준비 안 됨으로 보고한다
        checks["ollama"] = f"error: {exc}"
        checks["embed_model"] = "unknown"

    serving = len(qa_store.serving_items())
    checks["qa_serving"] = serving

    checks["status"] = "ok" if checks.get("embed_model") == "ok" and serving > 0 else "degraded"
    return checks
