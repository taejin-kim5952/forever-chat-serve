"""프로젝트 — 한 설치가 여러 도메인을 담는다 (API Link · API Manager · MCP).

여기서 지키는 것은 기능이 아니라 **경계**다. 프로젝트가 섞이면 틀려도 예외가 안 나고
"가끔 엉뚱한 답이 나온다"로만 드러나서, 한참 뒤에 사용자가 발견한다.

- 프로젝트를 고르면 그 프로젝트의 문서·카테고리·QA만 본다
- 없는 프로젝트를 주면 **막는다.** 조용히 기본값으로 떨어뜨리면 오타 하나로 남의 자료를 고친다
- 프로젝트를 안 고른 요청(= 단일 팩 설치)은 **예전과 똑같이** 동작한다
- 만들기·지우기는 studio 전용이다. 운영은 만들어진 폴더를 복사받는 쪽이다
"""

import base64

import pytest
from fastapi.testclient import TestClient

from app.core import config, projects
from app.main import app

AUTH = {"Authorization": "Basic " + base64.b64encode(b"tester:secret").decode()}

DOC = """---
title: {title}
---

# {title}

## 절

{title} 에 대한 내용입니다. 검색에 걸릴 만큼 충분히 긴 문장을 넣어 둡니다.
"""


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def studio(monkeypatch):
    monkeypatch.setattr("app.api.admin_projects.is_studio", lambda: True)
    monkeypatch.setattr("app.api.admin_docs.is_studio", lambda: True)


def make_project(client, project_id: str, name: str = "") -> dict:
    return client.post("/api/admin/projects", headers=AUTH,
                       json={"project_id": project_id, "name": name or project_id}).json()


def upload(client, project_id: str, title: str):
    body = DOC.format(title=title).encode("utf-8")
    return client.post(
        f"/api/admin/docs/upload?project={project_id}", headers=AUTH,
        files=[("files", (f"{title}.md", body, "text/markdown"))],
        data={"paths": f"{title}.md"},
    )


# ── 만들기 ───────────────────────────────────────────────────────────────────


def test_a_new_project_starts_empty_but_usable(client, studio, isolated_data):
    """만들면 **뼈대뿐**이다. 문서와 카테고리는 사람이 채운다."""
    created = make_project(client, "api-link", "API Link 도우미")

    assert created["project_id"] == "api-link"
    assert created["doc_count"] == 0 and created["qa_count"] == 0
    # 카테고리 파일이 함께 생겨야 한다 — 없으면 첫 저장이 경로를 만들다 실패한다.
    assert client.get("/api/categories?project=api-link").json()["groups"] == []


@pytest.mark.parametrize("bad", ["api link", "한글", "", "-", "a" * 41])
def test_bad_ids_are_refused(client, studio, isolated_data, bad):
    """id 는 폴더 이름이자 주소 조각이다. 공백·대문자·한글이 섞이면 반입과 프록시에서 깨진다."""
    response = client.post("/api/admin/projects", headers=AUTH, json={"project_id": bad})

    assert response.status_code == 400
    assert "프로젝트 ID" in response.json()["detail"]


def test_uppercase_is_normalised_not_refused(client, studio, isolated_data):
    """`API-Link` 라고 적어도 받아 준다. 폴더는 소문자로 만든다 — 리눅스에서 대소문자가
    다른 두 폴더가 생기면 반입할 때 어느 쪽이 진짜인지 알 수 없다."""
    created = make_project(client, "API-Link")

    assert created["project_id"] == "api-link"


def test_duplicate_id_is_refused(client, studio, isolated_data):
    make_project(client, "api-link")

    response = client.post("/api/admin/projects", headers=AUTH, json={"project_id": "api-link"})

    assert response.status_code == 400
    assert "이미 있는" in response.json()["detail"]


def test_serve_mode_cannot_create_or_delete(client, isolated_data):
    """운영은 만들어진 폴더를 복사받는 쪽이다. 빈 프로젝트가 사용자 선택지에 뜨면 안 된다."""
    assert client.post("/api/admin/projects", headers=AUTH,
                       json={"project_id": "api-link"}).status_code == 403
    assert client.delete("/api/admin/projects/x?confirm=x", headers=AUTH).status_code == 403


