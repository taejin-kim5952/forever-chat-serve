"""QA 생성 배치 실행 — 백그라운드 스레드 + 진행률 폴링 + 중지.

문서 5건에 변형 질문까지 만들면 LLM 호출이 수백 번이고 **수십 분**이 걸린다. HTTP 요청 안에서
끝낼 수 없으므로 스레드로 돌리고, 화면은 진행률을 폴링한다. 1차 프로젝트 `app/eval/runner.py`
에서 검증된 구조다.

### 중지가 기능인 이유

돌려보면 첫 몇 건에서 프롬프트나 모델 선택이 잘못됐다는 것을 알게 된다. 그때 30분을 기다리게
만들면 검수자는 서버를 죽이고, 그러면 그때까지 만든 것도 같이 사라진다. `stop` 은 지금까지
만든 초안을 **남긴 채** 멈춘다.

### 초안을 파일에 남기는 이유

화면 요구사항은 "생성 결과(미저장) → 검토 후 선택 항목만 추가"다. 그렇다고 메모리에만 두면
30분짜리 배치 결과가 서버 재시작 한 번에 사라진다. 그래서 초안은 `data/generated_qa.json`
에 계속 쓰고, **QA 인덱스(`qa_index.json`)에는 넣지 않는다.** 두 파일을 나눠 두면
"검수 대상"과 "아직 사람 손을 안 탄 것"이 파일 단위로 구분된다.

### 반영은 항상 pending

`apply` 는 초안을 `status="pending"` 으로만 넣는다. 승인은 사람이 검수 화면에서 한다.
생성 단계에서 approved 로 넣을 수 있는 경로를 아예 만들지 않는 것이 5-1 결정의 핵심이다.
"""

import threading
import time
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.core import jobs
from app.core.config import get_settings
from app.core.jsonstore import read_json, write_json_atomic
from app.core.logging import get_logger, log_event
from app.studio.generate import (
    GenerationStats,
    ModelRoles,
    QaDraft,
    generate_from_docs,
    generate_from_questions,
    normalize_question,
)
from app.qa import store as qa_store

logger = get_logger("studio.runner")

JobStatus = Literal["idle", "running", "done", "failed", "stopped"]

_LOCK = threading.RLock()


class JobProgress(BaseModel):
    status: JobStatus = "idle"
    stage: str = ""
    done: int = 0
    total: int = 0
    percent: int = 0
    produced: int = 0
    error: str = ""
    # 화면 표시용 한 줄. 역할별로 모델이 다르면 "질문 A · 답변 B" 로 온다.
    model: str = ""
    question_model: str = ""
    answer_model: str = ""
    # 비어 있으면 이번 배치는 채점하지 않았다는 뜻이다.
    judge_model: str = ""
    started_at: str = ""
    finished_at: str = ""


class DraftFile(BaseModel):
    generated_at: str = ""
    model: str = ""
    drafts: list[QaDraft] = Field(default_factory=list)
    # 이번 배치에서 무엇이 걸러졌는지. 진행 현황의 '흐름 요약'이 읽는다.
    stats: GenerationStats = Field(default_factory=GenerationStats)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


