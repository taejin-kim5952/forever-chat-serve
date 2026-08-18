"""QA 가져오기 (요청서 11).

답변을 **만드는 곳과 답하는 곳이 다르다.** 운영 서버에는 LLM이 없어 QA를 사내 작업 PC에서
만들고 파일로 들여온다. 여기서 지키는 것은 기능보다 **경계**다.

- 파일에 `approved` 라고 적혀 있어도 **검수 대기**로 들어온다
- 덮어써도 운영에서 쌓인 값(적중 횟수·검수 메모·`qa_id`)은 서버 것이 남는다
- 미리보기와 실제 반영이 **같은 판단**을 쓴다 — 다르면 확인 절차가 의미를 잃는다
"""

import json

from fastapi.testclient import TestClient

from app.main import app
from app.qa import importer
from app.qa import store as qa_store

AUTH = ("tester", "secret")


def _client() -> TestClient:
    return TestClient(app)


def _draft(question: str, **kw) -> dict:
    return {"question": question, "answer": "답변입니다.", "variants": ["변형1"], **kw}


def _upload(client: TestClient, payload: object, name: str = "generated_qa.json"):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return client.post("/api/admin/qa/import/preview", auth=AUTH,
                       files={"file": (name, body, "application/json")})


def _server_qa(qa_id: str, question: str, **kw) -> qa_store.QaItem:
    return qa_store.upsert_item(
        qa_store.QaItem(qa_id=qa_id, question=question, answer="서버 답변", status="approved", **kw)
    )


# ── 파일 읽기 ────────────────────────────────────────────────────────────────


def test_reads_both_file_shapes():
    """검수자가 어느 파일을 올릴지 알고 있을 필요가 없어야 한다."""
    drafts = importer.read_items({"drafts": [_draft("초안 질문")]})
    index = importer.read_items({"items": [_draft("인덱스 질문")]})
    bare = importer.read_items([_draft("목록만")])

    assert [i.question for i in drafts + index + bare] == ["초안 질문", "인덱스 질문", "목록만"]


def test_unknown_fields_are_dropped():
    """스튜디오 파일에 필드가 늘어나도 여기서 막히면 안 된다."""
    assert importer.read_items([{"question": "질문", "answer": "답", "미래필드": 1}])[0].question == "질문"


def test_broken_json_gives_a_readable_error():
    """화면이 그대로 사용자에게 보여주는 문구다. 'Internal Server Error' 면 안 된다."""
    response = _client().post("/api/admin/qa/import/preview", auth=AUTH,
                              files={"file": ("x.json", b"{ this is not json", "application/json")})
    assert response.status_code == 400
    assert "JSON" in response.json()["detail"]


def test_utf8_bom_file_is_read():
    """윈도우 편집기가 BOM을 붙여 저장하는 일이 흔하다."""
    body = "﻿" + json.dumps([_draft("질문")], ensure_ascii=False)
    response = _client().post("/api/admin/qa/import/preview", auth=AUTH,
                              files={"file": ("x.json", body.encode("utf-8"), "application/json")})
    assert response.status_code == 200


# ── 미리보기 ─────────────────────────────────────────────────────────────────


def test_preview_marks_new_and_existing():
    client = _client()
    _server_qa("qa_a", "이미 있는 질문")

    items = _upload(client, {"drafts": [_draft("새 질문"), _draft("이미 있는 질문")]}).json()["items"]

    assert [i["status"] for i in items] == ["new", "over"]


def test_preview_carries_answer_and_variants_back():
    """미리보기 항목이 그대로 다시 올라온다. 답변이 빠지면 반영할 내용이 없어진다."""
    item = _upload(_client(), [_draft("질문")]).json()["items"][0]

    assert item["answer"] == "답변입니다."
    assert item["variants"] == ["변형1"]


def test_preview_fills_category_label():
    """화면 표에 그대로 나가는 값이다. 화면이 id로 다시 찾게 하면 목록을 통째로 들고 있어야 한다."""
    from app.core import categories

    categories.save_categories(categories.CategoryStore(groups=[
        categories.CategoryGroup(group_id="auth", group_name="권한", categories=[
            categories.Category(category_id="auth_apply", name="권한 신청", group_id="auth"),
        ]),
    ]))

    items = _upload(_client(), [
        _draft("질문", category_id="auth_apply"),
        _draft("주제 없는 질문"),
    ]).json()["items"]

    assert items[0]["category_label"] == "권한 신청"
    # 주제가 없는 초안도 있다. 화면은 그때 '(주제 없음)' 을 스스로 채운다.
    assert items[1]["category_label"] == ""


def test_existing_is_matched_by_question_not_only_id():
    """스튜디오에서 다시 생성하면 id가 새로 붙는다. 질문이 같으면 같은 항목으로 본다 —
    id만 보면 같은 질문이 두 벌 쌓인다."""
    client = _client()
    _server_qa("qa_old", "API 등록은 어떻게 하나요?")

    items = _upload(client, [_draft("API 등록은 어떻게 하나요?", qa_id="qa_new")]).json()["items"]
    assert items[0]["status"] == "over"


def test_question_matching_ignores_spacing_and_punctuation():
    client = _client()
    _server_qa("qa_a", "API 등록은 어떻게 하나요?")

    items = _upload(client, [_draft("API등록은 어떻게 하나요")]).json()["items"]
    assert items[0]["status"] == "over"


def test_duplicate_inside_the_file_is_caught():
    items = _upload(_client(), [_draft("같은 질문"), _draft("같은 질문")]).json()["items"]

    assert [i["status"] for i in items] == ["new", "skip"]
    assert "두 번" in items[1]["reason"]


