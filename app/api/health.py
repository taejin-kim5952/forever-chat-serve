"""상태 확인. 인증 없이 열어둔다 — 컨테이너 헬스체크와 로드밸런서가 호출한다."""

from pathlib import Path

from fastapi import APIRouter

from app.core.config import get_settings, is_studio
from app.ingestion.embedder import MODEL_FILE, TOKENIZER_FILE
from app.qa import store as qa_store

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/health/ready")
def ready() -> dict:
    """답할 준비가 됐는지.

    프로세스가 떠 있는 것과 답할 수 있는 것은 다르다 — 임베딩 모델 파일이 없거나 QA 인덱스가
    비어 있으면 화면은 멀쩡히 뜨는데 **모든 질문이 unresolved** 가 된다. 그 상태를 여기서
    구분해 준다.

    Ollama 는 확인하지 않는다. 질문·답변 생성에만 쓰이고 **운영에는 없는 것이 정상**이다.
    """
    settings = get_settings()
    checks: dict = {"mode": settings.app_mode}

    model_dir = Path(settings.embed_onnx_dir)
    missing = [f for f in (MODEL_FILE, TOKENIZER_FILE) if not (model_dir / f).exists()]
    checks["embed_model"] = "ok" if not missing else f"missing: {', '.join(missing)}"
    checks["embed_model_dir"] = str(model_dir)

    serving = len(qa_store.serving_items())
    checks["qa_serving"] = serving

    # 스튜디오는 QA를 만드는 곳이라 승인된 QA가 0건이어도 정상이다. 운영은 아니다.
    ready_to_answer = checks["embed_model"] == "ok" and (serving > 0 or is_studio())
    checks["status"] = "ok" if ready_to_answer else "degraded"
    return checks