def test_listing_needs_admin(client, isolated_data):
    assert client.get("/api/admin/projects").status_code == 401


# ── 섞이지 않는다 ────────────────────────────────────────────────────────────


def test_documents_do_not_leak_between_projects(client, studio, isolated_data):
    """이 기능의 전부다. 섞이면 사용자가 다른 도메인의 답을 받는다."""
    make_project(client, "api-link")
    make_project(client, "mcp")
    upload(client, "api-link", "연동 신청")
    upload(client, "mcp", "서버 등록")

    link = client.get("/api/admin/docs?project=api-link", headers=AUTH).json()
    mcp = client.get("/api/admin/docs?project=mcp", headers=AUTH).json()

    assert [d["doc_id"] for d in link] == ["연동 신청"]
    assert [d["doc_id"] for d in mcp] == ["서버 등록"]


def test_the_same_question_finds_each_project_own_documents(client, studio, isolated_data):
    """검색(벡터)까지 갈려 있어야 한다. 파일만 나누고 인덱스를 공유하면 답이 섞인다."""
    make_project(client, "api-link")
    make_project(client, "mcp")
    upload(client, "api-link", "연동 신청")
    upload(client, "mcp", "서버 등록")

    link = client.post("/api/ask?project=api-link", json={"question": "연동 신청 방법"}).json()
    mcp = client.post("/api/ask?project=mcp", json={"question": "연동 신청 방법"}).json()

    # 한 문서가 절 단위로 여러 번 걸릴 수 있다. 보는 것은 **어느 프로젝트의 문서인가**다.
    assert {d["doc_id"] for d in link["related_docs"]} == {"연동 신청"}
    assert {d["doc_id"] for d in mcp["related_docs"]} == {"서버 등록"}


def test_categories_are_per_project(client, studio, isolated_data):
    make_project(client, "api-link")
    make_project(client, "mcp")
    client.post("/api/admin/categories/import?project=api-link", headers=AUTH, json={
        "content": '{"groups":[{"group_id":"g","group_name":"연동","categories":'
                   '[{"category_id":"c1","name":"신청"}]}]}',
        "mode": "replace",
    })

    link = client.get("/api/categories?project=api-link").json()
    mcp = client.get("/api/categories?project=mcp").json()

    assert [c["category_id"] for g in link["groups"] for c in g["categories"]] == ["c1"]
    assert mcp["groups"] == []


def test_the_header_works_as_well_as_the_query(client, studio, isolated_data):
    """화면은 헤더로, 스크립트는 쿼리로 보낸다 — 둘이 같은 곳을 가리켜야 한다."""
    make_project(client, "api-link")
    upload(client, "api-link", "연동 신청")

    by_header = client.get("/api/admin/docs", headers={**AUTH, "X-Project": "api-link"}).json()

    assert [d["doc_id"] for d in by_header] == ["연동 신청"]


# ── 막는다 ───────────────────────────────────────────────────────────────────


def test_unknown_project_is_refused_not_silently_replaced(client, isolated_data):
    """조용히 기본 프로젝트로 떨어뜨리면 오타 하나로 남의 문서를 지운다."""
    response = client.get("/api/admin/docs?project=없는것", headers=AUTH)

    assert response.status_code == 400
    assert "없는 프로젝트입니다" in response.json()["detail"]


def test_delete_needs_the_id_typed_again(client, studio, isolated_data):
    """되돌리기가 없는 작업이다. 화면의 확인 창만 믿지 않고 서버가 한 번 더 맞춰 본다."""
    make_project(client, "api-link")

    assert client.delete("/api/admin/projects/api-link", headers=AUTH).status_code == 400
    assert projects.exists("api-link"), "확인 없이 지워졌습니다"

    assert client.delete("/api/admin/projects/api-link?confirm=api-link",
                         headers=AUTH).status_code == 200
    assert not projects.exists("api-link")


# ── 단일 설치 호환 ───────────────────────────────────────────────────────────


