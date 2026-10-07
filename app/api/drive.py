"""자료 목록 — 사용자 화면(드라이브)이 왼쪽 폴더 카드와 가운데 파일 목록을 그리는 데 쓴다.

### `/api/library` 와 왜 따로 두는가

서가(`library.py`)는 **주제 → 문서**로 묶어 "무엇을 물을 수 있는지" 를 보여 준다. 드라이브는
**파일 한 줄짜리 목록**이고 정렬·종류 필터·페이지가 붙는다. 같은 응답을 비틀어 쓰면 한쪽
화면을 고칠 때마다 다른 쪽이 깨진다 — 새 화면에는 컨트롤러도 새로 만든다(CLAUDE.md).

### 한 번에 전부 준다

프로젝트 수는 많아야 열 몇 개이고 문서는 수백 건이다. 화면이 받아 두고 거기서 걸러·정렬·
나눠 보는 쪽이, 조건이 바뀔 때마다 서버를 다시 부르는 것보다 빠르고 코드도 적다. 퍼블
산출물의 `drive.js` 가 이미 그렇게 동작한다 — 그 구조를 그대로 살렸다.

### 등록일은 파일 수정 시각이다

앞머리(frontmatter)의 `updated` 는 **문서 내용의 날짜**다(사람이 적는다). 목록의 '등록일' 은
"언제 이 서버에 들어왔는가" 라서 둘이 다르다. 폐쇄망에 폴더를 복사해 넣는 배포에서도
파일 시각이 함께 따라오므로 이쪽이 사실에 가깝다.
"""

from pathlib import Path

import frontmatter
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core import projects
from app.core.config import get_settings, reset_project, use_project
from app.core.logging import get_logger
from app.core.profile import load_profile
from app.ingestion import doc_files
from app.pipeline.retrieve import get_retriever
from app.qa import store as qa_store

logger = get_logger("api.drive")

router = APIRouter(prefix="/api/drive", tags=["drive"])


class DriveFile(BaseModel):
    """본문에 묶인 원본 하나."""

    name: str
    kind: str = "etc"
    bytes: int = 0


class DriveDoc(BaseModel):
    doc_id: str
    title: str
    project: str = ""
    project_name: str = ""
    # 대표 원본의 종류. `ppt` · `pdf` · `doc` · `xls` · `hwp` · `zip` · `img` · `etc`,
    # 원본이 없으면 `md`. 목록의 아이콘과 내려받기 버튼은 하나씩만 둘 수 있어 대표를 정한다.
    kind: str = "md"
    file_name: str = ""
    bytes: int = 0
    # 묶인 원본 전부. 본문 하나가 여럿을 가리킬 수 있다(앞머리 `source_files`).
    files: list[DriveFile] = Field(default_factory=list)
    chunk_count: int = 0
    # 거짓이면 원본만 올라와 검색에 걸리지 않는 문서다. 화면이 `색인 안 됨` 을 띄운다.
    indexed: bool = True
    qa_count: int = 0
    category: str = ""
    updated: str = ""


class DriveProject(BaseModel):
    project_id: str
    name: str
    # `knowledge` 는 묻고 답하는 지식 자료, `library` 는 받아 쓰는 양식(자료실).
    # 화면이 메뉴를 가르는 데 쓴다 — 서버는 둘을 똑같이 다룬다.
    role: str = "knowledge"
    doc_count: int = 0
    bytes: int = 0
    # 이 프로젝트에서 물어볼 수 있는 질문 몇 개(카테고리의 추천 질문).
    # **챗봇은 물어봐야 답한다** — 무엇을 물을 수 있는지 모르는 사람은 아무것도 묻지 못하고
    # 나간다. 예전 화면의 '자료 서재' 가 하던 일을 이 목록이 대신한다.
    questions: list[str] = Field(default_factory=list)


class DriveResponse(BaseModel):
    projects: list[DriveProject] = Field(default_factory=list)
    docs: list[DriveDoc] = Field(default_factory=list)
    # 사이드바의 `N GB 사용`. 한도는 두지 않는다 — 폐쇄망 단일 서버라 걸 상대가 없다.
    total_bytes: int = 0


@router.get("", response_model=DriveResponse)
def get_drive() -> DriveResponse:
    found = projects.list_projects(enabled_only=True)
    if not found:
        docs = _docs_of("", load_profile().service_name)
        return DriveResponse(
            projects=[DriveProject(project_id="", name=load_profile().service_name,
                                   doc_count=len(docs), bytes=sum(d.bytes for d in docs),
                                   questions=_questions())],
            docs=docs, total_bytes=sum(d.bytes for d in docs),
        )

    out = DriveResponse()
    for project in found:
        token = use_project(project.project_id)
        try:
            docs = _docs_of(project.project_id, project.name)
        finally:
            reset_project(token)
        # 프로젝트에 적어 둔 것이 **이깁니다.** 카테고리 쪽은 이미 쓰고 있는 팩이 있어
        # 그대로 두되, 둘 다 있으면 프로젝트 것만 씁니다 — 섞으면 관리자가 적은 순서가
        # 깨지고, 지운 질문이 카테고리 쪽에서 되살아납니다.
        questions = list(project.questions)
        if not questions:
            token = use_project(project.project_id)
            try:
                questions = _questions()
            finally:
                reset_project(token)
        out.projects.append(DriveProject(
            project_id=project.project_id, name=project.name, role=project.role,
            doc_count=len(docs), bytes=sum(d.bytes for d in docs), questions=questions,
        ))
        out.docs.extend(docs)
    out.total_bytes = sum(d.bytes for d in out.docs)
    return out