def test_empty_question_is_skipped_with_a_reason():
    items = _upload(_client(), [{"question": "  ", "answer": "답"}]).json()["items"]

    assert items[0]["status"] == "skip"
    assert "대표 질문" in items[0]["reason"]


def test_preview_changes_nothing():
    """미리보기는 계산만 한다. 여기서 무언가 저장되면 확인 절차가 아니라 실행이 된다."""
    _upload(_client(), [_draft("새 질문")])
    assert qa_store.load_qa() == []


# ── 실제 반영 ────────────────────────────────────────────────────────────────


def _apply(client: TestClient, items: list[dict], overwrite: bool = False):
    return client.post("/api/admin/qa/import", auth=AUTH,
                       json={"items": items, "overwrite": overwrite}).json()


def test_import_adds_as_pending():
    client = _client()
    result = _apply(client, [_draft("새 질문")])

    assert [r["status"] for r in result["items"]] == ["created"]
    saved = qa_store.load_qa()[0]
    assert saved.status == "pending"
    assert saved.variants == ["변형1"]


def test_approved_in_the_file_still_lands_as_pending():
    """★ 이 제품의 전제 — 검수한 답변만 사용자에게 나간다.

    파일이 `approved` 라고 주장해도 믿지 않는다. 믿으면 파일 한 줄로 검수를 건너뛰는
    경로가 생긴다. `qa_index.json` 을 그대로 올리는 경우가 실제로 이 모양이다.
    """
    client = _client()
    items = _upload(client, {"items": [dict(_draft("승인이라 적힌 질문"), status="approved")]}).json()["items"]

    assert items[0]["status"] == "new", "파일의 status 를 미리보기 상태로 읽으면 안 됩니다"
    _apply(client, items)
    assert qa_store.load_qa()[0].status == "pending"


def test_import_does_not_serve_until_approved():
    _apply(_client(), [_draft("새 질문")])
    assert qa_store.serving_items() == []


def test_overwrite_keeps_hit_count_and_note():
    """덮어써도 운영에서 쌓인 값은 서버 것이 남는다. 적중 횟수는 검수 우선순위의 근거이고,
    검수 메모가 사라지면 다음 사람이 같은 판단을 반복한다."""
    client = _client()
    _server_qa("qa_a", "이미 있는 질문", hit_count=42, note="보류: 문구 확인 필요")

    _apply(client, [_draft("이미 있는 질문", answer="새 답변")], overwrite=True)

    saved = qa_store.load_qa()[0]
    assert saved.answer == "새 답변"
    assert saved.hit_count == 42
    assert saved.note == "보류: 문구 확인 필요"


def test_overwrite_reuses_the_server_qa_id():
    """서버 id를 유지해야 사용자 신고·질문 이력이 계속 이어진다."""
    client = _client()
    _server_qa("qa_server", "이미 있는 질문")

    _apply(client, [_draft("이미 있는 질문", qa_id="qa_studio")], overwrite=True)

    assert [i.qa_id for i in qa_store.load_qa()] == ["qa_server"]


def test_server_refuses_overwrite_even_if_the_screen_asks():
    """화면이 걸러 보내지만 **서버가 다시 판단한다.** 미리보기와 반영 사이에 다른 사람이
    승인했을 수도 있고, 화면을 거치지 않는 경로(scripts/push_qa.py)도 있다."""
    client = _client()
    _server_qa("qa_a", "이미 있는 질문")

    result = _apply(client, [_draft("이미 있는 질문", answer="새 답변")], overwrite=False)

    assert result["items"][0]["status"] == "skipped"
    saved = qa_store.load_qa()[0]
    assert saved.answer == "서버 답변"
    assert saved.status == "approved", "건너뛴 항목의 상태까지 바뀌면 안 됩니다"


def test_duplicate_inside_one_batch_is_applied_once():
    result = _apply(_client(), [_draft("같은 질문"), _draft("같은 질문")])

    assert [r["status"] for r in result["items"]] == ["created", "skipped"]
    assert len(qa_store.load_qa()) == 1


def test_batches_are_independent():
    """화면은 몇 건씩 나눠 부른다. 나눠 보내도 결과가 같아야 한다."""
    client = _client()
    for question in ["질문1", "질문2", "질문3"]:
        _apply(client, [_draft(question)])

    assert sorted(i.question for i in qa_store.load_qa()) == ["질문1", "질문2", "질문3"]


def test_preview_and_apply_agree():
    """화면이 '덮어씀 1건'을 보여준 뒤 실제로는 다르게 동작하면 확인 절차가 의미를 잃는다."""
    client = _client()
    _server_qa("qa_a", "이미 있는 질문")
    payload = [_draft("새 질문"), _draft("이미 있는 질문"), _draft("또 다른 새 질문")]

    preview = _upload(client, payload).json()["items"]
    result = _apply(client, preview, overwrite=True)["items"]

    assert [i["status"] for i in preview] == ["new", "over", "new"]
    assert [r["status"] for r in result] == ["created", "updated", "created"]


# ── 인증 · 모드 ──────────────────────────────────────────────────────────────


def test_import_needs_admin():
    """QA를 밀어 넣는 경로다. 열려 있으면 누구나 검수 대기줄을 채울 수 있다."""
    client = _client()
    assert client.post("/api/admin/qa/import", json={"items": []}).status_code == 401
    assert client.post("/api/admin/qa/import/preview",
                       files={"file": ("x.json", b"[]", "application/json")}).status_code == 401


def test_import_works_in_serve_mode():
    """운영에서 쓰는 기능이다. studio 전용으로 막히면 존재 이유가 없다."""
    from app.core import config

    assert config.get_settings().app_mode == "serve"
    assert _apply(_client(), [_draft("질문")])["items"][0]["status"] == "created"
