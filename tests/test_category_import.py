"""질문 카테고리 JSON 가져오기 (탭 ③).

카테고리는 **챗봇 첫 화면에 그대로 나가는 것**이라, 여기서 지키는 것은 기능보다 경계다.

- 미리보기와 실제 반영이 **같은 판단**을 쓴다 — 다르면 확인 절차가 의미를 잃는다
- `merge` 는 지우지 않는다. 지우는 것은 `replace` 뿐이고, 사라질 항목을 미리 보여준다
- `merge` 는 기존 항목의 **순서를 건드리지 않는다** — 이름 하나 고치려고 올린 파일이
  인트로 배열을 바꿔 놓으면 아무도 원인을 못 찾는다
- 형식 오류는 **어디를 고쳐야 하는지** 말해 준다. 사람이 고칠 수 있는 오류이기 때문이다
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.core import categories as cat_store
from app.core import category_import
from app.main import app

AUTH = ("tester", "secret")


def _client() -> TestClient:
    return TestClient(app)


def _payload(*groups: dict, quick: list[str] | None = None) -> str:
    body: dict = {"groups": list(groups)}
    if quick is not None:
        body["quick_category_ids"] = quick
    return json.dumps(body, ensure_ascii=False)


def _group(gid: str, name: str, *cats: dict) -> dict:
    return {"group_id": gid, "group_name": name, "categories": list(cats)}


def _cat(cid: str, name: str, questions: list[str] | None = None, **kw) -> dict:
    return {"category_id": cid, "name": name, "questions": questions or [], **kw}


def _seed(*groups: cat_store.CategoryGroup, quick: list[str] | None = None) -> None:
    cat_store.save_categories(
        cat_store.CategoryStore(groups=list(groups), quick_category_ids=quick or [])
    )


def _existing() -> cat_store.CategoryGroup:
    return cat_store.CategoryGroup(
        group_id="server", group_name="서버 관리", sort=0,
        categories=[
            cat_store.Category(category_id="reg", name="서버 등록", group_id="server",
                               questions=["등록은 어떻게 하나요?"], sort=0),
            cat_store.Category(category_id="perm", name="권한", group_id="server", sort=1),
        ],
    )


# ── 읽기 ─────────────────────────────────────────────────────────────────────


def test_reads_both_file_shapes():
    """올리는 사람이 어느 모양인지 알고 있을 필요가 없어야 한다."""
    formal = category_import.parse(_payload(_group("g", "대분류", _cat("c", "카테고리"))))
    bare = category_import.parse(json.dumps([_group("g", "대분류", _cat("c", "카테고리"))], ensure_ascii=False))

    assert [g.group_id for g in formal.groups] == [g.group_id for g in bare.groups] == ["g"]


def test_code_fence_is_stripped():
    """AI 답변을 통째로 붙여넣는 일이 잦다. 울타리 때문에 되돌려 보내지 않는다."""
    raw = "```json\n" + _payload(_group("g", "대분류", _cat("c", "카테고리"))) + "\n```"
    assert category_import.parse(raw).groups[0].group_id == "g"


def test_optional_fields_get_defaults():
    """`sort`·`enabled`·`questions` 가 없어도 들어와야 한다 — 규격에서 생략 가능이라고 했다."""
    store = category_import.parse(_payload(_group("g", "대분류", {"category_id": "c", "name": "이름"})))
    category = store.groups[0].categories[0]

    assert category.enabled is True and category.sort == 0 and category.questions == []
    assert category.group_id == "g", "대분류 안에 있으면 group_id 는 서버가 채운다"


def test_unknown_fields_are_dropped():
    """AI 가 붙여 보내는 설명·메모 때문에 48건이 통째로 막히면 안 된다."""
    store = category_import.parse(_payload(_group("g", "대분류", _cat("c", "이름", 설명="이건 메모입니다"))))
    assert store.groups[0].categories[0].category_id == "c"


@pytest.mark.parametrize(
    "content, expected",
    [
        ("{", "JSON 형식이 아닙니다"),
        ("", "비어 있습니다"),
        ('{"groups": []}', "대분류(groups)가 없습니다"),
        ('{"groups": [{"group_id": "g", "categories": []}]}', "카테고리가 한 건도 없습니다"),
        ('{"groups": [{"group_id": "", "categories": []}]}', "group_id 가 비어 있습니다"),
        ('{"groups": [{"group_id": "a b", "categories": []}]}', "공백이나 따옴표"),
    ],
)
def test_broken_files_say_where_to_fix(content: str, expected: str):
    """'Internal Server Error' 로는 파일의 어디를 고쳐야 하는지 알 수 없다."""
    with pytest.raises(ValueError) as err:
        category_import.parse(content)
    assert expected in str(err.value)


def test_duplicate_ids_are_refused():
    """id 가 겹치면 챗봇이 어느 주제를 고른 것인지 알 수 없게 된다."""
    with pytest.raises(ValueError, match="카테고리 ID가 겹칩니다"):
        category_import.parse(_payload(_group("g", "대분류", _cat("c", "하나"), _cat("c", "둘"))))


# ── 합치기 ───────────────────────────────────────────────────────────────────


def test_merge_never_deletes():
    """파일에 없는 기존 카테고리는 그대로 남는다. 지우는 것은 replace 뿐이다."""
    _seed(_existing())
    category_import.apply(category_import.ImportRequest(
        content=_payload(_group("docs", "문서", _cat("guide", "가이드"))), mode="merge"))

    ids = {c.category_id for g in cat_store.load_categories().groups for c in g.categories}
    assert ids == {"reg", "perm", "guide"}


def test_merge_keeps_the_order_of_existing_items():
    """이름만 고치려고 올린 파일이 챗봇 인트로의 배열을 바꾸면 원인을 못 찾는다."""
    _seed(_existing())
    category_import.apply(category_import.ImportRequest(
        # 파일에서는 순서가 반대다. 그래도 화면 순서는 그대로여야 한다.
        content=_payload(_group("server", "서버 관리", _cat("perm", "권한 관리"), _cat("reg", "서버 등록"))),
        mode="merge"))

    group = cat_store.load_categories().groups[0]
    assert [c.category_id for c in sorted(group.categories, key=lambda c: c.sort)] == ["reg", "perm"]
    assert {c.category_id: c.name for c in group.categories}["perm"] == "권한 관리", "이름은 갱신된다"


def test_merge_moves_a_category_that_changed_group():
    """대분류를 옮겨 오면 두 벌로 늘어나면 안 된다."""
    _seed(_existing(), cat_store.CategoryGroup(group_id="docs", group_name="문서", sort=1))
    category_import.apply(category_import.ImportRequest(
        content=_payload(_group("docs", "문서", _cat("perm", "권한"))), mode="merge"))

    store = cat_store.load_categories()
    holders = [g.group_id for g in store.groups for c in g.categories if c.category_id == "perm"]
    assert holders == ["docs"]


# ── 전체 교체 ────────────────────────────────────────────────────────────────


def test_replace_shows_what_disappears_before_it_happens():
    """replace 의 위험은 '추가'가 아니라 '삭제'다. 반영 전에 전부 보여준다."""
    _seed(_existing())
    result = category_import.preview(category_import.ImportRequest(
        content=_payload(_group("docs", "문서", _cat("guide", "가이드"))), mode="replace"))

    gone = {row.category_id for row in result.rows if row.status == "gone"}
    assert gone == {"reg", "perm"} and result.counts.gone == 2


def test_preview_does_not_save():
    """미리보기는 계산만 한다. 눌러 보다가 반영되면 확인 절차가 아니다."""
    _seed(_existing())
    category_import.preview(category_import.ImportRequest(
        content=_payload(_group("docs", "문서", _cat("guide", "가이드"))), mode="replace"))

    assert [g.group_id for g in cat_store.load_categories().groups] == ["server"]


def test_preview_and_apply_agree():
    """화면이 '새로 3건'을 보여준 뒤 실제로 다르게 동작하면 확인 절차가 의미를 잃는다."""
    _seed(_existing())
    request = category_import.ImportRequest(
        content=_payload(_group("server", "서버 관리", _cat("reg", "서버 등록(수정)"), _cat("new", "새 항목"))),
        mode="merge")

    shown = category_import.preview(request).counts
    done = category_import.apply(request).counts
    assert (shown.new, shown.over, shown.gone) == (done.new, done.over, done.gone) == (1, 1, 0)


# ── 자주 찾는 주제 ───────────────────────────────────────────────────────────


def test_quick_ids_survive_a_merge():
    """카테고리를 늘리려고 올린 파일이 챗봇 첫 화면의 칩을 비우면 안 된다."""
    _seed(_existing(), quick=["reg"])
    category_import.apply(category_import.ImportRequest(
        content=_payload(_group("docs", "문서", _cat("guide", "가이드"))), mode="merge"))

    assert cat_store.load_categories().quick_category_ids == ["reg"]


def test_quick_ids_drop_categories_that_no_longer_exist():
    """죽은 칩이 인트로에 남으면 눌러도 아무 일이 없다."""
    _seed(_existing(), quick=["reg", "perm"])
    category_import.apply(category_import.ImportRequest(
        content=_payload(_group("docs", "문서", _cat("guide", "가이드"))), mode="replace"))

    assert cat_store.load_categories().quick_category_ids == []


def test_quick_ids_stay_within_the_limit():
    _seed(_existing())
    many = [_cat(f"c{i}", f"이름{i}") for i in range(10)]
    category_import.apply(category_import.ImportRequest(
        content=_payload(_group("g", "대분류", *many), quick=[f"c{i}" for i in range(10)]),
        mode="replace"))

    assert len(cat_store.load_categories().quick_category_ids) == cat_store.QUICK_LIMIT


# ── API ──────────────────────────────────────────────────────────────────────


def test_endpoints_need_admin():
    body = {"content": _payload(_group("g", "대분류", _cat("c", "이름"))), "mode": "merge"}
    assert _client().post("/api/admin/categories/import", json=body).status_code == 401


def test_api_reports_a_broken_file_as_400_with_the_reason():
    response = _client().post("/api/admin/categories/import/preview", auth=AUTH,
                              json={"content": "{", "mode": "merge"})

    assert response.status_code == 400
    assert "JSON 형식이 아닙니다" in response.json()["detail"]


def test_api_round_trip():
    _seed(_existing())
    body = {"content": _payload(_group("docs", "문서", _cat("guide", "가이드", ["질문?"]))), "mode": "merge"}
    client = _client()

    shown = client.post("/api/admin/categories/import/preview", auth=AUTH, json=body).json()
    assert shown["counts"]["new"] == 2 and shown["categories"] == 3

    saved = client.post("/api/admin/categories/import", auth=AUTH, json=body).json()
    assert saved["counts"]["new"] == 2
    # 저장 뒤 조회가 같은 것을 보여줘야 한다 — 파일이 원본이고 화면은 그것을 읽는다.
    listed = client.get("/api/admin/categories", auth=AUTH).json()
    assert {c["category_id"] for g in listed["groups"] for c in g["categories"]} == {"reg", "perm", "guide"}
