"""관리자 화면 이식본이 서버와 실제로 맞물리는지.

화면은 퍼블 산출물을 옮긴 것이라 **서버가 화면을 모른다.** 경로를 한 글자 틀리면 탭 하나가
조용히 비어 보이고, 브라우저 콘솔을 열기 전까지는 아무도 모른다. 그래서 화면이 부르는
`/api/...` 를 전부 뽑아 서버에 그 경로가 있는지 확인한다.

이 테스트가 잡는 것:
- 퍼블 산출물을 새로 받아 이식하면서 배선을 빠뜨린 경우(더미 그대로 남은 탭)
- 서버 라우터를 옮기거나 이름을 바꿨는데 화면을 못 고친 경우
"""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"
ADMIN_JS = STATIC / "admin.js"

# '/api/admin/qa' 처럼 따옴표 안에 그대로 적힌 경로만 본다.
_URL = re.compile(r"""['"](/api/[^'"?\s]*)""")


@pytest.fixture
def client():
    return TestClient(app)


def route_paths() -> set[str]:
    return {getattr(r, "path", "") for r in app.routes}


def matches_route(url: str, paths: set[str]) -> bool:
    if url in paths:
        return True
    # 화면은 '/api/admin/qa/' + id 처럼 붙여 쓴다. 경로 매개변수 앞부분과 맞춰 본다.
    for path in paths:
        if "{" not in path:
            continue
        prefix = path.split("{", 1)[0]
        if url.rstrip("/") + "/" == prefix or url == prefix.rstrip("/"):
            return True
    return False


def test_every_url_in_admin_js_exists_on_the_server():
    urls = sorted({m.group(1) for m in _URL.finditer(ADMIN_JS.read_text(encoding="utf-8"))})
    assert urls, "화면이 서버를 전혀 부르지 않습니다 — 더미 상태 그대로입니다."

    paths = route_paths()
    missing = [u for u in urls if not matches_route(u, paths)]

    assert not missing, f"화면이 부르는데 서버에 없는 경로: {missing}"


def test_admin_screen_has_no_dummy_data_left():
    """퍼블 산출물의 더미 상수가 남아 있으면 서버 데이터 위에 가짜가 겹쳐 보인다."""
    source = ADMIN_JS.read_text(encoding="utf-8")

    for leftover in ["var Q_SEEDS", "var ANSWER_MD", "function mockSave", "function fakeRun"]:
        assert leftover not in source, f"더미 코드가 남아 있습니다: {leftover}"


def test_screens_load_assets_locally_and_absolutely():
    """퍼블 산출물이 CDN과 상대경로를 쓰고 온다. 둘 다 이 프로젝트에서는 화면을 죽인다.

    - **CDN**: 운영은 폐쇄망이다. jQuery를 못 받으면 화면 전체가 동작하지 않는다.
    - **상대경로**: 이 페이지들은 `/admin` 처럼 하위 경로로 서비스되므로 `admin.js` 는
      `/admin.js` 로 잘못 풀려 404가 난다. 실제로 이식 직후 이 상태였다.
    """
    for name in ["admin.html", "chat.html"]:
        html = (STATIC / name).read_text(encoding="utf-8")
        assets = re.findall(r'(?:src|href)="([^"]+\.(?:js|css))"', html)

        for asset in assets:
            assert not asset.startswith("http"), f"{name}: CDN 자원이 있습니다 — 폐쇄망에서 못 받습니다: {asset}"
            assert asset.startswith("/static/"), f"{name}: 상대경로 자원이 있습니다: {asset}"


def test_admin_page_is_served_with_server_mode(client):
    body = client.get("/admin").text

    # 화면이 켜진 뒤 API로 모드를 물어보면 운영에서 안 되는 탭이 잠깐 보였다 사라진다.
    assert 'data-mode="serve"' in body
    # 로그인 모달이 이 페이지 안에 있어야 한다 — 페이지를 막으면 로그인할 화면도 막힌다.
    assert 'id="authModal"' in body


