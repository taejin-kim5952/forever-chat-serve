"""챗봇이 쓰는 공개 API. 인증이 없는 유일한 영역이다."""

from pathlib import Path

import frontmatter
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import get_settings

from app.core.categories import load_categories, sorted_store
from app.core.feedback import REASON_LABELS, FeedbackEntry, append_feedback
from app.core.question_log import now_iso
from app.models.schemas import (
    AskRequest,
    AskResponse,
    CategoriesResponse,
    CategoryGroupOut,
    CategoryOut,
    DocChunkDetail,
    FeedbackRequest,
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


@router.post("/feedback")
def feedback(request: FeedbackRequest) -> dict:
    """답변 말풍선의 👍/👎.

    **여기서 받은 값은 QA의 상태를 바꾸지 않는다.** 관리자 화면의 표시·정렬에만 쓰인다 —
    사용자 클릭이 승인 상태를 움직이면 '검수한 답변만 나간다'는 전제가 무너진다.

    화면이 답변을 읽는 데 방해받지 않도록 판단을 느슨하게 둔다: 모르는 이유 값은 버리고
    투표만 남기며, 적재가 실패해도 200을 준다(`append_feedback` 이 예외를 삼킨다).
    """
    if not request.log_id.strip():
        raise HTTPException(status_code=400, detail="어느 답변에 대한 것인지 알 수 없습니다.")

    reason = request.reason if request.reason in REASON_LABELS else None
    append_feedback(
        FeedbackEntry(log_id=request.log_id, vote=request.vote, reason=reason, at=now_iso())
    )
    return {"ok": True}


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


# 문서에 들어가는 그림. 텍스트로 설명하기 어려운 절차(가입·배포 흐름)를 도식으로 보여준다.
# **답변에는 넣지 않는다** — 화면이 바뀌면 그 그림을 인용한 답변을 전부 고쳐야 하기 때문이다.
# 그림은 원본 문서에만 두고, 사용자는 출처 문서에서 본다.
IMAGE_TYPES = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg",
               ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}


@router.get("/docs/img/{filename}")
def doc_image(filename: str) -> FileResponse:
    """`data/raw_docs/img/` 의 그림 한 장.

    인증이 없는 경로라 **경로를 벗어나지 못하게 막는 것이 전부**다. 이름만 받고(`Path.name`),
    확장자를 흰 목록으로 거르고, 최종 경로가 그 폴더 안인지 다시 확인한다. 셋 중 하나만
    있어도 대개 충분하지만, 여기가 뚫리면 서버 파일이 그대로 나가는 자리다.
    """
    safe = Path(filename).name
    suffix = Path(safe).suffix.lower()
    if suffix not in IMAGE_TYPES:
        raise HTTPException(status_code=404, detail="이미지를 찾을 수 없습니다.")

    base = Path(get_settings().raw_docs_dir).resolve() / "img"
    path = (base / safe).resolve()
    if not path.is_file() or base not in path.parents:
        raise HTTPException(status_code=404, detail="이미지를 찾을 수 없습니다.")

    return FileResponse(path, media_type=IMAGE_TYPES[suffix])


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
    """출처 배지가 여는 문서. **문서 전체**를 준다.

    예전에는 첫 청크(첫 헤딩 앞 도입부)만 줬다. 배지에 문서 이름이 적혀 있는데 도입부
    한 문단만 열리면 "이게 왜 출처지"가 되고, 절차 도식처럼 아래쪽 절에 있는 내용은
    아예 볼 방법이 없었다. 관련 문서 카드는 실제로 걸린 절을 열어야 하므로 그대로
    `/docs/chunk/{chunk_id}` 를 쓴다 — 그쪽은 "왜 이 문서가 나왔나"가 질문이라 다르다.

    원본 파일을 읽는다. 벡터 저장소는 파생물이라 문서를 고치고 재색인하기 전까지
    옛 내용을 들고 있다.
    """
    index = get_retriever().doc_index
    result = index.collection.get(where={"doc_id": doc_id}, limit=1, include=["metadatas"])
    metadatas = result.get("metadatas") or []
    if not metadatas:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
    meta = metadatas[0]

    path = Path(get_settings().raw_docs_dir) / f"{Path(doc_id).name}.md"
    if path.is_file():
        body = frontmatter.load(path).content.strip()
    else:
        # 파일이 없어도(삭제·이름 변경) 색인에 남은 내용으로 열리게 둔다.
        chunks = index.collection.get(where={"doc_id": doc_id}, include=["documents"])
        body = "\n\n".join(chunks.get("documents") or [])

    return DocChunkDetail(
        doc_id=doc_id,
        title=meta.get("title") or doc_id,
        section=meta.get("category", ""),
        text=body,
        url_or_ref=meta.get("url", ""),
    )
