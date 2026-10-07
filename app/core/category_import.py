"""질문 카테고리를 JSON 으로 한 번에 들여온다 (탭 ③ '카테고리 가져오기').

### 왜 필요한가

카테고리는 대분류 5 · 카테고리 48 규모로 시작한다. 화면에서 한 건씩 만들면 48번을 눌러야
하고, 그 사이에 오타가 나면 챗봇 인트로에 죽은 칩이 뜬다. 실제로는 **다른 곳에서 한꺼번에
만들어 온다** — AI 에게 규격을 주고 받아오거나, 다른 설치본의 `categories.json` 을 옮기거나.
그 길을 화면에 열어 준다.

### 화면과의 분담

파일을 읽어 텍스트로 만드는 것까지가 화면 몫이고(파일 선택·붙여넣기가 같은 칸으로 모인다),
**형식을 아는 쪽은 서버 하나뿐이다.** 화면이 JSON 을 해석해 트리에 끼워 넣게 하면 규격이
바뀔 때마다 화면과 서버 두 곳을 고치게 되고, 두 판단이 어긋나면 미리보기와 실제 반영이
달라진다. 그래서 미리보기와 반영이 **같은 텍스트를 같은 함수에 넣는다**(`_plan`).

### 지키는 것 셋

1. **미리보기 없이는 반영하지 않는다.** 카테고리는 챗봇 첫 화면에 그대로 나가므로,
   무엇이 새로 생기고 무엇이 덮이는지 사람이 먼저 본다.
2. **merge 는 지우지 않는다.** 파일에 없는 기존 카테고리는 그대로 남는다. 지우는 것은
   `replace` 뿐이고, 그때는 사라질 항목을 미리보기에 `삭제` 로 전부 보여준다.
3. **merge 에서 기존 항목의 순서(`sort`)는 건드리지 않는다.** 파일에 순서가 없어도
   보이는 순서가 뒤집히지 않게 하려는 것이다 — 이름만 고치려고 올린 파일이 챗봇
   인트로의 배열을 바꿔 놓으면 아무도 원인을 못 찾는다. 새 항목만 뒤에 붙는다.
"""

import json
import re
from typing import Literal

from pydantic import BaseModel, Field

from app.core.categories import (
    Category,
    CategoryGroup,
    CategoryStore,
    QUICK_LIMIT,
    load_categories,
    save_categories,
)
from app.core.logging import get_logger, log_event

logger = get_logger("core.category_import")

# 들여오기 방식 — 합치기(기본) / 전체 교체
Mode = Literal["merge", "replace"]
# 미리보기 한 줄의 상태. `keep`(그대로 둠)은 줄로 만들지 않고 숫자로만 센다 —
# 안 바뀌는 것이 대부분이라, 줄로 만들면 정작 바뀌는 것이 묻힌다.
RowStatus = Literal["new", "over", "gone"]

# id 는 화면의 `data-category-id` 와 챗봇 링크에 그대로 들어간다. 한글 id 도 실제로
# 동작하므로 문자 종류까지 막지는 않고, **깨지는 것만** 막는다(공백·따옴표·꺾쇠).
_BAD_ID = re.compile(r"""[\s"'<>]""")
MAX_ID_LEN = 64


class PreviewRow(BaseModel):
    kind: Literal["group", "category"]
    group_id: str = ""
    group_name: str = ""
    category_id: str = ""
    name: str = ""
    questions: int = 0
    status: RowStatus
    reason: str = ""


class Counts(BaseModel):
    new: int = 0
    over: int = 0
    keep: int = 0
    gone: int = 0


class PreviewResponse(BaseModel):
    mode: Mode = "merge"
    rows: list[PreviewRow] = Field(default_factory=list)
    counts: Counts = Field(default_factory=Counts)
    # 반영 뒤에 남을 전체 규모. "48개를 올렸는데 왜 12개지" 를 반영 전에 알아채는 자리다.
    groups: int = 0
    categories: int = 0
    quick_category_ids: list[str] = Field(default_factory=list)


class ImportRequest(BaseModel):
    # 파일 내용 또는 붙여넣은 텍스트. 화면이 둘을 같은 칸으로 모아 보낸다.
    content: str = ""
    mode: Mode = "merge"


class ImportResponse(BaseModel):
    counts: Counts = Field(default_factory=Counts)
    store: CategoryStore = Field(default_factory=CategoryStore)


# ─────────────────────────────────────────────────────────────────────── 읽기


