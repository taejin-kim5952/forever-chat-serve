"""QA 검색 품질 평가 — 임계값 0.90이 맞는지 숫자로 확인한다(관리자 탭 ⑦).

지금 `qa_match_threshold=0.90` 은 **근거가 없는 값**이다. 이 모듈이 그 근거를 만든다.

### 골든셋을 따로 만들지 않는다 ★

사람이 평가 문항을 손으로 쓰는 대신, **이미 검수해 둔 QA의 변형 질문을 그대로 문항으로 쓴다.**
변형 질문은 "이 질문이 오면 이 답이 나와야 한다"를 사람이 직접 확인한 것이라, 정답 라벨이
이미 붙어 있는 셈이다. 별도 골든셋 파일을 두면 QA를 고칠 때마다 따로 관리해야 한다.

### 자기 자신에 걸리는 문제(leave-one-out)

변형 질문은 **벡터 인덱스에 이미 들어 있다.** 그대로 검색하면 유사도 1.000으로 자기 자신이
1등이 되어 적중률이 100%로 나온다 — 아무것도 측정하지 못한다.

그래서 검색 결과에서 **질문과 글자가 같은 항목을 걸러낸다.** 남은 순위는 "이 표현이 인덱스에
없었다면 어떻게 됐을까"에 해당한다. 벡터를 실제로 빼고 다시 넣는 방법도 있지만, 문항마다
색인을 고치는 것은 느리고 도중에 실패하면 인덱스가 깨진다.

### 무엇을 재는가

| 지표 | 뜻 |
| --- | --- |
| 적중률(Top-1) | 1등이 기대한 QA인 비율 |
| 적중률(Top-3) | 상위 3등 안에 기대한 QA가 있는 비율 |
| 오매칭률 | 1등이 **다른** QA인데 임계값을 넘어 답변으로 나가는 비율 ← 가장 위험한 값 |
| 미검색 | 기대한 QA를 못 찾았거나 임계값에 못 미친 비율 |

**오매칭이 미검색보다 나쁘다.** 못 찾으면 사용자가 다시 묻지만, 엉뚱한 답이 나가면 그것이
맞는 줄 안다. 임계값을 내릴 때는 이 값을 먼저 본다.
"""

import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.core import jobs
from app.core.config import get_settings
from app.core.jsonstore import read_json, write_json_atomic
from app.core.logging import get_logger, log_event
from app.core.runtime_config import load_runtime_config
from app.qa.index import QaIndex, collapse_by_qa
from app.qa.store import load_qa, serving_items
from app.studio.generate import normalize_question

logger = get_logger("studio.evaluate")

ProgressFn = Callable[[int, int, str], None]
StopFn = Callable[[], bool]

# 판정 4종 — 화면의 색과 1:1이다(적중 초록 / 오매칭 danger / 미검색 회색).
Verdict = Literal["hit", "mismatch", "miss"]


class EvalItem(BaseModel):
    question: str
    expected_qa_id: str
    expected_question: str
    matched_qa_id: Optional[str] = None
    matched_question: Optional[str] = None
    similarity: float = 0.0
    rank: int = 0          # 기대한 QA가 몇 등이었나. 0이면 상위 k 안에 없었다
    verdict: Verdict = "miss"


class EvalReport(BaseModel):
    run_at: str = ""
    model: str = ""
    threshold: float = 0.0
    total: int = 0
    top1: float = 0.0
    top3: float = 0.0
    mismatch_rate: float = 0.0
    miss_rate: float = 0.0
    # 임계값을 바꿨을 때 어떻게 달라지는지. 화면이 표로 보여준다.
    threshold_sweep: list[dict] = Field(default_factory=list)
    items: list[EvalItem] = Field(default_factory=list)


# ─────────────────────────────────────────────────────── 마지막 리포트 보관
#
# 리포트를 잡(메모리)에만 두면 서버를 재시작할 때마다 사라진다. 그러면 진행 현황 화면의
# '품질' 칸이 늘 "측정 이력 없음"이 되고, 임계값을 정할 때 근거로 삼은 숫자를 다음 사람이
# 다시 재야 한다. 파일 하나로 남긴다 — `data/` 의 다른 파생물과 같은 성격이라 지워도 된다.


def _report_path() -> Path:
    return Path(get_settings().eval_report_file)


def save_report(report: EvalReport) -> None:
    write_json_atomic(_report_path(), report.model_dump_json(indent=2))


