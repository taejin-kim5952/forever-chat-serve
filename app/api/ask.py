"""챗봇이 쓰는 공개 API. 인증이 없는 유일한 영역이다."""

from fastapi import APIRouter, HTTPException

from app.core.categories import load_categories, sorted_store
from app.models.schemas import (
    AskRequest,
    AskResponse,
    CategoriesResponse,
    CategoryGroupOut,
    CategoryOut,
    DocChunkDetail,
)
from app.pipeline.retrieve import get_retriever

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="질문을 입력해 주세요.")
    return get_retriever().ask(request)


@router.post("/support", response_model=AskResponse)
def support(request: AskRequest) -> AskResponse:
    """`related_docs` 말풍선의 '담당자에게 문의하기'.

    화면에서 접수번호를 만들면 사용자가 본 번호와 이력에 남은 번호가 달라져 담당자가
    번호로 찾을 수 없다. 접수는 반드시 서버를 거친다.
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="접수할 질문이 없습니다.")
    return get_retriever().record_support(request)


@router.get("/categories", response_model=CategoriesResponse)
def categories() -> CategoriesResponse:
    """챗봇 화면용 — 미사용 항목은 빼고 정렬해서 준다."""
    store = sorted_store(load_categories(), enabled_only=True)
    return CategoriesResponse(
        groups=[
            CategoryGroupOut(
                group_id=g.group_id,
                group_name=g.group_name,
                categories=[
                    CategoryOut(category_id=c.category_id, name=c.name, questions=c.questions)
                    for c in g.categories
                ],
            )
            for g in store.groups
        ],
        quick_category_ids=store.quick_category_ids,
    )


@router.get("/docs/chunk/{chunk_id}", response_model=DocChunkDetail)
def doc_chunk(chunk_id: str) -> DocChunkDetail:
    """출처 배지·관련 문서 카드를 눌렀을 때 여는 상세 모달의 내용."""
    chunk = get_retriever().doc_index.get_chunk(chunk_id)
    if not chunk:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
    return DocChunkDetail(
        doc_id=chunk["doc_id"],
        title=chunk["title"],
        section=chunk["section"],
        text=chunk["text"],
        url_or_ref=chunk["url"],
    )


@router.get("/docs/{doc_id}", response_model=DocChunkDetail)
def doc_detail(doc_id: str) -> DocChunkDetail:
    """출처 배지는 청크가 아니라 문서 단위라 문서 첫 청크를 보여준다."""
    index = get_retriever().doc_index
    result = index.collection.get(where={"doc_id": doc_id}, limit=1, include=["documents", "metadatas"])
    documents = result.get("documents") or []
    if not documents:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
    meta = (result.get("metadatas") or [{}])[0]
    return DocChunkDetail(
        doc_id=doc_id,
        title=meta.get("title") or doc_id,
        section=meta.get("section_title", ""),
        text=documents[0],
        url_or_ref=meta.get("url", ""),
    )