def _questions(limit: int = 8) -> list[str]:
    """지금 프로젝트의 추천 질문. 카테고리를 돌며 **한 카테고리에서 하나씩** 집는다 —
    앞 카테고리 것으로만 채우면 주제 폭이 좁아 보인다."""
    from app.core.categories import load_categories, sorted_store

    pools = [list(c.questions) for g in sorted_store(load_categories(), enabled_only=True).groups
             for c in g.categories if c.questions]
    out: list[str] = []
    while pools and len(out) < limit:
        for pool in list(pools):
            if not pool:
                pools.remove(pool)
                continue
            out.append(pool.pop(0))
            if len(out) >= limit:
                break
    return out


def _docs_of(project_id: str, project_name: str) -> list[DriveDoc]:
    """지금 컨텍스트가 가리키는 프로젝트의 자료 전부."""
    index = get_retriever().doc_index
    chunks: dict[str, int] = {}
    for meta in (index.collection.get(include=["metadatas"])["metadatas"] or []):
        doc_id = meta.get("doc_id") or ""
        if doc_id:
            chunks[doc_id] = chunks.get(doc_id, 0) + 1

    qa_counts: dict[str, int] = {}
    for item in qa_store.load_qa():
        if item.status != "approved":
            continue
        for doc_id in item.source_doc_ids or []:
            qa_counts[doc_id] = qa_counts.get(doc_id, 0) + 1

    linked, loose = doc_files.pairs()
    docs_dir = Path(get_settings().raw_docs_dir)
    out: list[DriveDoc] = []

    def as_files(paths: list) -> list[DriveFile]:
        return [DriveFile(name=p.name, kind=doc_files.kind_of(p.suffix),
                          bytes=p.stat().st_size) for p in paths]

    for path in sorted(docs_dir.glob("*.md")) if docs_dir.is_dir() else []:
        doc_id = path.stem
        try:
            post = frontmatter.load(path)
        except Exception:  # noqa: BLE001 - 앞머리가 깨진 파일 하나가 목록을 통째로 막으면 안 된다
            post = frontmatter.Post(content="")
        originals = linked.get(doc_id, [])
        primary = originals[0] if originals else None
        out.append(DriveDoc(
            doc_id=doc_id,
            title=str(post.get("title") or doc_id),
            project=project_id, project_name=project_name,
            kind=doc_files.kind_of(primary.suffix) if primary else "md",
            file_name=primary.name if primary else path.name,
            # 크기는 **묶인 원본 전부**의 합이다. 대표 하나만 세면 사이드바의 보관량이
            # 실제 차지한 용량과 어긋난다.
            bytes=sum(p.stat().st_size for p in originals) or path.stat().st_size,
            files=as_files(originals),
            chunk_count=chunks.get(doc_id, 0),
            indexed=chunks.get(doc_id, 0) > 0,
            qa_count=qa_counts.get(doc_id, 0),
            category=str(post.get("category") or ""),
            updated=_date_of(primary or path),
        ))

    # 본문 없이 원본만 올라온 것. 검색에 걸리지 않지만 **목록에는 보여야** 한다 —
    # 숨기면 "올렸는데 AI가 모른다"의 원인을 사람이 짚을 수 없다.
    for name, original in sorted(loose.items()):
        out.append(DriveDoc(
            doc_id=original.stem, title=original.stem,
            project=project_id, project_name=project_name,
            kind=doc_files.kind_of(original.suffix), file_name=name,
            bytes=original.stat().st_size, files=as_files([original]),
            chunk_count=0, indexed=False,
            qa_count=qa_counts.get(original.stem, 0), updated=_date_of(original),
        ))
    return out


def _date_of(path: Path) -> str:
    import datetime

    return datetime.date.fromtimestamp(path.stat().st_mtime).isoformat()


@router.get("/{doc_id}/file")
def download(doc_id: str, name: str = ""):
    """자료 하나를 내려준다. **원본이 있으면 원본, 없으면 `.md` 원문.**

    어느 프로젝트인지는 `?project=` 가 정한다(`ProjectMiddleware`). 화면이 목록에서 받은
    `project` 를 그대로 붙여 보내므로 여기서 다시 찾지 않는다.
    """
    if not doc_id or "/" in doc_id or "\\" in doc_id or doc_id.startswith("."):
        raise HTTPException(status_code=400, detail="문서 ID에 경로 문자를 쓸 수 없습니다.")

    # `?name=` 은 **그 문서에 묶인 원본 중에서만** 고를 수 있다. 아무 이름이나 받으면
    # 이름만 바꿔 보내 다른 문서의 원본을 받아 갈 수 있다.
    path = doc_files.find_named(doc_id, name) if name else doc_files.find(doc_id)
    if path is None and not name:
        path = Path(get_settings().raw_docs_dir) / f"{doc_id}.md"
    if path is None:
        raise HTTPException(status_code=404, detail="자료를 찾을 수 없습니다.")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="자료를 찾을 수 없습니다.")

    return FileResponse(path, filename=path.name)
