"""관리자 진행 현황 — 콘텐츠 파이프라인이 어디서 막혀 있는지.

**운영(serve)에서도 동작한다.** 이미 저장된 파일만 읽고 LLM을 부르지 않는다. 운영에서
검수가 밀려 있는지 확인하는 것이 이 화면의 주 용도이므로 여기서 막히면 안 된다.

읽기 전용 엔드포인트 하나뿐이다. 여섯 칸을 **한 번에** 내려주는 이유는
`app/pipeline/status.py` 독스트링 참고.
"""

from fastapi import APIRouter, Depends

from app.core.auth import require_admin
from app.pipeline.status import PipelineStatus, collect

router = APIRouter(
    prefix="/api/admin/pipeline", tags=["admin-pipeline"], dependencies=[Depends(require_admin)],
)


@router.get("/status", response_model=PipelineStatus)
def get_status() -> PipelineStatus:
    """진행 현황 한 벌. 화면(`#panel_flow`)이 새로 열릴 때마다 부른다.

    캐시하지 않는다 — 검수 한 건을 승인하고 돌아왔을 때 숫자가 그대로면 승인이 안 된 줄 안다.
    파일 몇 개를 읽는 정도라 비용도 크지 않다.
    """
    return collect()
