"""답변에 대한 사용자 신고(👍/👎) 적재·조회.

**사용자는 판정자가 아니라 신고자다.** 여기 쌓인 값은 QA의 상태를 절대 바꾸지 않는다 —
관리자 화면(질문 이력의 `평가` 열, 검수의 `사용자 신고`·`👎 많은순`)에만 쓰인다.
사용자 클릭이 승인 상태를 움직이면 "검수한 답변만 나간다"는 이 제품의 전제가 무너진다.

`question_log.jsonl` 과 **파일을 나눈** 이유:

- 질문 로그는 **추가 기록만 하는** 파일이다(동시 요청에도 줄이 안 섞인다). 피드백은 사용자가
  다시 눌러 취소·변경할 수 있어 성격이 반대다. 같은 파일에 넣으려면 매번 전체를 다시 써야 하고,
  그 사이 들어온 질문이 통째로 사라질 수 있다.
- 여기도 추가 기록만 하되 **같은 `log_id` 는 마지막 줄이 이긴다.** 취소·변경이 새 줄 하나로
  끝난다. `question_embeddings.jsonl` 과 같은 방식이고, 두 파일은 `log_id` 로 연결된다.

읽는 쪽이 유의할 점: 대부분의 질문에는 신고가 **없다.** 비율(만족도 82%)로 읽으면 거짓말이
된다 — 아무것도 안 누른 사람이 대부분이고 만족한 사람은 특히 안 누른다.
**어느 QA에 👎가 몰리는가**라는 상대 신호로만 쓴다.
"""

import io
import json
import threading
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel

from app.core.config import get_settings
from app.core.logging import get_logger, log_event

logger = get_logger("core.feedback")

_LOCK = threading.Lock()

# 화면의 이유 칩과 같은 값(chat.html 의 data-reason).
# 이유마다 담당자가 하는 일이 다르다 — 그래서 👎 하나로 뭉뚱그리지 않는다.
REASON_LABELS: dict[str, str] = {
    "mismatch": "질문과 다른 답이에요",   # → 변형 질문을 늘리거나 임계값 조정
    "wrong": "내용이 틀려요",             # → 문서를 다시 보고 답변 수정
    "thin": "설명이 부족해요",            # → 답변 보강
}

Vote = Literal["up", "down", ""]


class FeedbackEntry(BaseModel):
    log_id: str
    # "" 는 취소다. 다시 누르면 지워진다 — 잘못 누르는 일이 잦아 잠그지 않는다.
    vote: Vote = ""
    reason: Optional[str] = None
    at: str = ""

    @property
    def reason_label(self) -> str:
        return REASON_LABELS.get(self.reason or "", "")


def _path() -> Path:
    return Path(get_settings().question_feedback_file)


def append_feedback(entry: FeedbackEntry) -> None:
    """1건 기록. 실패해도 예외를 올리지 않는다 — 피드백 때문에 화면이 멈추면 안 된다."""
    try:
        path = _path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK, io.open(path, "a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")
    except OSError as exc:
        log_event(logger, "feedback append failed", log_id=entry.log_id, error=str(exc))


def read_feedback(log_ids: set[str] | None = None) -> dict[str, FeedbackEntry]:
    """`{log_id: 마지막 상태}`. 취소(`vote=""` 이고 이유도 없음)는 결과에서 뺀다."""
    path = _path()
    if not path.exists():
        return {}

    out: dict[str, FeedbackEntry] = {}
    with io.open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = FeedbackEntry(**json.loads(line))
            except ValueError:
                # 포맷이 바뀌기 전 줄이 섞여 있어도 나머지는 살린다.
                continue
            if log_ids is not None and entry.log_id not in log_ids:
                continue
            if not entry.vote:
                out.pop(entry.log_id, None)   # 취소
                continue
            # 이유만 따로 온 줄은 앞의 투표를 유지한 채 이유만 채운다.
            prev = out.get(entry.log_id)
            if prev and entry.reason is None:
                entry.reason = prev.reason
            out[entry.log_id] = entry
    return out


class QaReport(BaseModel):
    """검수 화면의 `사용자 신고` 한 줄 — 실제로 들어온 질문 원문."""

    asked_at: str = ""
    question: str = ""
    similarity: Optional[float] = None
    reason: str = ""
    reason_label: str = ""


def reports_by_qa() -> dict[str, list[QaReport]]:
    """`{qa_id: 👎 목록}` (최근 것 먼저).

    피드백 파일에는 `log_id` 만 있고 어느 QA가 걸렸는지는 질문 이력에 있다. 그래서 여기서
    두 파일을 잇는다 — **질문 원문이 보이는 것이 이 기능의 핵심**이다. 담당자는 숫자가
    아니라 "이 표현이 안 걸리는구나"를 보고 변형 질문을 추가한다.

    👍는 담지 않는다. 검수 화면에서 할 일이 생기는 것은 👎뿐이다.
    """
    # 순환 참조를 피하려고 함수 안에서 부른다 — question_log 는 피드백을 몰라야 한다.
    from app.core.question_log import read_all_question_logs

    votes = read_feedback()
    if not votes:
        return {}

    out: dict[str, list[QaReport]] = {}
    for entry in read_all_question_logs():
        fb = votes.get(entry.log_id)
        if not fb or fb.vote != "down" or not entry.matched_qa_id:
            continue
        out.setdefault(entry.matched_qa_id, []).append(
            QaReport(
                asked_at=entry.asked_at,
                question=entry.question,
                similarity=entry.similarity,
                reason=fb.reason or "",
                reason_label=fb.reason_label,
            )
        )
    for reports in out.values():
        reports.reverse()   # 최근 것 먼저
    return out