def load_last_report() -> EvalReport | None:
    """마지막으로 **완료된** 평가. 없거나 읽을 수 없으면 None."""
    data = read_json(_report_path())
    if not isinstance(data, dict):
        return None
    try:
        return EvalReport(**data)
    except ValueError as exc:
        log_event(logger, "eval report unreadable", path=str(_report_path()), error=str(exc))
        return None


def _build_questions(limit: int) -> list[tuple[str, str, str]]:
    """`(질문, 기대 qa_id, 기대 대표질문)`.

    변형 질문이 있는 항목만 쓴다. 대표 질문 자체를 문항으로 쓰면 인덱스에 있는 같은 문장을
    지운 뒤 남는 것이 변형 질문뿐이라, 결국 같은 것을 다르게 재는 셈이 된다.
    """
    rows: list[tuple[str, str, str]] = []
    for item in serving_items(load_qa()):
        for variant in item.variants:
            variant = variant.strip()
            if variant:
                rows.append((variant, item.qa_id, item.question))
    # 앞쪽 QA에만 몰리지 않도록 항목을 번갈아 뽑는다 — 그냥 자르면 마지막 QA들이 통째로 빠진다.
    rows.sort(key=lambda r: (r[0]))
    return rows[:limit] if limit else rows


def _evaluate_one(index: QaIndex, question: str, expected_qa_id: str, top_k: int) -> tuple[list[dict], int]:
    """`(자기 자신을 뺀 검색 결과, 기대한 QA의 순위)`. 순위는 1부터, 없으면 0.

    **접기 전에 빼야 한다.** 검색 결과를 qa_id 단위로 접으면 그 QA는 한 줄만 남는데, 그 한
    줄이 바로 "인덱스에 든 그 문항 자신"이라 빼는 순간 QA가 통째로 사라진다. 그러면 어떤
    데이터로 재도 적중률이 0%로 나온다 — 2026-08-17 에 실제로 그 상태였다.
    """
    vector = index.embedder.embed(question, task="similarity")
    # 자기 자신을 빼고도 순위를 매길 수 있게 넉넉히 가져온다(같은 QA의 변형이 자리를 차지한다).
    hits = index.search_by_vector(vector, top_k * 3, collapse=False)

    target = normalize_question(question)
    # 글자가 같은 항목 = 인덱스에 들어 있는 그 문항 자신. 빼야 실제 검색력을 잰다.
    hits = [h for h in hits if normalize_question(h.get("matched_question", "")) != target]
    hits = collapse_by_qa(hits)[:top_k]

    rank = 0
    for position, hit in enumerate(hits, start=1):
        if hit["qa_id"] == expected_qa_id:
            rank = position
            break
    return hits, rank


def _sweep(items: list[EvalItem], candidates: tuple[float, ...]) -> list[dict]:
    """임계값을 바꾸면 적중·오매칭이 어떻게 움직이는지.

    이 표가 탭 ⑧에서 값을 정할 때의 근거다. 0.90이 최선이 아닐 수도 있다.
    """
    rows = []
    total = len(items) or 1
    for threshold in candidates:
        answered = [i for i in items if i.similarity >= threshold]
        hit = sum(1 for i in answered if i.matched_qa_id == i.expected_qa_id)
        wrong = len(answered) - hit
        rows.append({
            "threshold": threshold,
            # 답변으로 나가는 비율
            "answer_rate": round(len(answered) / total * 100, 1),
            "hit_rate": round(hit / total * 100, 1),
            "mismatch_rate": round(wrong / total * 100, 1),
        })
    return rows


