"""관리자 탭 ④ QA 인덱스 — 검수 화면이 쓰는 API.

저장은 항상 **파일 먼저, 벡터 다음** 순서다. 벡터를 먼저 쓰면 파일 저장이 실패했을 때
검색은 새 답변을, 화면은 옛 답변을 보여주는 상태가 된다. 파일이 원본이므로
파일이 성공한 뒤에만 색인을 맞춘다. 색인이 실패해도 원본은 남아 재색인으로 복구된다.
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import require_admin
from app.core.logging import get_logger, log_event
from app.models.schemas import (
    QaBulkRequest,
    QaBulkResponse,
    QaPage,
    QaSaveRequest,
    ReindexResponse,
)
from app.pipeline.retrieve import get_retriever
from app.qa import store as qa_store
from app.qa.index import QaIndex

logger = get_logger("api.admin_qa")

router = APIRouter(prefix="/api/admin/qa", tags=["admin-qa"], dependencies=[Depends(require_admin)])


def _to_row(item: qa_store.QaItem) -> dict:
    data = item.model_dump()
    # 목록은 답변 전문을 실어 나를 필요가 없다 — 80건이면 응답이 수백 KB가 된다.
    data["answer_preview"] = " ".join(item.answer.split())[:120]
    data["variant_count"] = len(item.variants)
    data.pop("answer", None)
    return data


@router.get("", response_model=QaPage)
def list_qa(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status: str | None = None,
    category_id: str | None = None,
    keyword: str | None = None,
    sort: str = Query("hit_count", pattern="^(hit_count|variant_count|updated_at)$"),
) -> QaPage:
    items = qa_store.load_qa()

    if status:
        items = [i for i in items if i.status == status]
    if category_id:
        items = [i for i in items if i.category_id == category_id]
    if keyword:
        needle = keyword.lower()
        # 대표 질문·변형 질문·답변 본문을 모두 본다. 검수자는 답변 문구로도 찾는다.
        items = [
            i for i in items
            if needle in i.question.lower()
            or needle in i.answer.lower()
            or any(needle in v.lower() for v in i.variants)
        ]

    key = {
        "hit_count": lambda i: i.hit_count,
        "variant_count": lambda i: len(i.variants),
        "updated_at": lambda i: i.updated_at,
    }[sort]
    items.sort(key=key, reverse=True)

    return QaPage(
        items=[_to_row(i) for i in items[offset: offset + limit]],
        total=len(items),
        limit=limit,
        offset=offset,
        summary=qa_store.summary(),
    )


@router.get("/{qa_id}")
def get_qa(qa_id: str) -> dict:
    item = qa_store.get_item(qa_id)
    if not item:
        raise HTTPException(status_code=404, detail="QA 항목을 찾을 수 없습니다.")
    return item.model_dump()


@router.post("")
def save_qa(request: QaSaveRequest) -> dict:
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="대표 질문을 입력해 주세요.")
    if request.status == "approved" and not request.answer.strip():
        # 승인은 "이대로 사용자에게 나가도 된다"는 뜻이다. 빈 답변이 승인되면
        # 검색은 걸리는데 말풍선이 비어 나온다.
        raise HTTPException(status_code=400, detail="답변이 비어 있으면 승인할 수 없습니다.")

    item = qa_store.QaItem(
        qa_id=request.qa_id or qa_store.new_qa_id(),
        question=request.question.strip(),
        answer=request.answer,
        # 빈 줄과 대표 질문과 같은 문구는 걸러낸다 — 벡터를 낭비하고 중복 적중을 만든다.
        variants=[v.strip() for v in request.variants if v.strip() and v.strip() != request.question.strip()],
        category_id=request.category_id,
        source_doc_ids=request.source_doc_ids,
        status=request.status,
        note=request.note,
        created_by=request.created_by,
    )
    saved = qa_store.upsert_item(item)

    vectors = QaIndex().upsert_item(saved)
    log_event(logger, "qa saved", qa_id=saved.qa_id, status=saved.status, vectors=vectors)
    return {"item": saved.model_dump(), "vectors": vectors}


@router.post("/bulk", response_model=QaBulkResponse)
def bulk(request: QaBulkRequest) -> QaBulkResponse:
    qa_ids = set(request.qa_ids)
    if not qa_ids:
        return QaBulkResponse(changed=0)

    if request.action == "delete":
        changed = qa_store.delete_items(qa_ids)
        index = QaIndex()
        for qa_id in qa_ids:
            index.remove_item(qa_id)
        return QaBulkResponse(changed=changed, reindexed=len(qa_ids))

    if request.action == "set_category":
        return QaBulkResponse(changed=qa_store.set_category(qa_ids, request.category_id))

    status = {"approve": "approved", "hold": "hold", "pending": "pending", "disable": "disabled"}[request.action]
    changed = qa_store.set_status(qa_ids, status)

    # 상태가 바뀌면 검색 대상이 바뀐다 — 승인은 색인에 넣고, 나머지는 뺀다.
    index = QaIndex()
    reindexed = 0
    for qa_id in qa_ids:
        item = qa_store.get_item(qa_id)
        if item:
            reindexed += 1 if index.upsert_item(item) else 0
    return QaBulkResponse(changed=changed, reindexed=reindexed)


@router.post("/reindex", response_model=ReindexResponse)
def reindex(include_docs: bool = False) -> ReindexResponse:
    """전체 재색인. 임베딩 모델을 바꿨거나 QA 파일을 직접 넣었을 때 쓴다."""
    result = QaIndex().rebuild()
    docs: dict = {}
    if include_docs:
        docs = get_retriever().doc_index.rebuild()
    # 인덱스 핸들을 새로 잡게 한다 — 컬렉션을 지우고 다시 만들었으므로 옛 핸들은 죽어 있다.
    from app.pipeline.retrieve import reset_retriever
    reset_retriever()
    return ReindexResponse(items=result["items"], vectors=result["vectors"], docs=docs)