def test_an_installation_without_projects_behaves_as_before(client, isolated_data):
    """`PACK_DIR` 로 띄운 기존 설치(지금 운영)는 프로젝트를 모른다. 그대로 돌아야 한다."""
    assert projects.list_projects() == []
    assert projects.default_project() == ""

    assert client.get("/api/categories").status_code == 200
    # 프로젝트를 고르지 않았으므로 설정이 예전 경로 그대로여야 한다.
    assert config.get_settings().qa_index_file == isolated_data.qa_index_file


def test_project_settings_never_escape_the_test_sandbox(isolated_data):
    """프로젝트 설정이 `.env` 를 다시 읽으면 테스트가 실제 `packs/`·`var/` 를 건드린다.

    2026-08-17 에 테스트가 운영 데이터를 덮은 적이 있어서, 이쪽은 값이 아니라 **경로**를 본다.
    """
    scoped = config.settings_for("api-link")

    assert str(isolated_data.projects_dir) in scoped.pack_dir
    assert str(isolated_data.projects_var_dir) in scoped.var_dir
    assert scoped.admin_password == isolated_data.admin_password, "격리된 설정을 물려받지 못했습니다"


# ── 추천 질문 ──────────────────────────────────────────────────────────────


def test_questions_live_on_the_project_not_in_a_category(client, studio, isolated_data):
    """추천 질문은 **프로젝트에 직접** 적는다.

    전에는 카테고리 안에만 있었다. 질문 몇 개를 띄우려고 분류 체계부터 만들어야 했는데,
    추천 질문은 '이 프로젝트에 뭘 물어볼 수 있나' 를 보여주는 것이라 분류와 상관이 없다.
    """
    make_project(client, "api-link", "API Link")

    saved = client.put("/api/admin/projects/api-link", headers=AUTH,
                       json={"questions": ["API Link 가 뭔가요", "   ", "어떻게 신청하나요"]})

    assert saved.status_code == 200
    # 빈 줄은 버린다. 화면이 입력칸을 더해 두고 안 채우는 일이 흔한데, 그대로 저장하면
    # 사용자 화면에 빈 항목이 뜬다.
    assert saved.json()["questions"] == ["API Link 가 뭔가요", "어떻게 신청하나요"]


def test_not_sending_questions_leaves_them_alone(client, studio, isolated_data):
    """이름만 고칠 때 질문이 지워지면 안 된다.

    `None`(안 보냄)과 `[]`(전부 지움)은 다르다. 섞으면 지우는 방법이 없어지거나, 다른 값을
    고칠 때마다 질문이 사라진다.
    """
    make_project(client, "api-link", "API Link")
    client.put("/api/admin/projects/api-link", headers=AUTH, json={"questions": ["질문"]})

    client.put("/api/admin/projects/api-link", headers=AUTH, json={"name": "API Link 포털"})
    assert client.get("/api/admin/projects", headers=AUTH).json()["items"][0]["questions"] == ["질문"]

    client.put("/api/admin/projects/api-link", headers=AUTH, json={"questions": []})
    assert client.get("/api/admin/projects", headers=AUTH).json()["items"][0]["questions"] == []


def test_the_user_screen_shows_the_project_questions(client, studio, isolated_data):
    """사용자 화면(입력칸 드롭다운)이 그 목록을 받아야 한다."""
    make_project(client, "api-link", "API Link")
    client.put("/api/admin/projects/api-link", headers=AUTH,
               json={"questions": ["API Link 가 뭔가요"]})

    drive = client.get("/api/drive").json()
    mine = [p for p in drive["projects"] if p["project_id"] == "api-link"][0]

    assert mine["questions"] == ["API Link 가 뭔가요"]


def test_changing_the_role_actually_saves(client, studio, isolated_data):
    """용도(지식/자료실)가 저장돼야 한다.

    요청 모델에는 `role` 이 있는데 서비스로 **넘기지 않고 있었다** — 화면에서 바꿔도
    저장되지 않았고 오류도 나지 않았다(2026-10-07). 사용자 화면의 메뉴가 이것으로 갈린다.
    """
    make_project(client, "forms", "자료실")

    saved = client.put("/api/admin/projects/forms", headers=AUTH, json={"role": "library"})

    assert saved.json()["role"] == "library"
    assert client.get("/api/admin/projects", headers=AUTH).json()["items"][0]["role"] == "library"
