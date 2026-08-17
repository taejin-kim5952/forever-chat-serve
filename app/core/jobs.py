"""작업 이력 — 진행 현황 화면의 '최근 작업'과 '다음 단계'.

QA 하나가 서비스에 나가려면 **문서 등록 → 색인 → QA 생성 → 반영 → 검수 → 품질 측정**을
차례로 지나는데, 지금까지는 각 단계가 자기 탭 안에서만 돌고 서로를 몰랐다. 관리자가
"방금 그거 끝났나", "이제 뭘 해야 하나"를 스스로 기억해야 했다. 이 모듈이 그 기억을 맡는다.

### 왜 서버가 '다음 단계'를 정하는가 ★

화면이 작업 종류를 보고 다음 탭을 추측하면, 순서를 바꿀 때마다 화면과 서버가 서로 다른 것을
안내한다. `next` 는 여기서 정하고 화면은 받은 것을 그대로 그린다 — `result_type` 을 서버가
정하는 것과 같은 원칙이다(app/pipeline/retrieve.py).

### 실행 중(running)은 여기서 안 다룬다

`generate` 와 `evaluate` 는 각자 백그라운드 잡이 상태를 들고 있다(`app/studio/`). 그것을
복사해 두면 두 곳이 어긋난다. 이 파일은 **끝난 일만** 적는다. 현재 상태는
`app/api/admin_jobs.py` 가 잡에서 직접 읽어 합친다.

### 색인·업로드는 끝난 기록만 남는다

둘 다 요청 안에서 동기로 끝나므로 '몇 %'를 물어볼 대상이 없다. 대신 끝난 뒤 이력에 남아
"문서를 넣었으니 이제 QA를 생성하라"로 이어진다. 수십 분짜리(생성·평가)만 실행 중으로 뜬다.
"""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.jsonstore import read_json, write_json_atomic
from app.core.logging import get_logger, log_event

logger = get_logger("core.jobs")

JobKey = Literal["index", "upload", "generate", "apply", "evaluate"]
JobStatus = Literal["done", "stopped", "failed"]

# 작업 이름과 그 작업을 하는 화면. 화면에도 같은 표가 있지만 **서버가 보낸 값이 우선**이라
# (`r.title || JOB_TITLES[r.key]`), 새 작업을 추가할 때 화면을 고치지 않아도 된다.
JOB_TITLES: dict[str, str] = {
    "index": "문서 색인",
    "upload": "문서 업로드",
    "generate": "QA 생성",
    "apply": "초안 반영",
    "evaluate": "품질 평가",
}
JOB_TABS: dict[str, str] = {
    "index": "docs",
    "upload": "docs",
    "generate": "generate",
    "apply": "review",
    "evaluate": "eval",
}

# 이력은 화면에 5건만 뜨지만 조금 더 남긴다 — 어제 무엇을 돌렸는지 확인하는 데 쓴다.
_KEEP = 20
# 폴더 업로드는 화면이 몇 건씩 나눠 보낸다(app/api/admin_docs.py). 요청마다 이력을 남기면
# 40개짜리 폴더 하나가 10줄을 차지한다. 바로 이어지는 같은 작업은 한 줄로 합친다.
_MERGE_WINDOW_SECONDS = 180


class JobRecord(BaseModel):
    key: str
    status: JobStatus = "done"
    started_at: str = ""
    finished_at: str = ""
    # 사람이 읽는 한 줄 요약. "24건 · 312청크" 처럼 그 작업의 결과를 그대로 적는다.
    summary: str = ""
    error: str = ""
    # 합쳐진 요청 수. 업로드처럼 나눠 보내는 작업에서만 1보다 커진다.
    batches: int = 1
    counts: dict = Field(default_factory=dict)


class JobHistory(BaseModel):
    records: list[JobRecord] = Field(default_factory=list)


def _path() -> Path:
    return Path(get_settings().job_history_file)


def _load() -> JobHistory:
    data = read_json(_path())
    if not isinstance(data, dict):
        return JobHistory()
    try:
        return JobHistory(**data)
    except ValueError as exc:
        # 이력이 깨졌다고 작업을 막지 않는다. 부가 정보일 뿐이다.
        log_event(logger, "job history unreadable", path=str(_path()), error=str(exc))
        return JobHistory()


def _save(history: JobHistory) -> None:
    history.records = history.records[:_KEEP]
    write_json_atomic(_path(), history.model_dump_json(indent=2))


def now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _parse(value: str) -> Optional[datetime]:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
    except (TypeError, ValueError):
        return None


def elapsed_text(started_at: str, finished_at: str) -> str:
    start, end = _parse(started_at), _parse(finished_at)
    if not start or not end:
        return ""
    seconds = max(0, int((end - start).total_seconds()))
    if seconds < 60:
        return f"{seconds}초"
    if seconds < 3600:
        return f"{seconds // 60}분"
    return f"{seconds // 3600}시간 {seconds % 3600 // 60}분"


