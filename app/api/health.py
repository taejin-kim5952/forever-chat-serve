"""상태 확인. 인증 없이 열어둔다 — 컨테이너 헬스체크와 로드밸런서가 호출한다."""

from pathlib import Path

from fastapi import APIRouter

from app.core import projects as projects_mod
from app.core.config import get_settings, is_studio, reset_project, use_project
from app.ingestion.embedder import MODEL_FILE, TOKENIZER_FILE
from app.qa import store as qa_store

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _serving_everywhere() -> int:
    """답을 내보낼 수 있는 QA 가 **설치 전체에** 몇 건인가.

    프로젝트마다 세어 더한다. 그냥 `serving_items()` 를 부르면 **기본 팩(`data/`)만** 센다 —
    자료를 전부 `packs/` 에 둔 설치에서는 0 이 나오고, 21ms 에 제대로 답하는 서버가
    `degraded` 로 보고된다. Dockerfile 의 HEALTHCHECK 가 이 값을 보므로 컨테이너가
    **unhealthy** 로 표시된다(2026-10-07 에 실제로 그랬다).

    '전체가 몇 건인가' 로 세는 이유: 이 엔드포인트는 **이 설치가 답할 수 있나**를 답한다.
    프로젝트 하나가 비어 있는 것은 정상이고(막 만든 프로젝트), 전부 비어 있는 것이 사고다.
    """
    found = projects_mod.list_projects(enabled_only=True)
    if not found:
        return len(qa_store.serving_items())

    total = 0
    for project in found:
        token = use_project(project.project_id)
        try:
            total += len(qa_store.serving_items())
        except Exception:  # noqa: BLE001 - 팩 하나가 깨져도 상태는 돌려줘야 한다
            continue
        finally:
            reset_project(token)
    return total


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

    serving = _serving_everywhere()
    checks["qa_serving"] = serving

    # 스튜디오는 QA를 만드는 곳이라 승인된 QA가 0건이어도 정상이다. 운영은 아니다.
    ready_to_answer = checks["embed_model"] == "ok" and (serving > 0 or is_studio())
    checks["status"] = "ok" if ready_to_answer else "degraded"
    return checks
