"""API 계층 — 인증과 모드 게이팅이 실제로 막는지 확인한다.

`/admin` 이 인증 없이 열려 있던 적이 있고, 그 서버는 인터넷에 노출돼 있었다.
"막았다고 생각했는데 안 막혀 있었다"를 코드가 아니라 테스트로 확인한다.
"""

import base64

import pytest
from fastapi.testclient import TestClient

from app.core.categories import Category, CategoryGroup, CategoryStore, save_categories
from app.core.runtime_config import RuntimeConfig, save_runtime_config
from app.main import app
from app.qa import store as qa_store
from app.qa.index import QaIndex


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth():
    token = base64.b64encode(b"tester:secret").decode()
    return {"Authorization": f"Basic {token}"}


# ─────────────────────────────────────────────────────────── 인증


@pytest.mark.parametrize("path", [
    "/api/admin/qa", "/api/admin/docs", "/api/admin/questions",
    "/api/admin/settings", "/api/admin/mode", "/api/admin/categories",
])
def test_admin_endpoints_require_auth(client, path):
    assert client.get(path).status_code == 401


def test_admin_page_requires_auth(client):
    response = client.get("/admin")
    assert response.status_code == 401
    # 이 헤더가 없으면 브라우저가 로그인 창을 띄우지 않는다.
    assert "Basic" in response.headers.get("WWW-Authenticate", "")


def test_wrong_password_is_rejected(client):
    token = base64.b64encode(b"tester:wrong").decode()
    assert client.get("/api/admin/mode", headers={"Authorization": f"Basic {token}"}).status_code == 401


def test_correct_credentials_pass(client, auth):
    assert client.get("/api/admin/mode", headers=auth).status_code == 200


def test_chat_endpoints_are_public(client):
    assert client.get("/api/categories").status_code == 200
    assert client.get("/health").status_code == 200


# ─────────────────────────────────────────────────────────── 모드 게이팅


def test_serve_mode_blocks_doc_editing(client, auth):
    response = client.post("/api/admin/docs", json={"doc_id": "새문서", "content": "# 제목"}, headers=auth)
    assert response.status_code == 403


def test_studio_mode_allows_doc_editing(client, auth, monkeypatch, isolated_data):
    monkeypatch.setattr("app.api.admin_docs.is_studio", lambda: True)
    response = client.post("/api/admin/docs", json={"doc_id": "새문서", "content": "# 제목\n\n## 절\n\n내용"}, headers=auth)
    assert response.status_code == 200


def test_mode_endpoint_reports_current_mode(client, auth):
    body = client.get("/api/admin/mode", headers=auth).json()
    assert body["mode"] == "serve"
    # serve 에서는 LLM을 올리지 않으므로 모델 이름을 노출하지 않는다.
    assert body["llm_model"] is None


# ─────────────────────────────────────────────────────────── QA 관리


def test_cannot_approve_empty_answer(client, auth):
    response = client.post(
        "/api/admin/qa",
        json={"question": "질문", "answer": "   ", "status": "approved"},
        headers=auth,
    )
    assert response.status_code == 400


def test_save_and_list_qa(client, auth):
    saved = client.post(
        "/api/admin/qa",
        json={"question": "API 등록은 어떻게 하나요?", "answer": "등록 화면에서 진행합니다.",
              "variants": ["API 등록 절차"], "status": "approved"},
        headers=auth,
    ).json()
    assert saved["vectors"] == 2   # 대표 질문 + 변형 1

    page = client.get("/api/admin/qa", headers=auth).json()
    assert page["total"] == 1
    assert page["summary"]["approved"] == 1
    # 목록에 답변 전문을 싣지 않는다 — 미리보기만 준다.
    assert "answer" not in page["items"][0]
    assert page["items"][0]["answer_preview"]


def test_bulk_disable_removes_from_index(client, auth):
    item = qa_store.upsert_item(qa_store.QaItem(
        qa_id=qa_store.new_qa_id(), question="질문", answer="답변", status="approved"))
    QaIndex().upsert_item(item)
    assert QaIndex().count() == 1

    client.post("/api/admin/qa/bulk", json={"qa_ids": [item.qa_id], "action": "disable"}, headers=auth)

    assert QaIndex().count() == 0


def test_reindex_rebuilds_from_file(client, auth):
    qa_store.upsert_item(qa_store.QaItem(
        qa_id=qa_store.new_qa_id(), question="질문", answer="답변", status="approved"))
    assert QaIndex().count() == 0   # 파일에만 있고 색인은 비어 있는 상태

    result = client.post("/api/admin/qa/reindex", headers=auth).json()

    assert result["items"] == 1
    assert result["vectors"] == 1


# ─────────────────────────────────────────────────────────── 설정 · 카테고리


def test_settings_reject_inverted_thresholds(client, auth):
    response = client.put(
        "/api/admin/settings",
        json={"qa_match_threshold": 0.5, "related_docs_floor": 0.8,
              "related_docs_count": 3, "qa_top_k": 10, "doc_top_k": 10},
        headers=auth,
    )
    assert response.status_code == 400


def test_settings_round_trip(client, auth):
    payload = {"qa_match_threshold": 0.88, "related_docs_floor": 0.5,
               "related_docs_count": 2, "qa_top_k": 8, "doc_top_k": 8}
    client.put("/api/admin/settings", json=payload, headers=auth)
    assert client.get("/api/admin/settings", headers=auth).json() == payload


def test_chat_categories_hide_disabled(client):
    save_categories(CategoryStore(
        groups=[CategoryGroup(group_id="g1", group_name="그룹", categories=[
            Category(category_id="c1", name="보이는 주제", group_id="g1"),
            Category(category_id="c2", name="숨긴 주제", group_id="g1", enabled=False),
        ])],
        quick_category_ids=["c1", "c2"],
    ))

    body = client.get("/api/categories").json()

    names = [c["name"] for c in body["groups"][0]["categories"]]
    assert names == ["보이는 주제"]
    # 미사용 카테고리가 인트로 칩으로 남으면 눌러도 아무 일도 안 일어난다.
    assert body["quick_category_ids"] == ["c1"]


def test_duplicate_category_id_is_rejected(client, auth):
    payload = {
        "groups": [{"group_id": "g1", "group_name": "그룹", "sort": 0, "enabled": True, "categories": [
            {"category_id": "dup", "name": "A", "group_id": "g1"},
            {"category_id": "dup", "name": "B", "group_id": "g1"},
        ]}],
        "quick_category_ids": [],
    }
    assert client.put("/api/admin/categories", json=payload, headers=auth).status_code == 400


# ─────────────────────────────────────────────────────────── 챗봇


def test_ask_rejects_blank_question(client):
    assert client.post("/api/ask", json={"question": "   "}).status_code == 400


def test_ask_returns_unresolved_when_index_empty(client):
    save_runtime_config(RuntimeConfig(
        qa_match_threshold=0.9, related_docs_floor=0.5,
        related_docs_count=3, qa_top_k=10, doc_top_k=10))

    body = client.post("/api/ask", json={"question": "아무 질문"}).json()

    assert body["result_type"] == "unresolved"
    assert body["ticket_id"]


def test_question_log_csv_export(client, auth):
    client.post("/api/ask", json={"question": "질문 하나"})

    response = client.get("/api/admin/questions/export", headers=auth)

    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    # Excel 이 UTF-8 을 알아보게 하는 BOM
    assert response.text.startswith("﻿")
    assert "질문 하나" in response.text