def parse(content: str) -> CategoryStore:
    """텍스트에서 카테고리 묶음을 꺼낸다. 못 읽으면 `ValueError` — 화면이 그대로 보여준다.

    두 모양을 받는다. 사람이 어느 파일을 올릴지 미리 알고 있을 필요가 없어야 한다.

        {"groups": [...], "quick_category_ids": [...]}   정식(= categories.json)
        [...]                                            대분류 목록만 있는 파일

    **모르는 필드는 버린다.** AI 에게 받아온 파일에는 설명이나 메모가 붙어 오기 쉬운데,
    그것 때문에 전체가 막히면 규격을 아무리 잘 적어도 실패한다.
    """
    text = (content or "").strip()
    if not text:
        raise ValueError("내용이 비어 있습니다.")
    # ```json 울타리째 붙여넣는 일이 잦다. 형식 오류로 돌려보내는 대신 벗겨낸다.
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 형식이 아닙니다 ({exc.lineno}번째 줄: {exc.msg}).") from exc

    if isinstance(data, dict):
        raw_groups = data.get("groups")
        raw_quick = data.get("quick_category_ids") or []
    elif isinstance(data, list):
        raw_groups, raw_quick = data, []
    else:
        raise ValueError("맨 바깥이 { } 또는 [ ] 여야 합니다.")

    if not isinstance(raw_groups, list) or not raw_groups:
        raise ValueError("대분류(groups)가 없습니다. 규격의 예시를 확인해 주세요.")

    groups: list[CategoryGroup] = []
    seen_groups: dict[str, str] = {}
    seen_cats: dict[str, str] = {}

    for gi, raw in enumerate(raw_groups):
        if not isinstance(raw, dict):
            raise ValueError(f"{gi + 1}번째 대분류가 객체({{ }})가 아닙니다.")
        gid = _clean_id(raw.get("group_id"), f"{gi + 1}번째 대분류의 group_id")
        if gid in seen_groups:
            raise ValueError(f"대분류 ID가 겹칩니다: {gid}")
        seen_groups[gid] = gid

        raw_cats = raw.get("categories") or []
        if not isinstance(raw_cats, list):
            raise ValueError(f"'{gid}' 의 categories 가 목록([ ])이 아닙니다.")

        categories: list[Category] = []
        for ci, rawc in enumerate(raw_cats):
            if not isinstance(rawc, dict):
                raise ValueError(f"'{gid}' 의 {ci + 1}번째 카테고리가 객체({{ }})가 아닙니다.")
            cid = _clean_id(rawc.get("category_id"), f"'{gid}' 의 {ci + 1}번째 카테고리의 category_id")
            if cid in seen_cats:
                raise ValueError(f"카테고리 ID가 겹칩니다: {cid}")
            seen_cats[cid] = gid
            categories.append(
                Category(
                    category_id=cid,
                    name=_clean_text(rawc.get("name")) or cid,
                    group_id=gid,
                    questions=_clean_questions(rawc.get("questions")),
                    enabled=_clean_flag(rawc.get("enabled")),
                    sort=_clean_sort(rawc.get("sort"), ci),
                )
            )

        groups.append(
            CategoryGroup(
                group_id=gid,
                group_name=_clean_text(raw.get("group_name")) or gid,
                enabled=_clean_flag(raw.get("enabled")),
                sort=_clean_sort(raw.get("sort"), gi),
                categories=categories,
            )
        )

    if not seen_cats:
        raise ValueError("카테고리가 한 건도 없습니다. 대분류 안에 categories 를 채워 주세요.")

    quick = [str(q).strip() for q in raw_quick if isinstance(q, (str, int)) and str(q).strip()]
    return CategoryStore(groups=groups, quick_category_ids=quick)


