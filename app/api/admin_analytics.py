"""관리자 탭 ② 질문 분석.

**운영(serve)에서도 동작한다.** LLM을 쓰지 않고 이미 저장된 질문 임베딩만 다시 읽기 때문이다.
"무엇을 다음 QA로 만들지"는 실사용 질문에서만 알 수 있고, 실사용 질문은 운영에만 쌓인다.

분석은 몇 초~수십 초 걸린다. 시작과 진행률을 나눠 둔 이유이며, 결과는
`data/analytics.json` 에 저장돼 다시 열었을 때 그대로 보인다.
"""

import threading

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import require_admin
from app.core.logging import get_logger, log_event
from app.models.schemas import AnalyticsOverrideRequest
from app.pipeline import analytics

logger = get_logger("api.admin_analytics")

router = APIRouter(prefix="/api/admin/analytics", tags=["admin-analytics"], dependencies=[Depends(require_admin)])


@router.get("")
def get_analytics() -> dict:
    """마지막 분석 결과. 한 번도 안 돌렸으면 빈 결과가 온다(화면이 빈 상태를 그린다)."""
    return analytics.load_analytics()


@router.get("/progress")
def progress() -> dict:
    return analytics.get_progress()


# 동시에 두 개가 시작하는 좁은 틈을 막는다. 같은 파일에 결과를 쓰기 때문에 두 번 돌면
# 나중 것이 앞의 것을 덮어써 사람이 지정한 상태가 어긋날 수 있다.
_START_LOCK = threading.Lock()


@router.post("/run")
def run(
    period_days: int = Query(30, ge=1, le=365),
    include_test: bool = False,
) -> dict:
    if not _START_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="분석이 이미 진행 중입니다.")
    try:
        # 백그라운드로 돌리지 않는다 — 수천 건이어도 수십 초다. 스레드를 하나 더 두면
        # 진행 중 재요청·중지·결과 회수를 전부 관리해야 하는데 얻는 것이 적다.
        result = analytics.run_analysis(period_days=period_days, include_test=include_test)
    finally:
        _START_LOCK.release()

    log_event(logger, "analytics run", clusters=len(result.get("clusters", [])))
    return result


@router.post("/override")
def override(request: AnalyticsOverrideRequest) -> dict:
    if request.kind == "status" and request.value not in analytics.CLUSTER_STATUSES:
        raise HTTPException(status_code=400, detail=f"알 수 없는 상태입니다: {request.value}")
    return analytics.set_override(request.kind, request.cluster_ids, request.value)
