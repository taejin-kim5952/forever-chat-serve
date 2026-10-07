"""관리자 탭 ⑤ RAG 문서.

serve 모드에서는 **읽기 전용**이다. 문서를 고치면 재색인이 필요한데, 그 비용(문서 전체
임베딩)을 GPU 없는 운영 서버에서 요청 처리 중에 치를 수 없다. 편집은 스튜디오에서 하고
운영에는 결과 파일을 배포한다.
"""

from pathlib import Path

import frontmatter
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core import jobs
from app.core.auth import require_admin
from app.core.config import get_settings, is_studio
from app.core.logging import get_logger, log_event
from app.ingestion import doc_files
from app.ingestion.doc_upload import MAX_FILES_PER_REQUEST, UploadItem, register_uploads
from app.models.schemas import (
    DocBulkDeleteItem,
    DocBulkDeleteRequest,
    DocBulkDeleteResponse,
    DocCreateRequest,
    DocDetail,
    DocSaveRequest,
    DocSaveResponse,
    DocSummary,
    DocUploadItemResult,
    DocUploadResponse,
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
    qa_links: dict[str, int] = {}
    for item in qa_store.load_qa():
        for doc_id in item.source_doc_ids:
            qa_links[doc_id] = qa_links.get(doc_id, 0) + 1

    linked, loose = doc_files.pairs()
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
            linked_qa_count=qa_links.get(doc_id, 0),
            **_file_fields(linked.get(doc_id) or None),
        ))

    # 본문(`.md`) 없이 원본만 올라온 문서. **숨기지 않는다** — 검색에 걸리지 않는 상태를
    # 목록에서 보여줘야 "올렸는데 AI가 모른다"의 원인을 사람이 짚을 수 있다.
    for name, file_path in sorted(loose.items()):
        summaries.append(DocSummary(
            doc_id=file_path.stem, title=file_path.stem, chunk_count=0,
            linked_qa_count=qa_links.get(file_path.stem, 0), **_file_fields([file_path]),
        ))
    return summaries


def _file_fields(paths: list | None) -> dict:
    """`DocSummary` 의 원본 칸. 없으면 빈 값 — 화면이 그것으로 `색인 안 됨` 을 판단한다.
    여럿이면 **대표 하나**를 적고 크기는 합계로 둔다."""
    if not paths:
        return {}
    return {
        "file_kind": doc_files.kind_of(paths[0].suffix),
        "file_name": paths[0].name,
        "file_bytes": sum(p.stat().st_size for p in paths),
    }


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


@router.post("/upload", response_model=DocUploadResponse)
async def upload_docs(
    files: list[UploadFile] = File(..., description="문서 파일. 파일 이름이 문서 ID가 된다"),
    paths: list[str] = Form(default=[], description="폴더 안 상대 경로. 순서는 files 와 같다"),
    overwrite: bool = Form(default=False),
) -> DocUploadResponse:
    """폴더째 올린 문서를 파일 이름으로 등록한다(탭 ⑤ '폴더 업로드').

    화면이 폴더를 통째로 보내지 않고 몇 건씩 나눠 보낸다. 그래서 이 경로는 **묶음 하나**만
    처리하고 상태를 남기지 않는다 — 중간에 창을 닫아도 그때까지 들어간 문서는 그대로 남고,
    다시 올리면 이미 있는 것은 건너뛴다.
    """
    _require_studio()
    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(status_code=400, detail=f"한 번에 {MAX_FILES_PER_REQUEST}개까지 보낼 수 있습니다.")

    # 브라우저는 `webkitRelativePath` 를 파일 이름에 넣어주지 않는다. 하위 폴더까지 보이는
    # 경로를 화면이 따로 보내고, 어긋나면 파일 이름으로 돌아간다(결과 표의 표시에만 쓴다).
    items = [
        UploadItem(
            path=(paths[idx] if idx < len(paths) else None) or file.filename or "",
            data=await file.read(),
        )
        for idx, file in enumerate(files)
    ]

    started = jobs.now()
    results = register_uploads(items, index=get_retriever().doc_index, overwrite=overwrite)
    counts = {"created": 0, "updated": 0, "attached": 0, "skipped": 0, "failed": 0}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1

    # 화면이 몇 건씩 나눠 보내므로 묶음마다 이력을 남기면 폴더 하나가 열 줄을 차지한다.
    # `merge=True` 가 바로 이어지는 같은 작업을 한 줄로 합친다(app/core/jobs.py).
    jobs.record(
        "upload",
        status="failed" if counts["failed"] else "done",
        started_at=started,
        counts={"docs": counts["created"] + counts["updated"], **counts},
        merge=True,
        summary_from_counts=_upload_summary,
    )

    return DocUploadResponse(items=[DocUploadItemResult(**vars(r)) for r in results], **counts)


