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
from app.core.question_log import read_question_logs
from app.models.schemas import QuestionLogPage

router = APIRouter(
    prefix="/api/admin/questions", tags=["admin-questions"], dependencies=[Depends(require_admin)]
)

CSV_COLUMNS = [
    "asked_at", "question", "result_type", "similarity", "category_label",
    "matched_question", "response_time_ms", "ticket_id", "channel",
]


@router.get("", response_model=QuestionLogPage)
def list_questions(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    result_type: str | None = None,
    category_id: str | None = None,
    keyword: str | None = None,
    since: str | None = None,
    include_test: bool = False,
) -> QuestionLogPage:
    items, total = read_question_logs(
        limit=limit, offset=offset, result_type=result_type, category_id=category_id,
        keyword=keyword, since=since, include_test=include_test,
    )
    return QuestionLogPage(
        items=[i.model_dump() for i in items], total=total, limit=limit, offset=offset
    )


@router.get("/export")
def export_csv(
    result_type: str | None = None,
    category_id: str | None = None,
    keyword: str | None = None,
    since: str | None = None,
    include_test: bool = False,
) -> StreamingResponse:
    """폐쇄망에서 오프라인 분석에 쓴다. 화면 필터를 그대로 받아 같은 결과를 내려준다."""
    items, _ = read_question_logs(
        limit=100_000, offset=0, result_type=result_type, category_id=category_id,
        keyword=keyword, since=since, include_test=include_test,
    )

    buffer = io.StringIO()
    # Excel 이 UTF-8 을 알아보게 BOM 을 넣는다. 없으면 한글이 전부 깨져 보인다.
    buffer.write("﻿")
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for item in items:
        writer.writerow(item.model_dump())
    buffer.seek(0)

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="question_log.csv"'},
    )