def record(
    key: str,
    *,
    status: JobStatus = "done",
    started_at: str = "",
    summary: str = "",
    error: str = "",
    counts: Optional[dict] = None,
    merge: bool = False,
    summary_from_counts: Optional[Callable[[dict], str]] = None,
) -> JobRecord:
    """끝난 작업 한 건을 남긴다.

    `merge=True` 면 같은 작업이 방금 끝났을 때 그 줄에 합친다(업로드 묶음). 이때 요약 문구는
    합쳐진 숫자로 다시 만들어야 하므로 `summary_from_counts` 를 받는다 — 마지막 묶음의 문구만
    남으면 "4건 등록"처럼 폴더 전체가 아니라 그 요청 하나의 결과가 이력에 남는다.
    """
    finished = now()
    entry = JobRecord(
        key=key, status=status, started_at=started_at or finished, finished_at=finished,
        summary=summary, error=error, counts=counts or {},
    )

    # 이력은 부가 정보다. 여기서 예외가 나가면 **부르는 쪽이 실패한다** — 실제로 요약 문구를
    # 만들다 틀린 필드를 읽어 30분짜리 생성 배치가 통째로 '실패'로 뒤집힌 적이 있다.
    try:
        history = _load()
        previous = history.records[0] if history.records else None
        if merge and previous and previous.key == key and _within_merge_window(previous.finished_at, finished):
            entry = _merged(previous, entry)
            history.records[0] = entry
        else:
            history.records.insert(0, entry)
        if summary_from_counts:
            entry.summary = summary_from_counts(entry.counts)
        _save(history)
        log_event(logger, "job recorded", key=key, status=status, summary=entry.summary)
    except Exception as exc:  # noqa: BLE001 — 기록 실패가 작업 실패로 보이면 안 된다
        log_event(logger, "job record failed", key=key, error=str(exc))
    return entry


def _within_merge_window(previous_finished: str, finished: str) -> bool:
    before, after = _parse(previous_finished), _parse(finished)
    if not before or not after:
        return False
    return (after - before).total_seconds() <= _MERGE_WINDOW_SECONDS


def _merged(previous: JobRecord, entry: JobRecord) -> JobRecord:
    counts = dict(previous.counts)
    for name, value in entry.counts.items():
        counts[name] = counts.get(name, 0) + value
    return JobRecord(
        key=entry.key,
        # 한 묶음이라도 실패했으면 합쳐진 줄도 실패다 — 성공으로 덮으면 못 들어간 파일이 묻힌다.
        status="failed" if "failed" in (previous.status, entry.status) else entry.status,
        started_at=previous.started_at,
        finished_at=entry.finished_at,
        summary=entry.summary,
        error=entry.error or previous.error,
        batches=previous.batches + 1,
        counts=counts,
    )


def next_step(entry: JobRecord) -> Optional[dict]:
    """이 작업 다음에 할 일. 없으면 None(화면이 버튼을 감춘다).

    실패는 그 작업 화면으로 돌려보낸다 — 다음 단계로 가라고 안내하면 안 된다.
    중지는 안내하지 않는다. 왜 멈췄는지는 사람이 알고 있다.
    """
    if entry.status == "failed":
        return {"label": f"{JOB_TITLES.get(entry.key, '작업')} 화면으로", "tab": JOB_TABS.get(entry.key, "flow")}
    if entry.status == "stopped":
        return None

    if entry.key in ("upload", "index"):
        # 문서가 하나도 안 들어갔으면 생성할 것이 없다.
        if entry.counts.get("docs", 1) <= 0:
            return None
        return {"label": "QA 생성하기", "tab": "generate"}
    if entry.key == "generate":
        if entry.counts.get("drafts", 1) <= 0:
            return None
        return {"label": "초안 검토하기", "tab": "generate"}
    if entry.key == "apply":
        if entry.counts.get("saved", 1) <= 0:
            return None
        return {"label": "검수하기", "tab": "review"}
    if entry.key == "evaluate":
        return {"label": "임계값 조정하기", "tab": "settings"}
    return None


def recent(limit: int = 5) -> list[dict]:
    """화면이 그대로 그리는 모양으로 최근 작업을 낸다."""
    rows = []
    for entry in _load().records[:limit]:
        rows.append({
            "key": entry.key,
            "title": JOB_TITLES.get(entry.key, entry.key),
            "status": entry.status,
            "finished_at": entry.finished_at,
            "summary": entry.summary or entry.error,
            "elapsed": elapsed_text(entry.started_at, entry.finished_at),
            "tab": JOB_TABS.get(entry.key, "flow"),
            "next": next_step(entry),
        })
    return rows
