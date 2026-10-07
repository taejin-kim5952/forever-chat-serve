"""자료 서가 — 챗봇 왼쪽에 주제와 그 주제의 문서를 펼쳐 보여 준다.

### 왜 필요한가

챗봇은 **물어봐야 답한다.** 무엇을 물을 수 있는지 모르는 사람은 아무것도 묻지 못하고 나간다.
주제 목록은 팝오버 안에 숨어 있어서 누르기 전까지 보이지 않는다. 화면 왼쪽을 비워 두는 대신
**주제와 자료를 펼쳐 두면**, 들어온 사람이 "이런 걸 물어도 되는구나"를 먼저 알게 된다.

### 주제와 문서는 무엇으로 이어지는가

둘을 직접 잇는 필드는 없다. **승인된 QA가 다리를 놓는다.**

    카테고리 ──(QA.category_id)── QA ──(QA.source_doc_ids)── 문서

그래서 여기 나오는 문서는 "이 주제로 **실제로 답할 수 있는** 근거 자료"다. 문서 앞머리의
`category` 문자열로 잇지 않는 이유가 그것이다 — 그쪽은 사람이 분류해 둔 라벨일 뿐이라
답변과 무관할 수 있고, 라벨을 고치면 조용히 어긋난다.

**승인된 QA만 본다.** 검수 전 초안이 가리키는 문서를 서가에 올리면, 아직 사용자에게 나가지
않는 답변의 근거가 먼저 노출된다.
"""

import collections
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core import projects
from app.core.categories import load_categories, sorted_store
from app.core.config import reset_project, use_project
from app.core.logging import get_logger
from app.core.profile import load_profile
from app.pipeline.retrieve import get_retriever
from app.qa import store as qa_store

logger = get_logger("api.library")

router = APIRouter(prefix="/api", tags=["chat"])


class ShelfDoc(BaseModel):
    doc_id: str
    title: str
    # 책 두께로 쓴다. 긴 문서가 두껍게 보이면 서가가 한눈에 읽힌다.
    chunk_count: int = 0
    # 문서 앞머리의 `category` 문자열. 화면이 표지 색을 고르는 데 쓴다(`이용가이드` 등).
    category: str = ""


class ShelfCategory(BaseModel):
    category_id: str
    name: str
    questions: list[str] = Field(default_factory=list)
    docs: list[ShelfDoc] = Field(default_factory=list)
    # 이 주제로 답할 수 있는 QA 수. 0이면 아직 비어 있는 주제다.
    qa_count: int = 0


class ShelfGroup(BaseModel):
    """**프로젝트 하나**. 화면은 이것을 서재의 한 칸으로 그린다.

    이름이 `group_*` 인 것은 화면 산출물의 이름을 따른 것이다 — 퍼블이 쓰는 이름을 서버가
    따라가는 편이, 중간에 변환 계층을 두는 것보다 고칠 자리가 적다.
    """

    group_id: str
    group_name: str
    categories: list[ShelfCategory] = Field(default_factory=list)


class LibraryResponse(BaseModel):
    groups: list[ShelfGroup] = Field(default_factory=list)
    # 어느 주제에도 묶이지 않은 문서. 숨기면 "올렸는데 안 보인다"가 된다.
    unshelved: list[ShelfDoc] = Field(default_factory=list)


@router.get("/library", response_model=LibraryResponse)
def get_library() -> LibraryResponse:
    """**모든 프로젝트**의 자료 서재. 챗봇 화면이 왼쪽에 그린다.

    한 번에 전부 주는 이유: 화면의 프로젝트 선택기가 이 응답만 보고 돈다. 프로젝트를 바꿀
    때마다 서버를 다시 부르면 전환이 끊겨 보이고, 요청마다 어느 프로젝트인지를 헤더로
    실어 보내야 해서 화면이 복잡해진다. 프로젝트는 많아야 열 몇 개다.

    프로젝트가 하나도 없는 설치(= `PACK_DIR` 단일 팩)는 **지금 설정 그대로** 한 칸을 만든다.
    """
    projects_found = projects.list_projects(enabled_only=True)
    if not projects_found:
        return LibraryResponse(groups=[_shelf_group("", load_profile().service_name)])

    groups = []
    for project in projects_found:
        token = use_project(project.project_id)
        try:
            groups.append(_shelf_group(project.project_id, project.name))
        finally:
            reset_project(token)
    return LibraryResponse(groups=groups)


def _shelf_group(project_id: str, name: str) -> ShelfGroup:
    """지금 컨텍스트가 가리키는 프로젝트 하나를 서재 한 칸으로 만든다."""
    index = get_retriever().doc_index
    titles: dict[str, str] = {}
    chunks: dict[str, int] = {}
    kinds: dict[str, str] = {}
    for meta in (index.collection.get(include=["metadatas"])["metadatas"] or []):
        doc_id = meta.get("doc_id") or ""
        if not doc_id:
            continue
        titles.setdefault(doc_id, meta.get("title") or doc_id)
        # 앞머리의 `category` 는 `이용가이드 > 절차` 처럼 두 단계로 적는다. 표지 색을 고르는
        # 데만 쓰므로 **맨 앞 한 조각**만 넘긴다.
        kinds.setdefault(doc_id, str(meta.get("category") or "").split(">")[0].strip())
        chunks[doc_id] = chunks.get(doc_id, 0) + 1

    by_category: dict[str, set[str]] = collections.defaultdict(set)
    qa_counts: collections.Counter = collections.Counter()
    for item in qa_store.load_qa():
        if item.status != "approved" or not item.category_id:
            continue
        qa_counts[item.category_id] += 1
        by_category[item.category_id].update(item.source_doc_ids or [])

    def shelf(doc_id: str) -> ShelfDoc:
        return ShelfDoc(doc_id=doc_id, title=titles.get(doc_id, doc_id),
                        chunk_count=chunks.get(doc_id, 0), category=kinds.get(doc_id, ""))

    categories_out = []
    shelved: set[str] = set()
    # 대분류는 화면에서 접었다. 주제(카테고리)가 프로젝트 바로 아래 한 줄로 늘어선다 —
    # 자료가 몇 건뿐인 설치에서 두 단계는 누르는 품만 늘린다.
    for group in sorted_store(load_categories(), enabled_only=True).groups:
        for category in group.categories:
            docs = sorted(d for d in by_category.get(category.category_id, set()) if d in titles)
            shelved.update(docs)
            categories_out.append(ShelfCategory(
                category_id=category.category_id, name=category.name,
                questions=category.questions, docs=[shelf(d) for d in docs],
                qa_count=qa_counts.get(category.category_id, 0),
            ))

    # 어느 주제에도 안 묶인 문서는 맨 아래 한 칸에 모은다. 숨기면 "올렸는데 안 보인다"가 된다.
    loose = sorted(set(titles) - shelved)
    if loose:
        categories_out.append(ShelfCategory(
            category_id="", name="주제 미지정", docs=[shelf(d) for d in loose],
        ))

    return ShelfGroup(group_id=project_id, group_name=name, categories=categories_out)
