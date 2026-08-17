"""관리자 탭 ⑦ 품질 평가 — **studio 전용**.

LLM을 쓰지 않으므로 기술적으로는 운영에서도 돌릴 수 있다. 그런데도 막는 이유는 **비용**이다.
문항 100건이면 임베딩을 100번 계산한다. GPU 없는 운영 서버에서 그동안 들어온 사용자 질문은
같은 CPU를 나눠 쓰며 느려진다. 측정은 스튜디오에서 하고, 정해진 임계값만 운영에 넣는다.
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import require_admin
from app.core.config import is_studio
from app.core.logging import get_logger, log_event
from app.studio import evaluate

logger = get_logger("api.studio_eval")

router = APIRouter(prefix="/api/studio/eval", tags=["studio-eval"], dependencies=[Depends(require_admin)])


def _require_studio() -> None:
    if not is_studio():
        raise HTTPException(
            status_code=403,
            detail="운영에서는 품질 평가를 실행할 수 없습니다. 평가는 스튜디오에서 진행합니다.",
        )


@router.post("")
def start(
    limit: int = Query(100, ge=1, le=2000),
    top_k: int = Query(10, ge=1, le=50),
) -> dict:
    _require_studio()
    try:
        return evaluate.get_job().start(limit=limit, top_k=top_k)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/progress")
def progress() -> dict:
    _require_studio()
    return evaluate.get_job().snapshot()


@router.post("/stop")
def stop() -> dict:
    _require_studio()
    return evaluate.get_job().request_stop()


@router.get("/result")
def result() -> dict:
    """마지막 평가 결과. 아직 없으면 빈 리포트가 온다(화면이 빈 상태를 그린다)."""
    _require_studio()
    report = evaluate.get_job().report
    if report is None:
        return evaluate.EvalReport().model_dump()
    log_event(logger, "evaluation result read", total=report.total)
    return report.model_dump()
