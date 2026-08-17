"""API 계층 — 인증과 모드 게이팅이 실제로 막는지 확인한다.

`/admin` 이 인증 없이 열려 있던 적이 있고, 그 서버는 인터넷에 노출돼 있었다.
"막았다고 생각했는데 안 막혀 있었다"를 코드가 아니라 테스트로 확인한다.
"""

import base64
from pathlib import Path

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


def test_admin_page_is_a_shell_without_data(client):
    """관리자 HTML 자체는 인증 없이 내려간다.

    로그인 모달이 그 페이지 안에 있어서, 페이지를 막으면 로그인할 화면도 막힌다.
    대신 **데이터는 한 줄도 실려 있지 않다** — 전부 인증 걸린 API 에서 가져온다.
    """
    response = client.get("/admin")

    assert response.status_code == 200
    assert client.get("/api/admin/qa").status_code == 401


def test_unauthorized_response_has_no_basic_challenge(client):
    """브라우저 기본 로그인 창이 뜨면 우리 로그인 모달과 두 개가 겹친다."""
    response = client.get("/api/admin/qa")

    assert response.status_code == 401
    assert "WWW-Authenticate" not in response.headers


def test_removed_review_page_is_gone(client):
    """`/admin/review` 임시 화면은 2026-08-16 에 걷어냈다.

    검수는 관리자 화면의 `검수` 항목이 맡는다. 라우트가 되살아나면 편집 폼이 두 벌이 되어
    한쪽만 고쳐지는 상태로 돌아간다 — 그래서 사라진 것을 테스트로 붙잡아 둔다.
    """
    assert client.get("/admin/review").status_code == 404


def test_approval_is_guarded_by_the_api_not_the_screen(client):
    """화면은 껍데기만 내려간다. 승인 권한은 `/api/admin/qa` 가 지킨다."""
    assert client.get("/admin").status_code == 200
    assert client.post("/api/admin/qa", json={"question": "질문"}).status_code == 401


def test_wrong_password_is_rejected(client):
    token = base64.b64encode(b"tester:wrong").decode()
    assert client.get("/api/admin/mode", headers={"Authorization": f"Basic {token}"}).status_code == 401


def test_correct_credentials_pass(client, auth):
    assert client.get("/api/admin/mode", headers=auth).status_code == 200


def test_chat_endpoints_are_public(client):
    assert client.get("/api/categories").status_code == 200
    assert client.get("/health").status_code == 200


# ─────────────────────────────────────────────────────────── 모드 게이팅


def test_mode_reports_runtime_models_for_the_screen(client, auth, monkeypatch, isolated_data):
    """설정 화면이 '지금 무엇이 쓰이는지'를 읽는 곳.

    역할별 모델은 비어 있을 수 있고 그때는 `OLLAMA_LLM_MODEL` 이 쓰인다. 그 대체를 화면이
    다시 계산하면 서버와 어긋나므로 여기서 마쳐서 내려보낸다.
    """
    settings = isolated_data
    monkeypatch.setattr(settings, "app_mode", "studio")
    monkeypatch.setattr(settings, "ollama_question_model", "")      # 비면 llm_model 로 대체
    monkeypatch.setattr(settings, "ollama_answer_model", "big-model")
    monkeypatch.setattr(settings, "ollama_judge_model", "")         # 비면 '채점 안 함'

    body = client.get("/api/admin/mode", headers=auth).json()

    assert body["question_model"] == settings.ollama_llm_model
    assert body["answer_model"] == "big-model"
    # 채점 모델만은 대체하지 않는다 — 비어 있는 것이 '채점 안 함'이라는 뜻이다.
    assert body["judge_model"] is None
    assert body["num_ctx"] == settings.ollama_num_ctx


def test_serve_mode_hides_llm_settings(client, auth):
    """운영에는 LLM이 없다. 모델 이름이 내려가면 화면이 없는 기능을 보여준다."""
    body = client.get("/api/admin/mode", headers=auth).json()

    assert body["llm_model"] is None
    assert body["question_model"] is None
    assert body["num_ctx"] == 0
    # 임베딩은 운영에서도 돈다 — 질문을 벡터로 만들어야 검색이 된다.
    assert body["embed_model"]
    # 문서 길이 기준도 임베딩 쪽 값이라 운영에서도 내려간다(⑤ 문서 작성 안내가 읽는다).
    assert body["embed_warn_chars"] > 0


def test_reindex_works_after_the_embedding_model_changed(client, auth, isolated_data, monkeypatch):
    """모델을 바꾼 뒤에도 재색인이 **되어야** 한다.

    컬렉션은 어떤 모델로 색인했는지 적어 두고 다르면 예외를 낸다. 그런데 그 검사가 재색인
    경로까지 막으면, "재색인하세요"라는 오류를 내면서 재색인은 못 하는 상태가 된다 —
    실제로 Ollama 에서 ONNX 로 옮길 때 여기서 막혔다.
    """
    qa_store.upsert_item(qa_store.QaItem(
        qa_id="qa_1", question="API 등록은 어떻게 하나요?", answer="답변", status="approved"))
    QaIndex().upsert_item(qa_store.get_item("qa_1"))

    # 모델을 바꾼 상황을 만든다(폴더 이름이 곧 색인 주체다).
    monkeypatch.setattr(isolated_data, "embed_onnx_dir", str(Path(isolated_data.embed_onnx_dir).parent / "다른-모델"))
    from app.ingestion import vector_store
    vector_store.reset_client()

    # 검색 경로는 막혀야 한다 — 어긋난 벡터로 답하느니 멈추는 편이 낫다.
    with pytest.raises(vector_store.EmbedModelMismatch):
        QaIndex()

    # 그러나 재색인은 되어야 한다.
    assert client.post("/api/admin/qa/reindex", headers=auth).status_code == 200
    assert QaIndex().count() > 0


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


def test_saving_keeps_which_model_made_the_draft(client, auth):
    """검수자가 문구를 고쳐 저장해도 '어느 모델이 만든 초안인지'는 남아야 한다.

    저장 요청(QaSaveRequest)에는 model_used 가 없다. 저장할 때마다 잃는 값이라
    화면을 고쳐도 되돌릴 수 없어서 저장소가 지킨다.
    """
    item = qa_store.upsert_item(qa_store.QaItem(
        qa_id="qa_ai", question="원래 질문", answer="초안", status="pending",
        created_by="ai", model_used="gemma4:latest"))

    client.post("/api/admin/qa", json={
        "qa_id": item.qa_id, "question": "다듬은 질문", "answer": "다듬은 답변",
        "status": "approved", "created_by": "ai",
    }, headers=auth)

    saved = qa_store.get_item("qa_ai")
    assert saved.model_used == "gemma4:latest"
    assert saved.question == "다듬은 질문"


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