class GenerationJob:
    """동시에 한 건만 돈다.

    두 건이 동시에 돌면 (1) 같은 문서에서 같은 질문이 두 번 나오고 (2) 로컬 GPU 한 장을
    두 배치가 나눠 쓰며 둘 다 느려진다. 실행 중 재요청은 409로 막는다.
    """

    def __init__(self):
        self._progress = JobProgress()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._drafts: list[QaDraft] = []
        self._loaded = False

    # ------------------------------------------------------------- 상태 조회

    def progress(self) -> JobProgress:
        with _LOCK:
            return self._progress.model_copy()

    def is_running(self) -> bool:
        with _LOCK:
            return self._progress.status == "running"

    def is_stopping(self) -> bool:
        """중지를 요청했지만 아직 돌고 있는 상태. 작업 현황판이 [중지] 버튼을 잠근다."""
        return self._stop.is_set() and self.is_running()

    def drafts(self) -> list[QaDraft]:
        """마지막 생성 결과. 서버를 다시 띄웠으면 파일에서 읽어 온다."""
        with _LOCK:
            if not self._loaded:
                self._drafts = _read_drafts().drafts
                self._loaded = True
            return list(self._drafts)

    # ------------------------------------------------------------- 실행/중지

    def start(
        self,
        *,
        source: str,
        doc_ids: list[str],
        questions: list[str],
        category_id: str | None,
        question_model: str | None,
        answer_model: str | None,
        judge_model: str | None = None,
        items_per_chunk: int,
        variant_count: int,
        max_items: int,
    ) -> JobProgress:
        with _LOCK:
            if self._progress.status == "running":
                raise RuntimeError("이미 생성이 진행 중입니다.")
            roles = ModelRoles.resolve(question_model, answer_model, judge_model)
            self._stop.clear()
            self._drafts = []
            self._loaded = True
            self._progress = JobProgress(
                status="running", stage="준비 중…", model=roles.label(),
                question_model=roles.question.model, answer_model=roles.answer.model,
                judge_model=roles.judge.model if roles.judge else "",
                started_at=_now(),
            )

        self._thread = threading.Thread(
            target=self._run,
            kwargs={
                "roles": roles, "source": source, "doc_ids": doc_ids, "questions": questions,
                "category_id": category_id, "items_per_chunk": items_per_chunk,
                "variant_count": variant_count, "max_items": max_items,
            },
            daemon=True,   # 서버를 내릴 때 배치가 종료를 막지 않도록
            name="qa-generation",
        )
        self._thread.start()
        return self.progress()

    def request_stop(self) -> JobProgress:
        self._stop.set()
        with _LOCK:
            if self._progress.status == "running":
                self._progress.stage = "중지 요청됨 — 진행 중인 항목까지 마치고 멈춥니다."
        return self.progress()

    def join(self, timeout: float | None = None) -> bool:
        """배치가 끝날 때까지 기다린다. 스크립트(`scripts/generate_qa.py`)와 테스트가 쓴다."""
        thread = self._thread
        if thread is None:
            return True
        thread.join(timeout)
        return not thread.is_alive()

    # ------------------------------------------------------------- 내부

    def _on_progress(self, done: int, total: int, stage: str) -> None:
        with _LOCK:
            self._progress.done = done
            self._progress.total = total
            self._progress.stage = stage
            self._progress.percent = int(done / max(1, total) * 100)

    def _run(self, *, roles: ModelRoles, source: str, doc_ids: list[str], questions: list[str],
             category_id: str | None, items_per_chunk: int, variant_count: int, max_items: int) -> None:
        try:
            # 이미 있는 질문은 다시 만들지 않는다. 같은 문서를 두 번 돌리는 일이 흔한데,
            # 그때마다 같은 질문이 초안으로 쌓이면 검수자가 중복을 손으로 지워야 한다.
            existing = {normalize_question(i.question) for i in qa_store.load_qa()}

            common = {
                "roles": roles,
                "variant_count": variant_count,
                "max_items": max_items,
                "existing_questions": existing,
                "progress": self._on_progress,
                "should_stop": self._stop.is_set,
            }
            if source == "docs":
                outcome = generate_from_docs(doc_ids, items_per_chunk=items_per_chunk, **common)
            else:
                outcome = generate_from_questions(questions, category_id=category_id, **common)
            drafts = outcome.drafts

            with _LOCK:
                self._drafts = drafts
                self._progress.produced = len(drafts)
                self._progress.status = "stopped" if self._stop.is_set() else "done"
                self._progress.stage = "중지됨" if self._stop.is_set() else "완료"
                self._progress.percent = 100 if not self._stop.is_set() else self._progress.percent
                self._progress.finished_at = _now()
            # 중지된 경우에도 남긴다 — 지금까지 만든 것을 버리면 중지 버튼을 아무도 안 쓴다.
            _write_drafts(DraftFile(
                generated_at=_now(), model=roles.label(), drafts=drafts, stats=outcome.stats,
            ))
            log_event(logger, "generation finished", status=self._progress.status, drafts=len(drafts))
            stats = outcome.stats
            jobs.record(
                "generate",
                status="stopped" if self._stop.is_set() else "done",
                started_at=self._progress.started_at,
                summary=(f"{len(drafts)}건 생성"
                         + (f" · 근거없음 {stats.dropped_ungrounded}건" if stats.dropped_ungrounded else "")),
                counts={"drafts": len(drafts)},
            )
        except Exception as exc:  # noqa: BLE001 — 배치 실패가 서버를 죽이면 안 된다
            with _LOCK:
                self._progress.status = "failed"
                self._progress.error = str(exc)
                self._progress.stage = "실패"
                self._progress.finished_at = _now()
            log_event(logger, "generation failed", error=str(exc))
            jobs.record("generate", status="failed",
                        started_at=self._progress.started_at, error=str(exc))


_job = GenerationJob()


def get_job() -> GenerationJob:
    return _job


def reset_job() -> None:
    """테스트에서 잡 상태를 초기화한다. 모듈 전역이라 테스트끼리 상태가 새어 나간다."""
    global _job
    _job = GenerationJob()


# ─────────────────────────────────────────────────────────── 초안 파일


def _path() -> Path:
    return Path(get_settings().generated_qa_file)


def _read_drafts() -> DraftFile:
    data = read_json(_path())
    if not isinstance(data, dict):
        return DraftFile()
    try:
        return DraftFile(**data)
    except ValueError as exc:
        log_event(logger, "draft file unreadable", path=str(_path()), error=str(exc))
        return DraftFile()