def run_evaluation(
    limit: int = 100,
    top_k: int = 10,
    progress: ProgressFn | None = None,
    should_stop: StopFn | None = None,
) -> EvalReport:
    config = load_runtime_config()
    index = QaIndex()
    questions = _build_questions(limit)

    if not questions:
        raise RuntimeError(
            "평가할 문항이 없습니다. 승인된 QA에 변형 질문이 있어야 합니다(검수 화면에서 승인하세요)."
        )

    items: list[EvalItem] = []
    for position, (question, qa_id, expected_question) in enumerate(questions):
        if should_stop and should_stop():
            break
        if progress:
            progress(position, len(questions), f"검색 정확도 측정 중… ({position}/{len(questions)})")

        hits, rank = _evaluate_one(index, question, qa_id, top_k)
        top = hits[0] if hits else None
        similarity = top["similarity"] if top else 0.0

        if top and top["qa_id"] == qa_id and similarity >= config.qa_match_threshold:
            verdict: Verdict = "hit"
        elif top and top["qa_id"] != qa_id and similarity >= config.qa_match_threshold:
            # 임계값을 넘겨 답변으로 나가는데 다른 QA다 — 사용자에게 틀린 답이 간다.
            verdict = "mismatch"
        else:
            verdict = "miss"

        items.append(EvalItem(
            question=question,
            expected_qa_id=qa_id,
            expected_question=expected_question,
            matched_qa_id=top["qa_id"] if top else None,
            matched_question=top.get("matched_question") if top else None,
            similarity=round(similarity, 4),
            rank=rank,
            verdict=verdict,
        ))

    total = len(items) or 1
    report = EvalReport(
        run_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        model=index.embedder.model,
        threshold=config.qa_match_threshold,
        total=len(items),
        top1=round(sum(1 for i in items if i.rank == 1) / total * 100, 1),
        top3=round(sum(1 for i in items if 1 <= i.rank <= 3) / total * 100, 1),
        mismatch_rate=round(sum(1 for i in items if i.verdict == "mismatch") / total * 100, 1),
        miss_rate=round(sum(1 for i in items if i.verdict == "miss") / total * 100, 1),
        threshold_sweep=_sweep(items, (0.75, 0.80, 0.85, 0.90, 0.95)),
        items=items,
    )
    log_event(
        logger, "evaluation finished",
        total=report.total, top1=report.top1, mismatch=report.mismatch_rate, model=report.model,
    )
    return report


# ─────────────────────────────────────────────────────────── 실행 상태

_LOCK = threading.RLock()


class EvalJob:
    """탭 ⑦의 실행 상태. 생성(탭 ⑥)과 같은 구조지만 훨씬 짧게 끝난다(LLM을 안 쓴다)."""

    def __init__(self):
        self.status: str = "idle"
        self.stage: str = ""
        self.percent: int = 0
        self.error: str = ""
        self.started_at: str = ""
        self.report: EvalReport | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def snapshot(self) -> dict:
        with _LOCK:
            return {
                "status": self.status, "stage": self.stage, "percent": self.percent,
                "error": self.error, "total": self.report.total if self.report else 0,
                # 작업 현황판이 경과 시간과 [중지] 버튼 상태를 그린다.
                "started_at": self.started_at,
                "stopping": self._stop.is_set() and self.status == "running",
            }

    def start(self, limit: int, top_k: int) -> dict:
        with _LOCK:
            if self.status == "running":
                raise RuntimeError("평가가 이미 진행 중입니다.")
            self._stop.clear()
            self.status, self.stage, self.percent, self.error = "running", "준비 중…", 0, ""
            self.started_at = jobs.now()

        self._thread = threading.Thread(
            target=self._run, args=(limit, top_k), daemon=True, name="qa-evaluation")
        self._thread.start()
        return self.snapshot()

    def request_stop(self) -> dict:
        self._stop.set()
        return self.snapshot()

    def join(self, timeout: float | None = None) -> bool:
        if self._thread is None:
            return True
        self._thread.join(timeout)
        return not self._thread.is_alive()

    def _on_progress(self, done: int, total: int, stage: str) -> None:
        with _LOCK:
            self.stage = stage
            self.percent = int(done / max(1, total) * 100)

    def _run(self, limit: int, top_k: int) -> None:
        try:
            report = run_evaluation(
                limit=limit, top_k=top_k,
                progress=self._on_progress, should_stop=self._stop.is_set,
            )
            stopped = self._stop.is_set()
            with _LOCK:
                self.report = report
                self.status = "stopped" if stopped else "done"
                self.stage = "중지됨" if stopped else "완료"
                self.percent = 100 if not stopped else self.percent
            # 중지된 평가는 **저장하지 않는다.** 문항을 일부만 돌린 오매칭률이 파일에 남으면
            # 진행 현황이 그것을 최신 품질로 보여준다 — 틀린 숫자가 근거로 쓰인다.
            if not stopped:
                save_report(report)
            jobs.record(
                "evaluate",
                status="stopped" if stopped else "done",
                started_at=self.started_at,
                summary=(f"중지됨 ({report.total}문항)" if stopped
                         else f"{report.total}문항 · 적중 {report.top1}% · 오매칭 {report.mismatch_rate}%"),
                counts={"total": report.total},
            )
        except Exception as exc:  # noqa: BLE001 — 평가 실패가 서버를 죽이면 안 된다
            with _LOCK:
                self.status, self.error, self.stage = "failed", str(exc), "실패"
            log_event(logger, "evaluation failed", error=str(exc))
            jobs.record("evaluate", status="failed", started_at=self.started_at, error=str(exc))


_job = EvalJob()


def get_job() -> EvalJob:
    return _job


def reset_job() -> None:
    global _job
    _job = EvalJob()
