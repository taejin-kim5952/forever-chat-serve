"""관리자 탭 ③ 카테고리 가져오기 — JSON 한 벌로 한꺼번에 등록한다.

한 건씩 만드는 길(`PUT /api/admin/categories`)은 `admin_settings.py` 에 그대로 있다.
여기는 **파일·붙여넣기로 들어오는 길**만 다룬다. 판단은 전부 `app/core/category_import.py`
에 있고 이 파일은 오가는 모양과 오류 코드만 맡는다.

미리보기와 반영을 나눈 이유: 카테고리는 챗봇 첫 화면에 그대로 나간다. 무엇이 새로 생기고
무엇이 덮이는지 — `replace` 라면 무엇이 사라지는지 — 사람이 먼저 보고 누르게 한다.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.core import category_import
from app.core.auth import require_admin
from app.core.logging import get_logger

logger = get_logger("api.admin_categories")

router = APIRouter(prefix="/api/admin", tags=["admin-categories"], dependencies=[Depends(require_admin)])


@router.post("/categories/import/preview", response_model=category_import.PreviewResponse)
def preview_categories(request: category_import.ImportRequest) -> category_import.PreviewResponse:
    try:
        return category_import.preview(request)
    except ValueError as exc:
        # 형식 오류는 사람이 고칠 수 있는 것이다. 메시지를 그대로 화면에 보낸다 —
        # '400 Bad Request' 만 보여주면 파일의 어디를 고쳐야 하는지 알 수 없다.
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/categories/import", response_model=category_import.ImportResponse)
def import_categories(request: category_import.ImportRequest) -> category_import.ImportResponse:
    try:
        return category_import.apply(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