def read_draft_file() -> DraftFile:
    """초안 파일 전체(초안 + 통계). 진행 현황 집계가 읽는다.

    `get_job().drafts()` 는 초안 목록만 주므로 생성 시각·통계를 못 본다. serve 모드에서도
    파일은 그대로 읽히므로(생성만 못 할 뿐) 이 함수는 모드를 가리지 않는다.
    """
    return _read_drafts()


def _write_drafts(payload: DraftFile) -> None:
    with _LOCK:
        write_json_atomic(_path(), payload.model_dump_json(indent=2))


# ─────────────────────────────────────────────────────────── 반영


class ApplyResult(BaseModel):
    saved: int = 0
    skipped: int = 0
    # 채점 기준에 못 미쳐 빠진 건수. `skipped`(중복·이미 반영)와 나눠야 검수자가 무엇을
    # 손봐야 하는지 안다 — 중복은 정상이고, 낮은 점수는 프롬프트나 문서를 봐야 한다는 신호다.
    low_score: int = 0
    min_score: int = 0
    qa_ids: list[str] = Field(default_factory=list)


def apply_drafts(draft_ids: Optional[list[str]] = None, min_score: Optional[int] = None) -> ApplyResult:
    """선택한 초안을 QA 인덱스에 **pending** 으로 넣는다.

    벡터 색인은 건드리지 않는다. `pending` 은 애초에 색인 대상이 아니므로(5-1) 넣을 것이 없고,
    여기서 색인을 부르면 "생성 직후에 사용자에게 나갈 수 있다"는 오해를 코드가 만들어 준다.

    채점이 있는 초안은 `min_score` 미만을 여기서 뺀다. 채점을 안 한 배치(판정 모델을 안 정한
    경우)는 전부 0점이므로, **점수가 하나라도 매겨진 배치에서만** 이 필터가 동작한다.
    그러지 않으면 판정 모델을 안 쓰는 사람은 아무것도 반영하지 못한다.
    """
    job = get_job()
    wanted = set(draft_ids) if draft_ids else None
    drafts = [d for d in job.drafts() if wanted is None or d.draft_id in wanted]

    threshold = get_settings().qa_apply_min_score if min_score is None else min_score
    judged = any(d.score for d in job.drafts())

    existing = {normalize_question(i.question) for i in qa_store.load_qa()}
    result = ApplyResult(min_score=threshold if judged else 0)

    for draft in drafts:
        if draft.applied_qa_id or normalize_question(draft.question) in existing:
            result.skipped += 1
            continue
        if judged and draft.score < threshold:
            result.low_score += 1
            continue
        item = qa_store.upsert_item(qa_store.QaItem(
            qa_id=qa_store.new_qa_id(),
            question=draft.question,
            answer=draft.answer,
            variants=draft.variants,
            category_id=draft.category_id,
            source_doc_ids=draft.source_doc_ids,
            status="pending",
            created_by="ai",
            model_used=draft.model_used,
            note=f"자동 생성 · 출처: {draft.source_section}" if draft.source_section else "자동 생성",
            # 채점을 여기서 버리면 검수 화면이 무엇부터 볼지 정할 근거를 잃는다.
            score=draft.score,
            judge_model=draft.judge_model,
            judge_reason=draft.judge_reason,
        ))
        draft.applied_qa_id = item.qa_id
        existing.add(normalize_question(draft.question))
        result.saved += 1
        result.qa_ids.append(item.qa_id)

    # 반영 표시를 파일에도 남긴다. 안 그러면 새로고침 뒤 같은 초안을 또 넣게 된다.
    # 하나도 못 넣은 경우에도 쓴다 — "전부 4점 미만이라 0건"이 진행 현황에 보여야
    # 검수자가 채점 기준을 의심할 수 있다. 안 남기면 아무 일도 없었던 것처럼 보인다.
    current = _read_drafts()
    applied = {d.draft_id: d.applied_qa_id for d in drafts if d.applied_qa_id}
    for draft in current.drafts:
        if draft.draft_id in applied:
            draft.applied_qa_id = applied[draft.draft_id]
    current.stats.applied = result.saved
    current.stats.skipped = result.skipped
    current.stats.low_score = result.low_score
    _write_drafts(current)

    log_event(
        logger, "drafts applied",
        saved=result.saved, skipped=result.skipped, low_score=result.low_score, min_score=threshold,
    )
    # 반영이 끝나면 다음은 검수다. 그 안내를 진행 현황이 하도록 이력에 남긴다.
    jobs.record(
        "apply",
        summary=(f"{result.saved}건 반영"
                 + (f" · 중복 {result.skipped}건" if result.skipped else "")
                 + (f" · {result.min_score}점 미만 {result.low_score}건" if result.low_score else "")),
        counts={"saved": result.saved},
    )
    return result
