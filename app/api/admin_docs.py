"""관리자 탭 ⑤ RAG 문서.

serve 모드에서는 **읽기 전용**이다. 문서를 고치면 재색인이 필요한데, 그 비용(문서 전체
임베딩)을 GPU 없는 운영 서버에서 요청 처리 중에 치를 수 없다. 편집은 스튜디오에서 하고
운영에는 결과 파일을 배포한다.
"""

from pathlib import Path

import frontmatter
from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import require_admin
from app.core.config import get_settings, is_studio
from app.core.logging import get_logger, log_event
from app.models.schemas import (
    DocCreateRequest,
    DocDetail,
    DocSaveRequest,
    DocSaveResponse,
    DocSummary,
)
from app.pipeline.retrieve import get_retriever
from app.qa import store as qa_store

logger = get_logger("api.admin_docs")

router = APIRouter(prefix="/api/admin/docs", tags=["admin-docs"], dependencies=[Depends(require_admin)])


def _require_studio() -> None:
    if not is_studio():
        raise HTTPException(status_code=403, detail="운영에서는 문서를 조회만 할 수 있습니다. 편집은 스튜디오에서 진행합니다.")


def _docs_dir() -> Path:
    path = Path(get_settings().raw_docs_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _doc_path(doc_id: str) -> Path:
    # doc_id 가 경로로 해석되면 문서 디렉터리 밖의 파일을 읽고 쓸 수 있다.
    if not doc_id or "/" in doc_id or "\\" in doc_id or doc_id.startswith("."):
        raise HTTPException(status_code=400, detail="문서 ID에 경로 문자를 쓸 수 없습니다.")
    return _docs_dir() / f"{doc_id}.md"


@router.get("", response_model=list[DocSummary])
def list_docs() -> list[DocSummary]:
    index = get_retriever().doc_index
    linked: dict[str, int] = {}
    for item in qa_store.load_qa():
        for doc_id in item.source_doc_ids:
            linked[doc_id] = linked.get(doc_id, 0) + 1

    summaries = []
    for path in sorted(_docs_dir().glob("*.md")):
        post = frontmatter.load(path)
        doc_id = path.stem
        summaries.append(DocSummary(
            doc_id=doc_id,
            title=post.get("title", doc_id),
            category=post.get("category", ""),
            updated=str(post.get("updated", "")),
            chunk_count=index.count_chunks(doc_id),
            linked_qa_count=linked.get(doc_id, 0),
        ))
    return summaries


@router.get("/{doc_id}", response_model=DocDetail)
def get_doc(doc_id: str) -> DocDetail:
    path = _doc_path(doc_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
    return DocDetail(doc_id=doc_id, content=path.read_text(encoding="utf-8"))


@router.post("", response_model=DocSaveResponse)
def create_doc(request: DocCreateRequest) -> DocSaveResponse:
    _require_studio()
    path = _doc_path(request.doc_id)
    if path.exists():
        raise HTTPException(status_code=409, detail="같은 ID의 문서가 이미 있습니다.")
    path.write_text(request.content, encoding="utf-8")
    chunks = get_retriever().doc_index.ingest_file(path, force=True)
    log_event(logger, "doc created", doc_id=request.doc_id, chunks=chunks)
    return DocSaveResponse(doc_id=request.doc_id, chunks_created=chunks, status="created")


@router.put("/{doc_id}", response_model=DocSaveResponse)
def save_doc(doc_id: str, request: DocSaveRequest) -> DocSaveResponse:
    _require_studio()
    path = _doc_path(doc_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
    path.write_text(request.content, encoding="utf-8")
    chunks = get_retriever().doc_index.ingest_file(path, force=True)
    log_event(logger, "doc saved", doc_id=doc_id, chunks=chunks)
    return DocSaveResponse(doc_id=doc_id, chunks_created=chunks, status="saved")


@router.delete("/{doc_id}", response_model=DocSaveResponse)
def delete_doc(doc_id: str) -> DocSaveResponse:
    _require_studio()
    path = _doc_path(doc_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
    path.unlink()
    get_retriever().doc_index.delete_doc(doc_id)
    log_event(logger, "doc deleted", doc_id=doc_id)
    return DocSaveResponse(doc_id=doc_id, chunks_created=0, status="deleted")
