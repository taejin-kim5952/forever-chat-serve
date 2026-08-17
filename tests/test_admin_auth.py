"""세션 로그인 — 화면의 로그인 모달(`#authModal`)이 실제로 동작하는지.

여기서 지키려는 것 세 가지다.

1. **로그인해야 데이터가 나온다.** 화면 껍데기는 열려도 API 는 막혀 있어야 한다.
2. **스크립트가 계속 동작한다.** 배포·점검 절차가 `curl -u` 로 적혀 있어 Basic 인증을
   걷어내면 손과 문서가 전부 어긋난다. 두 방식이 함께 살아 있어야 한다.
3. **비밀번호를 계속 찔러 볼 수 없다.** 화면이 5회 잠금을 하지만 화면 코드는 건너뛸 수 있다.
"""

import base64

import pytest
from fastapi.testclient import TestClient

from app.api import admin_auth
from app.core import session
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_lockout():
    """실패 기록은 모듈 전역이라 테스트끼리 샌다."""
    admin_auth._failures.clear()
    yield
    admin_auth._failures.clear()


def login(client, username="tester", password="secret"):
    return client.post("/api/admin/login", json={"username": username, "password": password})


# ─────────────────────────────────────────────────────────── 로그인


def test_login_sets_session_cookie(client):
    response = login(client)

    assert response.status_code == 200
    assert response.json()["username"] == "tester"
    cookie = client.cookies.get("admin_session")
    assert cookie
    # 토큰은 서명돼 있어야 한다 — 사용자가 아이디를 바꿔 넣을 수 있으면 안 된다.
    assert session.verify(cookie) == "tester"


def test_session_cookie_opens_admin_api(client):
    assert client.get("/api/admin/qa").status_code == 401

    login(client)

    assert client.get("/api/admin/qa").status_code == 200


def test_wrong_password_is_rejected(client):
    response = login(client, password="틀린비밀번호")

    assert response.status_code == 401
    # 아이디가 없는 건지 비밀번호가 틀린 건지 알려주면 계정을 하나씩 확인할 수 있다.
    assert response.json()["detail"] == "아이디 또는 비밀번호가 올바르지 않습니다."
    assert client.get("/api/admin/qa").status_code == 401


def test_unknown_user_gets_the_same_message(client):
    wrong_id = login(client, username="없는사람", password="secret").json()["detail"]
    wrong_pw = login(client, password="틀림").json()["detail"]

    assert wrong_id == wrong_pw


def test_logout_clears_the_session(client):
    login(client)
    assert client.get("/api/admin/qa").status_code == 200

    client.post("/api/admin/logout")

    assert client.get("/api/admin/qa").status_code == 401


def test_logout_works_without_being_logged_in(client):
    """세션이 이미 만료된 상태에서 눌러도 쿠키는 지워져야 한다."""
    assert client.post("/api/admin/logout").status_code == 200


# ─────────────────────────────────────────────────────────── 세션 조회


def test_session_endpoint_is_public(client):
    body = client.get("/api/admin/session").json()

    assert body["authenticated"] is False
    assert body["username"] is None
    # 로그인 전에도 모드를 알아야 화면이 studio 전용 탭을 미리 정리한다.
    assert body["mode"] == "serve"


def test_session_endpoint_reports_login(client):
    login(client)

    body = client.get("/api/admin/session").json()

    assert body["authenticated"] is True
    assert body["username"] == "tester"


# ─────────────────────────────────────────────────────────── 위조·만료


def test_tampered_cookie_is_rejected(client):
    login(client)
    token = client.cookies.get("admin_session")
    body, _, signature = token.partition(".")
    client.cookies.set("admin_session", body[:-2] + "XX." + signature)

    assert client.get("/api/admin/qa").status_code == 401


def test_expired_cookie_is_rejected(client):
    expired, _ = session.issue("tester", ttl_seconds=-1)

    assert session.verify(expired) is None


# ─────────────────────────────────────────────────────────── Basic 인증 병행


def test_basic_auth_still_works(client):
    """`curl -u admin:비밀번호 ... /reindex` 같은 절차가 문서에 그대로 적혀 있다."""
    token = base64.b64encode(b"tester:secret").decode()

    response = client.get("/api/admin/qa", headers={"Authorization": f"Basic {token}"})

    assert response.status_code == 200


def test_basic_auth_with_wrong_password_fails(client):
    token = base64.b64encode(b"tester:wrong").decode()

    assert client.get("/api/admin/qa", headers={"Authorization": f"Basic {token}"}).status_code == 401


# ─────────────────────────────────────────────────────────── 무차별 대입


def test_repeated_failures_lock_out(client):
    for _ in range(admin_auth._MAX_FAILURES):
        assert login(client, password="틀림").status_code == 401

    locked = login(client, password="틀림")

    assert locked.status_code == 429
    assert "Retry-After" in locked.headers
    # 잠긴 동안에는 맞는 비밀번호도 받지 않는다. 안 그러면 잠금이 의미가 없다.
    assert login(client).status_code == 429


def test_successful_login_clears_failure_count(client):
    for _ in range(admin_auth._MAX_FAILURES - 1):
        login(client, password="틀림")

    assert login(client).status_code == 200

    # 성공했으므로 실패 기록이 비워져 있어야 한다 — 다음 오타 한 번에 잠기면 안 된다.
    for _ in range(admin_auth._MAX_FAILURES - 1):
        assert login(client, password="틀림").status_code == 401
