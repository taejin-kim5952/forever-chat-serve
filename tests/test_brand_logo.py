"""로고 이미지 — 설치 전체에 하나.

- 올리면 **글자 대신 그림**이 나가고, 지우면 글자로 돌아간다(되돌릴 길이 있어야 한다)
- 로고 자리에 아무 파일이나 올라가면 그건 업로드 기능이지 로고 기능이 아니다
- 주소에 내용 해시가 붙는다 — 안 붙으면 "바꿨는데 안 바뀐다"가 된다
- 팩이 아니라 따로 저장한다. 프로젝트를 바꿔도 회사 로고는 그대로다
"""

import base64
import re

import pytest
from fastapi.testclient import TestClient

from pathlib import Path

from app.main import app

ADMIN_JS = Path(__file__).resolve().parents[1] / "app" / "static" / "admin.js"

AUTH = {"Authorization": "Basic " + base64.b64encode(b"tester:secret").decode()}
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


@pytest.fixture
def client():
    return TestClient(app)


def put_logo(client, name="logo.png", data=PNG):
    return client.post("/api/admin/brand/logo", headers=AUTH,
                       files={"file": (name, data, "application/octet-stream")})


def test_the_admin_screen_does_not_overwrite_the_logo(client, isolated_data):
    """화면이 켜진 뒤 **자바스크립트가 로고를 글자로 덮으면 안 된다.**

    관리자 화면은 프로필을 저장한 뒤 브랜드 문자열을 다시 그린다(`applyBrand`). 그 함수가
    `[data-brand]` 전부에 `.text()` 를 넣는데, 로고 자리에도 `data-brand` 가 붙어 있다 —
    서버가 거기 박아 둔 `<img>` 가 조직 이름 글자로 바뀐다.

    2026-10-07 에 그랬다. **서버는 멀쩡히 `<img>` 를 내려주고 있었고**, 그래서 응답을
    보는 테스트(`test_uploaded_logo_replaces_the_letters_on_both_screens`)는 통과했다.
    화면이 켜진 뒤에 벌어지는 일이라 브라우저로 봐야만 보였다. 사용자 화면은 이 함수가
    없어서 멀쩡했다.
    """
    source = ADMIN_JS.read_text(encoding="utf-8")
    start = source.index("$('[data-brand]').each(")
    # 주석에도 `.text()` 와 `data-brand-logo` 가 적혀 있다. 주석에 걸리면 코드가 틀려도
    # 테스트가 통과하므로, **주석을 걷어내고** 실행되는 줄만 본다.
    lines = [line for line in source[start:start + 2000].splitlines()
             if not line.lstrip().startswith(("/*", "*", "//"))]
    block = chr(10).join(lines)

    guard = [line for line in lines if "data-brand-logo" in line and "return" in line]
    assert guard, (
        "applyBrand 가 로고 자리를 걸러내지 않습니다 — 서버가 박아 둔 <img> 를 "
        "조직 이름 글자로 덮습니다"
    )
    assert block.index(guard[0]) < block.index("$(this).text("), (
        "로고 자리를 거르는 검사가 .text() 보다 뒤에 있습니다"
    )


def test_no_logo_means_the_text_badge_stays(client, isolated_data):
    """로고가 없으면 마크업의 글자가 그대로 쓰인다 — 기존 설치의 모습이다."""
    assert client.get("/api/brand/logo").status_code == 404
    page = client.get("/").text
    assert "data-brand-logo" in page
    # 로고가 없으면 그 자리에 **글자**가 남는다(`data-brand="{organization}"`).
    #
    # 요소의 **안쪽만** 본다. 앞뒤 200자를 뭉뚱그려 보면 옆에 둔 주석이나 다른 요소에
    # 걸려 거짓으로 깨진다(2026-10-07 에 주석 속 태그 이름에 걸렸다).
    inside = re.search(r"<(\w+)[^>]*\sdata-brand-logo[^>]*>(.*?)</\1>", page, re.DOTALL)
    assert inside, "로고 자리를 찾지 못했습니다"
    assert "<img" not in inside.group(2)
    assert inside.group(2).strip(), "로고도 글자도 없이 비어 있습니다"


def test_uploaded_logo_replaces_the_letters_on_both_screens(client, isolated_data):
    put_logo(client)

    for path in ("/", "/admin"):
        page = client.get(path).text
        assert "/api/brand/logo?v=" in page, f"{path} 에 로고가 안 들어갔습니다"


def test_the_url_changes_when_the_image_changes(client, isolated_data):
    """주소가 그대로면 브라우저가 옛 그림을 계속 보여 준다."""
    put_logo(client)
    first = client.get("/").text.split("/api/brand/logo?v=")[1][:8]

    put_logo(client, data=PNG + b"\x00")
    second = client.get("/").text.split("/api/brand/logo?v=")[1][:8]

    assert first != second


def test_only_image_types_are_accepted(client, isolated_data):
    assert put_logo(client, name="logo.exe").status_code == 400
    assert put_logo(client, name="logo.md").status_code == 400


def test_oversize_is_refused_with_the_size_in_the_message(client, isolated_data):
    """몇 KB 까지인지 모르면 사람이 줄여 올 수가 없다."""
    response = put_logo(client, data=b"x" * (1024 * 1024 + 1))

    assert response.status_code == 400
    assert "KB" in response.json()["detail"]


def test_replacing_with_another_format_leaves_one_file(client, isolated_data):
    """옛 파일이 남으면 폴더 훑는 순서가 어느 그림이 나갈지 정한다."""
    from pathlib import Path

    put_logo(client, name="logo.png")
    put_logo(client, name="logo.svg", data=b"<svg xmlns='http://www.w3.org/2000/svg'/>")

    files = sorted(p.name for p in Path(isolated_data.brand_dir).glob("logo.*"))
    assert files == ["logo.svg"]


def test_deleting_returns_to_the_text_badge(client, isolated_data):
    put_logo(client)

    assert client.delete("/api/admin/brand/logo", headers=AUTH).status_code == 200
    assert client.get("/api/brand/logo").status_code == 404
    assert "/api/brand/logo?v=" not in client.get("/").text


def test_upload_needs_admin_but_viewing_does_not(client, isolated_data):
    """로고는 로그인 전에도 보여야 한다 — 로그인 화면에도 로고가 있다."""
    assert client.post("/api/admin/brand/logo",
                       files={"file": ("logo.png", PNG, "image/png")}).status_code == 401

    put_logo(client)
    assert client.get("/api/brand/logo").status_code == 200
