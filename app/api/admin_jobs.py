"""작업 현황판 — 진행 현황 화면의 '실행 중인 작업'과 '최근 작업'(퍼블 요청서 06).

화면이 탭마다 따로 진행률을 폴링하던 것을 **한 곳으로 모은다.** QA 생성은 수십 분짜리
배치인데, 지금까지는 그 탭에 머물러야만 진행 상황이 보였다. 새로고침하면 그마저 사라졌다.

```
GET  /api/admin/jobs             실행 중 1건 + 최근 5건
POST /api/admin/jobs/{key}/stop  실행 중인 배치 중지
```

### 실행 중은 잡에서 직접 읽는다

`generate` · `evaluate` 는 각자 상태를 들고 있다(`app/studio/`). 여기서 복사해 두면 두 값이
어긋나므로, 요청이 올 때마다 잡에게 물어 합친다. 이력(`app/core/jobs.py`)은 끝난 것만 적는다.

### 한 번에 하나만 돈다

두 배치가 동시에 돌면 같은 CPU/GPU를 나눠 쓰며 둘 다 느려진다. 각 잡이 실행 중 재요청을
409로 막고 있으므로, 여기서는 **먼저 찾은 하나**만 내려보낸다.

### serve 모드에도 살아 있다

운영에는 생성·평가가 없어 `running` 이 항상 비지만, 문서 색인 이력은 운영에서도 남는다.
모드에 따라 경로를 없애면 화면이 404를 만나 "주소가 틀렸나"를 먼저 의심하게 된다 —
studio 전용 라우터를 항상 등록하는 것과 같은 이유다(`app/main.py`).
"""

from fastapi import APIRouter, Depends, HTTPException

from app.core import jobs
from app.core.auth import require_admin
from app.core.config import is_studio
from app.core.logging import get_logger, log_event
from app.models.schemas import JobsResponse, RunningJob

logger = get_logger("api.admin_jobs")

router = APIRouter(prefix="/api/admin/jobs", tags=["admin-jobs"], dependencies=[Depends(require_admin)])

# 중지할 수 있는 작업. 색인·업로드는 요청 안에서 끝나므로 멈출 지점이 없다.
_STOPPABLE = ("generate", "evaluate")


def _running() -> RunningJob | None:
    """실행 중인 배치 하나. studio 가 아니면 언제나 None."""
    if not is_studio():
        return None

    from app.studio import evaluate, runner

    progress = runner.get_job().progress()
    if progress.status == "running":
        return RunningJob(
            key="generate",
            title=jobs.JOB_TITLES["generate"],
            stage=progress.stage,
            percent=progress.percent,
            done=progress.done,
            total=progress.total,
            model=progress.model,
            started_at=progress.started_at,
            # 중지 요청이 들어왔는지. 화면이 [중지] 버튼을 잠그고 문구를 바꾼다.
            stopping=runner.get_job().is_stopping(),
            tab=jobs.JOB_TABS["generate"],
        )

    snapshot = evaluate.get_job().snapshot()
    if snapshot.get("status") == "running":
        return RunningJob(
            key="evaluate",
            title=jobs.JOB_TITLES["evaluate"],
            stage=snapshot.get("stage", ""),
            percent=snapshot.get("percent", 0),
            done=0,
            total=0,
            model="",
            started_at=snapshot.get("started_at", ""),
            stopping=bool(snapshot.get("stopping")),
            tab=jobs.JOB_TABS["evaluate"],
        )
    return None


@router.get("", response_model=JobsResponse)
def list_jobs() -> JobsResponse:
    return JobsResponse(running=_running(), recent=jobs.recent())


@router.post("/{key}/stop", response_model=JobsResponse)
def stop_job(key: str) -> JobsResponse:
    """지금까지 만든 것은 남기고 멈춘다.

    이미 끝난 작업에 중지를 눌러도 오류로 만들지 않는다 — 화면이 폴링 사이에 한 박자 늦게
    누르는 일이 흔하고, 그때 빨간 토스트가 뜨면 무엇이 잘못된 줄 안다.
    """
    if key not in _STOPPABLE:
        raise HTTPException(status_code=400, detail=f"중지할 수 없는 작업입니다: {key}")
    if not is_studio():
        raise HTTPException(status_code=403, detail="운영에서는 실행 중인 배치가 없습니다.")

    from app.studio import evaluate, runner

    if key == "generate":
        runner.get_job().request_stop()
    else:
        evaluate.get_job().request_stop()

    log_event(logger, "job stop requested", key=key)
    return JobsResponse(running=_running(), recent=jobs.recent())