def _clean_id(value: object, where: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{where} 가 비어 있습니다.")
    if _BAD_ID.search(text):
        raise ValueError(f"{where} 에 공백이나 따옴표를 쓸 수 없습니다: {text}")
    if len(text) > MAX_ID_LEN:
        raise ValueError(f"{where} 가 너무 깁니다({MAX_ID_LEN}자까지): {text}")
    return text


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _clean_questions(value: object) -> list[str]:
    """추천 질문. 목록이 아니거나 빈 문장이 섞여 와도 막지 않고 버린다 —
    카테고리 자체는 멀쩡한데 질문 하나 때문에 48건이 통째로 막히면 손해다."""
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        text = _clean_text(item)
        if text and text not in out:
            out.append(text)
    return out


def _clean_flag(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() not in {"false", "0", "no", ""}
    return bool(value)


def _clean_sort(value: object, fallback: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback


# ─────────────────────────────────────────────────────────────── 판단·반영


def _plan(incoming: CategoryStore, mode: Mode) -> tuple[CategoryStore, list[PreviewRow], Counts]:
    """반영하면 어떻게 되는지를 계산한다. **저장하지 않는다.**

    미리보기와 실제 반영이 이 함수 하나를 같이 쓴다. 화면이 '덮어씀 3건' 을 보여준 뒤
    실제로는 다르게 동작하면 확인 절차가 의미를 잃는다.
    """
    current = load_categories()
    rows: list[PreviewRow] = []
    counts = Counts()

    old_groups = {g.group_id: g for g in current.groups}
    old_cats = {c.category_id: (g.group_id, c) for g in current.groups for c in g.categories}
    new_ids = {c.category_id for g in incoming.groups for c in g.categories}

    if mode == "replace":
        result = incoming.model_copy(deep=True)
        for group in result.groups:
            for category in group.categories:
                category.group_id = group.group_id
                status = "over" if category.category_id in old_cats else "new"
                rows.append(_row_of(group, category, status))
                setattr(counts, status, getattr(counts, status) + 1)
        # 사라지는 것을 반드시 보여준다. replace 의 위험은 '추가'가 아니라 '삭제'다.
        for cid, (gid, category) in old_cats.items():
            if cid not in new_ids:
                rows.append(
                    PreviewRow(
                        kind="category", group_id=gid,
                        group_name=old_groups[gid].group_name if gid in old_groups else gid,
                        category_id=cid, name=category.name,
                        questions=len(category.questions), status="gone",
                        reason="파일에 없어 사라집니다",
                    )
                )
                counts.gone += 1
    else:
        result = current.model_copy(deep=True)
        by_id = {g.group_id: g for g in result.groups}
        next_group_sort = max((g.sort for g in result.groups), default=-1) + 1

        for group in incoming.groups:
            target = by_id.get(group.group_id)
            if target is None:
                target = CategoryGroup(
                    group_id=group.group_id, group_name=group.group_name,
                    enabled=group.enabled, sort=next_group_sort, categories=[],
                )
                next_group_sort += 1
                result.groups.append(target)
                by_id[target.group_id] = target
                rows.append(_row_of(target, None, "new"))
                counts.new += 1
            elif target.group_name != group.group_name:
                rows.append(_row_of(target, None, "over", f"이름이 '{group.group_name}' 로 바뀝니다"))
                target.group_name = group.group_name
                counts.over += 1

            next_sort = max((c.sort for c in target.categories), default=-1) + 1
            for category in group.categories:
                # 다른 대분류에 같은 id 가 있으면 옮겨 온다. 두 벌로 늘어나면 챗봇이
                # 어느 주제를 고른 것인지 알 수 없게 된다.
                moved_from = old_cats.get(category.category_id, (None, None))[0]
                if moved_from is not None and moved_from != group.group_id:
                    src = by_id.get(moved_from)
                    if src is not None:
                        src.categories = [c for c in src.categories if c.category_id != category.category_id]

                found = next((c for c in target.categories if c.category_id == category.category_id), None)
                if found is None:
                    fresh = category.model_copy(update={"group_id": target.group_id, "sort": next_sort})
                    next_sort += 1
                    target.categories.append(fresh)
                    rows.append(_row_of(target, fresh, "new"))
                    counts.new += 1
                else:
                    # **순서는 그대로 둔다.** 이유는 파일 상단 독스트링 3번.
                    found.name = category.name
                    found.questions = category.questions
                    found.enabled = category.enabled
                    found.group_id = target.group_id
                    rows.append(_row_of(target, found, "over",
                                        "옮겨 왔습니다" if moved_from and moved_from != target.group_id else ""))
                    counts.over += 1

        counts.keep = sum(1 for cid in old_cats if cid not in new_ids)

    result.quick_category_ids = _plan_quick(current, incoming, result, mode)
    return result, rows, counts


def _plan_quick(current: CategoryStore, incoming: CategoryStore, result: CategoryStore, mode: Mode) -> list[str]:
    """자주 찾는 주제. **파일에 없으면 지금 것을 지키는 쪽**이다 —
    카테고리를 늘리려고 올린 파일이 챗봇 첫 화면의 칩을 비워 버리면 안 된다."""
    live = {c.category_id for g in result.groups for c in g.categories}
    picked = list(incoming.quick_category_ids)
    if mode == "merge":
        picked = current.quick_category_ids + [q for q in picked if q not in current.quick_category_ids]
    elif not picked:
        picked = current.quick_category_ids

    out: list[str] = []
    for cid in picked:
        if cid in live and cid not in out:
            out.append(cid)
    return out[:QUICK_LIMIT]


def _row_of(group: CategoryGroup, category: Category | None, status: RowStatus, reason: str = "") -> PreviewRow:
    if category is None:
        return PreviewRow(kind="group", group_id=group.group_id, group_name=group.group_name,
                          status=status, reason=reason or "대분류")
    return PreviewRow(kind="category", group_id=group.group_id, group_name=group.group_name,
                      category_id=category.category_id, name=category.name,
                      questions=len(category.questions), status=status, reason=reason)


def preview(request: ImportRequest) -> PreviewResponse:
    result, rows, counts = _plan(parse(request.content), request.mode)
    return PreviewResponse(
        mode=request.mode, rows=rows, counts=counts,
        groups=len(result.groups),
        categories=sum(len(g.categories) for g in result.groups),
        quick_category_ids=result.quick_category_ids,
    )


def apply(request: ImportRequest) -> ImportResponse:
    result, _rows, counts = _plan(parse(request.content), request.mode)
    save_categories(result)
    log_event(logger, "categories imported", mode=request.mode,
              new=counts.new, over=counts.over, gone=counts.gone,
              groups=len(result.groups),
              categories=sum(len(g.categories) for g in result.groups))
    return ImportResponse(counts=counts, store=result)