def test_static_assets_are_served(client):
    for path in ["/static/admin.js", "/static/admin.css", "/static/chat.js", "/static/chat.css"]:
        assert client.get(path).status_code == 200, path


@pytest.mark.parametrize("anchor,closing", [
    ('id="panel_generate"', "</section>"),
    ('id="panel_eval"', "</section>"),
    ('id="subpanel_generation"', "<!-- /#subpanel_generation -->"),
])
def test_screen_controls_are_all_wired_to_the_server(anchor, closing):
    """화면의 입력칸은 전부 `admin.js` 가 읽어야 한다.

    퍼블 산출물에는 1차 프로젝트에서 넘어온 `답 없는 질문 비율`, 역할 분리 전의 `생성 모델`,
    LLM을 쓰지도 않는 평가의 `판정 모델` 이 남아 있었다. 셋 다 서버로 전송되지 않는 값이라
    아무리 바꿔도 결과가 같은데 화면에는 멀쩡히 보인다. 검수자는 그 값을 조절하며 결과가
    달라지기를 기다린다 — **오류보다 나쁘다.** 산출물을 다시 이식할 때 같은 칸이 딸려 오면
    여기서 잡는다.

    고칠 수 없는 값(`.env` 에서 오는 모델·컨텍스트)은 입력칸이 아니라 읽기 전용 표시로 둔다.
    """
    html = (STATIC / "admin.html").read_text(encoding="utf-8")
    js = ADMIN_JS.read_text(encoding="utf-8")

    start = html.index(anchor)
    panel = html[start: html.index(closing, start)]
    controls = re.findall(r'<(?:input|select|textarea)[^>]*\bid="([^"]+)"', panel)

    dead = [c for c in controls if c not in js]
    assert not dead, f"화면에는 있는데 admin.js 가 읽지 않는 입력: {dead}"


def test_state_changing_actions_refresh_the_status_board():
    """무언가를 바꾼 뒤에는 진행 현황도 다시 읽어야 한다.

    초안을 반영했는데 진행 현황 숫자가 그대로여서 새로고침해야 바뀌는 상태였다. 값이 틀린
    화면은 없는 화면보다 나쁘다 — 사람이 그 숫자를 믿고 다음 판단을 한다.

    바꾸는 지점(문서 저장·삭제·폴더 등록·초안 반영)마다 `refreshFlow()` 또는
    `refreshQaAndFlow()` 가 따라붙는지 본다.
    """
    js = ADMIN_JS.read_text(encoding="utf-8")

    for anchor in ["loadDocs().done(renderDocs)",          # 문서 저장·삭제·폴더 등록
                   "/api/studio/generate/apply"]:          # 초안 반영
        for position in [m.start() for m in re.finditer(re.escape(anchor), js)]:
            window = js[position: position + 700]
            assert "refreshFlow()" in window or "refreshQaAndFlow()" in window, (
                f"'{anchor}' 뒤에 진행 현황 갱신이 없습니다"
            )


def test_document_guide_is_reachable_from_the_docs_tab():
    """문서 작성 형식 안내가 이식에서 빠지지 않았는지.

    문서를 만드는 사람이 볼 유일한 안내다. 버튼만 오고 모달이 빠지면 눌러도 아무 일이
    없고, 모달만 오면 열 방법이 없다 — 둘 다 조용히 실패하므로 함께 확인한다.
    """
    html = (STATIC / "admin.html").read_text(encoding="utf-8")
    js = ADMIN_JS.read_text(encoding="utf-8")

    assert 'id="docGuideBtn"' in html
    assert 'id="docGuideModal"' in html
    assert "docGuideBtn" in js
    # 길이 기준은 서버 설정에서 채운다. 화면에 숫자를 박으면 설정과 조용히 어긋난다.
    assert "guideWarnChars" in html and "embed_warn_chars" in js


