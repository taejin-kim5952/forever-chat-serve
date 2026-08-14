"""질문 카테고리 저장소.

관리자 화면(탭 ③)에서 등록·수정하고, 챗봇 화면이 `GET /api/categories` 로 읽어간다.
2단계 구조(대분류 group → 카테고리 category)이며, 카테고리마다 추천 질문을 갖는다.

**필드 이름은 퍼블 산출물(`chat.js` 의 `CATEGORY_GROUPS`)과 일부러 똑같이 맞췄다.**
`group_id` / `group_name` / `categories[].category_id` / `name` / `questions`.
서버가 다른 이름을 쓰면 화면과 서버 사이에 변환 계층이 하나 더 생기고, 그 계층은 화면을
고칠 때마다 같이 틀어진다. 퍼블 더미를 그대로 서버 응답으로 바꿔 끼울 수 있게 두는 편이 낫다.
"""

import threading
from pathlib import Path

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.jsonstore import read_json, write_json_atomic
from app.core.logging import get_logger, log_event

logger = get_logger("core.categories")

_LOCK = threading.Lock()

# 챗봇 인트로의 '자주 찾는 주제' 칩 개수 상한. 퍼블 요청서 5-4 와 같은 값.
QUICK_LIMIT = 6


class Category(BaseModel):
    category_id: str
    name: str
    group_id: str = ""
    questions: list[str] = Field(default_factory=list)
    enabled: bool = True
    sort: int = 0


class CategoryGroup(BaseModel):
    group_id: str
    group_name: str
    enabled: bool = True
    sort: int = 0
    categories: list[Category] = Field(default_factory=list)


class CategoryStore(BaseModel):
    groups: list[CategoryGroup] = Field(default_factory=list)
    quick_category_ids: list[str] = Field(default_factory=list)


def _path() -> Path:
    return Path(get_settings().categories_file)


def load_categories() -> CategoryStore:
    """매 호출마다 파일에서 읽는다 — 관리자 화면에서 저장하면 다음 요청부터 바로 반영되도록."""
    data = read_json(_path())
    if data is None:
        return CategoryStore()
    try:
        return CategoryStore(**data)
    except ValueError as exc:
        # 파일이 깨졌다고 챗봇 전체가 멈추면 안 되므로 빈 목록으로 동작시키되,
        # 조용히 사라지면 "카테고리가 왜 안 보이지"로 한참 헤매게 되므로 반드시 남긴다.
        log_event(logger, "categories file unreadable, using empty list", path=str(_path()), error=str(exc))
        return CategoryStore()


def save_categories(store: CategoryStore) -> None:
    with _LOCK:
        write_json_atomic(_path(), store.model_dump_json(indent=2))


def find_category(store: CategoryStore, category_id: str) -> Category | None:
    for group in store.groups:
        for category in group.categories:
            if category.category_id == category_id:
                return category
    return None


def category_label(category_id: str | None) -> str | None:
    """id 로 라벨을 찾는다. 화면이 보내온 라벨을 그대로 믿지 않기 위한 것 —
    카테고리 이름이 바뀌면 이력에 옛 이름이 계속 쌓인다."""
    if not category_id:
        return None
    found = find_category(load_categories(), category_id)
    return found.name if found else None


def sorted_store(store: CategoryStore, enabled_only: bool = False) -> CategoryStore:
    """sort 순으로 정렬한 사본. `enabled_only` 면 미사용 항목을 걸러낸다(챗봇 화면용)."""
    groups = []
    for group in sorted(store.groups, key=lambda g: g.sort):
        if enabled_only and not group.enabled:
            continue
        categories = sorted(group.categories, key=lambda c: c.sort)
        if enabled_only:
            categories = [c for c in categories if c.enabled]
        groups.append(group.model_copy(update={"categories": categories}))

    quick = store.quick_category_ids[:QUICK_LIMIT]
    if enabled_only:
        # 미사용 카테고리가 자주 찾는 주제에 남아 있으면 챗봇 인트로에 죽은 칩이 뜬다.
        live = {c.category_id for g in groups for c in g.categories}
        quick = [cid for cid in quick if cid in live]

    return CategoryStore(groups=groups, quick_category_ids=quick)
