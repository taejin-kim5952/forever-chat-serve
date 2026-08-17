"""관리자 탭 ① 질문 이력.

**운영에서 가장 중요한 화면이다.** 답변 생성은 스튜디오로 옮겼지만, 사용자가 실제로
무엇을 물었는지는 운영에서만 알 수 있다. 여기 쌓인 질문 — 특히 `unresolved` — 이
다음에 무엇을 만들어야 하는지를 정한다.
"""

import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.core.auth import require_admin
from app.core.feedback import read_feedback
from app.core.question_log import read_question_logs
from app.models.schemas import QuestionLogPage

router = APIRouter(
    prefix="/api/admin/questions", tags=["admin-questions"], dependencies=[Depends(require_admin)]
)

CSV_COLUMNS = [
    "asked_at", "question", "result_type", "similarity", "category_label",
    "matched_question", "response_time_ms", "ticket_id", "channel",
    "feedback", "feedback_reason",
]


def _down_only_ids() -> set[str]:
    """'👎만' 필터가 고를 log_id. 신고가 없으면 빈 집합 → 결과도 0건이 맞다."""
    return {log_id for log_id, fb in read_feedback().items() if fb.vote == "down"}


def _with_feedback(items: list) -> list[dict]:
    """행에 평가를 붙인다. **대부분의 행은 빈 값이다** — 그게 정상이다.

    비율(만족도 %)로 읽으면 안 된다. 아무것도 안 누른 사람이 대부분이고 만족한 사람은
    특히 안 누른다. 어느 QA에 👎가 몰리는가라는 상대 신호로만 쓴다.
    """
    feedback = read_feedback({i.log_id for i in items})
    out = []
    for item in items:
        row = item.model_dump()
        fb = feedback.get(item.log_id)
        row["feedback"] = fb.vote if fb else ""
        row["feedback_reason"] = fb.reason_label if fb else ""
        out.append(row)
    return out


@router.get("", response_model=QuestionLogPage)
def list_questions(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    result_type: str | None = None,
    category_id: str | None = None,
    keyword: str | None = None,
    since: str | None = None,
    include_test: bool = False,
    feedback: str | None = Query(None, description="'down' 이면 👎 만"),
) -> QuestionLogPage:
    items, total = read_question_logs(
        limit=limit, offset=offset, result_type=result_type, category_id=category_id,
        keyword=keyword, since=since, include_test=include_test,
        log_ids=_down_only_ids() if feedback == "down" else None,
    )
    return QuestionLogPage(
        items=_with_feedback(items), total=total, limit=limit, offset=offset
    )


@router.get("/export")
def export_csv(
    result_type: str | None = None,
    category_id: str | None = None,
    keyword: str | None = None,
    since: str | None = None,
    include_test: bool = False,
    feedback: str | None = None,
) -> StreamingResponse:
    """폐쇄망에서 오프라인 분석에 쓴다. 화면 필터를 그대로 받아 같은 결과를 내려준다."""
    items, _ = read_question_logs(
        limit=100_000, offset=0, result_type=result_type, category_id=category_id,
        keyword=keyword, since=since, include_test=include_test,
        log_ids=_down_only_ids() if feedback == "down" else None,
    )

    buffer = io.StringIO()
    # Excel 이 UTF-8 을 알아보게 BOM 을 넣는다. 없으면 한글이 전부 깨져 보인다.
    buffer.write("﻿")
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for row in _with_feedback(items):
        writer.writerow(row)
    buffer.seek(0)

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="question_log.csv"'},
    )
