"""문서 일괄 삭제 — 목록에서 체크한 것을 한 번에 지우는 경로.

여기서 확인하는 것은 "여러 건이 지워진다"가 아니라 **잘못 지워지지 않는지**, 그리고
**하나가 실패해도 나머지가 지워지는지**다.

- 운영(serve)에서는 지워지면 안 된다. 문서 편집은 스튜디오의 일이다
- 열 건을 골랐는데 세 번째에서 멈추면 무엇이 지워졌는지 사람이 알 수 없다
- 파일과 벡터가 **함께** 사라져야 한다. 벡터만 남으면 목록에 없는 문서가 검색에 걸린다
"""

import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.pipeline.retrieve import get_retriever

DOC = "---\ntitle: 문서 제목\n---\n\n# 제목\n\n## 절\n\n검색에 걸릴 만큼 긴 내용입니다. " * 3


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth():
    token = base64.b64encode(b"tester:secret").decode()
    return {"Authorization": f"Basic {token}"}


@pytest.fixture
def studio(monkeypatch):
    monkeypatch.setattr("app.api.admin_docs.is_studio", lambda: True)


def make_docs(isolated_data, *names: str) -> Path:
    docs_dir = Path(isolated_data.raw_docs_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        (docs_dir / f"{name}.md").write_text(DOC, encoding="utf-8")
    get_retriever().doc_index.ingest_dir(force=True)
    return docs_dir


def delete(client, auth, doc_ids):
    return client.post("/api/admin/docs/bulk-delete", headers=auth, json={"doc_ids": doc_ids})


def test_deletes_the_chosen_documents_only(client, auth, studio, isolated_data):
    docs_dir = make_docs(isolated_data, "문서-하나", "문서-둘", "문서-셋")

    result = delete(client, auth, ["문서-하나", "문서-셋"]).json()

    assert (result["deleted"], result["failed"]) == (2, 0)
    assert sorted(p.stem for p in docs_dir.glob("*.md")) == ["문서-둘"]


def test_vectors_go_with_the_file(client, auth, studio, isolated_data):
    """파일만 지우고 벡터가 남으면 목록에 없는 문서가 검색 결과에 나온다."""
    make_docs(isolated_data, "문서-하나", "문서-둘")
    index = get_retriever().doc_index

    delete(client, auth, ["문서-하나"])

    remaining = {meta.get("doc_id") for meta in index.collection.get(include=["metadatas"])["metadatas"]}
    assert remaining == {"문서-둘"}


def test_one_failure_does_not_stop_the_rest(client, auth, studio, isolated_data):
    """열 건을 골랐는데 중간에서 멈추면 무엇이 지워졌는지 알 수 없다."""
    docs_dir = make_docs(isolated_data, "있는문서")

    result = delete(client, auth, ["없는문서", "있는문서"]).json()

    assert (result["deleted"], result["failed"]) == (1, 1)
    statuses = {item["doc_id"]: item["status"] for item in result["items"]}
    assert statuses == {"없는문서": "failed", "있는문서": "deleted"}
    # 실패한 건은 이유가 함께 온다 — 화면이 그대로 보여 준다.
    assert "찾을 수 없습니다" in [i["reason"] for i in result["items"] if i["status"] == "failed"][0]
    assert not list(docs_dir.glob("*.md"))


def test_duplicate_ids_are_handled_once(client, auth, studio, isolated_data):
    """화면이 같은 id 를 두 번 보내도 '실패 1건'으로 보이면 안 된다."""
    make_docs(isolated_data, "문서-하나")

    result = delete(client, auth, ["문서-하나", "문서-하나"]).json()

    assert (result["deleted"], result["failed"]) == (1, 0)


def test_serve_mode_cannot_delete(client, auth, isolated_data):
    """운영에서는 조회만 한다. 편집 경로가 열려 있으면 모드를 나눈 의미가 없다."""
    docs_dir = make_docs(isolated_data, "문서-하나")

    assert delete(client, auth, ["문서-하나"]).status_code == 403
    assert (docs_dir / "문서-하나.md").exists()


def test_needs_admin(client, isolated_data):
    make_docs(isolated_data, "문서-하나")
    assert client.post("/api/admin/docs/bulk-delete", json={"doc_ids": ["문서-하나"]}).status_code == 401


def test_empty_list_changes_nothing(client, auth, studio, isolated_data):
    docs_dir = make_docs(isolated_data, "문서-하나")

    result = delete(client, auth, []).json()

    assert (result["deleted"], result["failed"], result["items"]) == (0, 0, [])
    assert (docs_dir / "문서-하나.md").exists()