def _upload_summary(counts: dict) -> str:
    parts = [f"{counts.get('created', 0)}건 등록"]
    if counts.get("updated"):
        parts.append(f"{counts['updated']}건 갱신")
    if counts.get("attached"):
        parts.append(f"원본 {counts['attached']}건")
    if counts.get("skipped"):
        parts.append(f"{counts['skipped']}건 건너뜀")
    if counts.get("failed"):
        parts.append(f"{counts['failed']}건 실패")
    return " · ".join(parts)


@router.post("/bulk-delete", response_model=DocBulkDeleteResponse)
def bulk_delete_docs(request: DocBulkDeleteRequest) -> DocBulkDeleteResponse:
    """고른 문서를 한 번에 지운다 (탭 ⑤ 목록의 체크박스).

    **한 건이 실패해도 멈추지 않는다.** 열 건을 골랐는데 세 번째에서 멈추면 무엇이
    지워졌는지 사람이 알 수 없고, 다시 누르기도 겁난다. 건마다 결과를 따로 돌려준다.

    `DELETE` 가 아니라 `POST` 인 이유: 목록을 본문에 실어야 하는데 `DELETE` 의 본문은
    중간 프록시가 버리기도 한다. QA 일괄 작업(`POST /api/admin/qa/bulk`)과 같은 모양이다.

    삭제 순서는 **파일 먼저, 벡터 다음**이다(`app/api/admin_qa.py` 와 같은 규칙). 벡터를
    먼저 지우면 파일 삭제가 실패했을 때 목록에는 있는데 검색에서만 사라진 문서가 남는다.
    """
    _require_studio()

    items: list[DocBulkDeleteItem] = []
    index = get_retriever().doc_index
    for doc_id in dict.fromkeys(request.doc_ids):      # 같은 id 가 두 번 와도 한 번만
        path = _doc_path(doc_id)
        if not path.exists():
            # 본문이 없고 원본만 있는 문서(목록의 `색인 안 됨`). 지울 길이 없으면 목록에서
            # 치울 수가 없다.
            if doc_files.remove(doc_id):
                items.append(DocBulkDeleteItem(doc_id=doc_id, status="deleted"))
            else:
                items.append(DocBulkDeleteItem(doc_id=doc_id, status="failed", reason="문서를 찾을 수 없습니다"))
            continue
        # 묶인 원본은 **본문을 지우기 전에** 잡아 둔다. 지우고 나면 앞머리를 읽을 수
        # 없어 무엇이 묶여 있었는지 알 수 없다.
        originals = doc_files.find_all(doc_id)
        try:
            path.unlink()
            doc_files.remove_orphans(originals)
            index.delete_doc(doc_id)
        except OSError as exc:
            # 파일이 열려 있거나 권한이 없는 경우(리눅스에서 chown 을 안 맞춘 설치가 그렇다).
            items.append(DocBulkDeleteItem(doc_id=doc_id, status="failed", reason=str(exc)))
            continue
        items.append(DocBulkDeleteItem(doc_id=doc_id, status="deleted"))

    deleted = sum(1 for i in items if i.status == "deleted")
    failed = len(items) - deleted
    log_event(logger, "docs bulk deleted", requested=len(request.doc_ids), deleted=deleted, failed=failed)
    return DocBulkDeleteResponse(items=items, deleted=deleted, failed=failed)


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
    originals = doc_files.find_all(doc_id)
    path.unlink()
    doc_files.remove_orphans(originals)
    get_retriever().doc_index.delete_doc(doc_id)
    log_event(logger, "doc deleted", doc_id=doc_id)
    return DocSaveResponse(doc_id=doc_id, chunks_created=0, status="deleted")