def test_job_board_markup_and_wiring_are_present():
    """작업 현황판이 이식에서 빠지지 않았는지.

    이 화면은 퍼블 산출물을 갈아 끼울 때마다 다시 옮겨야 한다. 마크업만 오고 배선이 빠지면
    빈 카드가 영영 안 뜨고, 배선만 있고 마크업이 빠지면 아무 일도 안 일어난다 — 둘 다
    조용히 실패하므로 여기서 함께 확인한다.
    """
    html = (STATIC / "admin.html").read_text(encoding="utf-8")
    js = ADMIN_JS.read_text(encoding="utf-8")

    for element in ["flowJob", "flowJobHistory", "flowJobStop", "tpl_job_row", "data-nav-spin"]:
        assert element in html, f"작업 현황판 마크업이 없습니다: {element}"
    # 진행 상태는 서버가 들고 있다. 화면 안에서 만들어 내면 새로고침에 사라진다.
    assert "/api/admin/jobs" in js
    assert "setInterval" in js


def test_feedback_markup_and_wiring_are_present():
    """사용자 피드백(요청서 10)이 이식에서 빠지지 않았는지.

    챗봇에서 버튼만 오고 서버 호출이 빠지면 **누를 수는 있는데 아무 데도 안 남는다** —
    가장 알아채기 어려운 형태의 고장이다. 관리자 쪽은 반대로, 서버가 값을 내려주는데
    화면이 그리지 않으면 신고가 쌓여도 아무도 안 본다. 세 화면을 함께 확인한다.
    """
    chat_html = (STATIC / "chat.html").read_text(encoding="utf-8")
    chat_js = (STATIC / "chat.js").read_text(encoding="utf-8")
    admin_html = (STATIC / "admin.html").read_text(encoding="utf-8")
    admin_js = ADMIN_JS.read_text(encoding="utf-8")

    # 챗봇 — 이유 세 가지는 담당자의 조치를 가르는 값이라 하나라도 빠지면 안 된다.
    for element in ["chat_fb_up", "chat_fb_down", "chat_fb_skip",
                    'data-reason="mismatch"', 'data-reason="wrong"', 'data-reason="thin"']:
        assert element in chat_html, f"챗봇 피드백 마크업이 없습니다: {element}"
    assert "/api/feedback" in chat_js, "👍/👎 가 서버로 가지 않습니다"
    # 어느 응답인지는 log_id 로 잇는다. 없으면 서버가 붙일 곳을 모른다.
    assert "data-log-id" in chat_js

    # 관리자 ① 질문 이력 · ② 검수
    for element in ['data-col="fb"', 'data-fb="down"', 'value="fb_desc"', 'data-ed="feedback"']:
        assert element in admin_html, f"관리자 피드백 마크업이 없습니다: {element}"
    for element in ["fbCell", "renderEdFeedback", "report_count", "feedback="]:
        assert element in admin_js, f"관리자 피드백 배선이 없습니다: {element}"


def test_intro_category_accordion_is_present():
    """인트로의 `전체 주제 보기`(요청서 09).

    예전에는 이 버튼이 화면 맨 아래 팝오버를 열어서 '아무 일도 안 일어난 것'처럼 보였다.
    같은 회귀를 막으려면 인트로 안에 자기 목록이 있어야 한다.
    """
    html = (STATIC / "chat.html").read_text(encoding="utf-8")
    js = (STATIC / "chat.js").read_text(encoding="utf-8")

    assert 'id="chatIntroCats"' in html and 'id="chatIntroCatList"' in html
    assert 'aria-controls="chatIntroCats"' in html, "펼침 상태를 읽을 수 없습니다"
    # 아래 팝오버는 그대로 살아 있어야 한다 — 대화가 시작되면 그쪽만 쓴다.
    assert 'id="chatCatPopover"' in html
    # 목록을 그리는 함수는 하나여야 한다. 두 벌이 되면 한쪽만 고치는 일이 생긴다.
    assert "function buildCatList" in js
    assert "openIntroCats" in js and "closeIntroCats" in js


def test_studio_only_markup_is_present():
    """serve 에서 감춰야 하는 요소가 표시돼 있는지. 없으면 운영에서 동작하지 않는 버튼이 보인다."""
    html = (STATIC / "admin.html").read_text(encoding="utf-8")

    assert "data-studio-only" in html
    assert 'data-tab="generate"' in html and 'data-tab="eval"' in html
