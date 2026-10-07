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
    for name in ["admin.html", "drive.html", "folder-new.html"]:
        html = (STATIC / name).read_text(encoding="utf-8")
        assets = re.findall(r'(?:src|href)="([^"]+\.(?:js|css))"', html)

        for asset in assets:
            assert not asset.startswith("http"), f"{name}: CDN 자원이 있습니다 — 폐쇄망에서 못 받습니다: {asset}"
            assert asset.startswith("/static/"), f"{name}: 상대경로 자원이 있습니다: {asset}"


def test_the_logo_link_is_not_underlined(client):
    """로고를 **안 올린 설치**에서 로고 자리가 파란 밑줄 링크가 되면 안 된다.

    서버는 로고를 올린 설치에서만 그 자리를 `<img>` 로 갈아 끼운다(`app/main.py` 의
    `_apply_logo`). 안 올렸으면 글자가 그대로 남는데, `<a class="logo">` 에
    `text-decoration` 지정이 없으면 브라우저 기본값이 그대로 나온다.

    **개발 PC 에서는 영영 안 보이는 종류다.** 거기에는 `data/brand/logo.svg` 가 있어서
    늘 `<img>` 가 들어가고, 이미지에는 밑줄이 안 그려진다. 2026-10-07 에 개발 서버에
    처음 올리고서야 드러났다 — 기본값이 어떻게 보이는지는 **기본값으로 쓰는 곳**에서만
    알 수 있다.
    """
    for name in ["drive.css", "folder-new.css"]:
        css = (STATIC / name).read_text(encoding="utf-8")
        rule = next((line for line in css.splitlines()
                     if line.strip().startswith(".logo{")), None)
        assert rule, f"{name}: `.logo` 규칙이 없습니다"
        assert "text-decoration:none" in rule, (
            f"{name}: `.logo` 에 text-decoration:none 이 없습니다 — 로고를 안 올린 "
            f"설치에서 파란 밑줄 링크가 됩니다: {rule.strip()}"
        )


def test_the_product_name_sits_outside_the_logo_slot():
    """제품 이름은 `data-brand-logo` **바깥**이어야 한다.

    서버가 그 요소의 **내용을 통째로** `<img>` 로 갈아 끼우므로, 안에 두면 제품 이름이
    사라지고 `alt` 에 마크업이 들어간다(2026-10-06 에 겪음).
    """
    for name in ["drive.html", "folder-new.html"]:
        html = (STATIC / name).read_text(encoding="utf-8")
        slot = re.search(r"<span[^>]*data-brand-logo[^>]*>(.*?)</span>", html, re.DOTALL)
        assert slot, f"{name}: 로고 자리를 찾지 못했습니다"
        assert "<" not in slot.group(1), (
            f"{name}: 로고 자리 안에 다른 요소가 있습니다 — 갈아 끼울 때 사라집니다: "
            f"{slot.group(1)[:60]}"
        )


def test_admin_page_is_served_with_server_mode(client):
    body = client.get("/admin").text

    # 화면이 켜진 뒤 API로 모드를 물어보면 운영에서 안 되는 탭이 잠깐 보였다 사라진다.
    assert 'data-mode="serve"' in body
    # 로그인 모달이 이 페이지 안에 있어야 한다 — 페이지를 막으면 로그인할 화면도 막힌다.
    assert 'id="authModal"' in body


def test_static_assets_are_served(client):
    for path in ["/static/admin.js", "/static/admin.css", "/static/drive.js", "/static/drive.css",
                 "/static/common.css", "/static/dropdown.js"]:
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


def test_qa_import_markup_and_wiring_are_present():
    """QA 가져오기(요청서 11).

    모달만 오고 배선이 빠지면 눌러도 아무 일이 없고, 배선만 있고 마크업이 빠지면 화면이
    비어 보인다 — 둘 다 조용히 실패하므로 함께 확인한다.
    """
    html = (STATIC / "admin.html").read_text(encoding="utf-8")
    js = ADMIN_JS.read_text(encoding="utf-8")

    for element in ["qaImportBtn", "qaImportModal", "qaImportPreviewBody", "qaImportResultBody",
                    "tpl_qa_import_row", "tpl_qa_import_result", 'data-sum="new"']:
        assert element in html, f"QA 가져오기 마크업이 없습니다: {element}"

    assert "/api/admin/qa/import/preview" in js, "미리보기를 서버에 묻지 않습니다"
    assert "/api/admin/qa/import" in js
    # 되돌리기가 없다. 덮어쓸 것이 있으면 마지막으로 한 번 더 물어야 한다.
    handler = js[js.index("$('#qaImportStartBtn').on('click'"):]
    assert "askConfirm" in handler[:800], "덮어쓰기 전 확인 단계가 없습니다"
    # 진입 버튼은 검수 화면에 있어야 한다 — 가져오기의 결과가 곧 검수 대기줄이다.
    review = html[html.index('id="panel_review"'): html.index('id="panel_history"')]
    assert "qaImportBtn" in review


def test_studio_only_markup_is_present():
    """serve 에서 감춰야 하는 요소가 표시돼 있는지. 없으면 운영에서 동작하지 않는 버튼이 보인다."""
    html = (STATIC / "admin.html").read_text(encoding="utf-8")

    assert "data-studio-only" in html
    assert 'data-tab="generate"' in html and 'data-tab="eval"' in html


def test_docs_tab_can_register_single_files_not_only_folders():
    """문서를 낱개로도 올릴 수 있어야 한다.

    `webkitdirectory` 가 붙은 입력칸은 파일을 하나씩 고를 수 없다 — 브라우저가 폴더
    선택창만 연다. 그래서 몇 건만 고쳐 다시 올리는 흔한 경우에 폴더째 고르게 되고,
    바뀌지 않은 문서까지 전부 다시 청킹·임베딩한다.

    입력칸 둘(폴더·파일)이 다 있고 **각각 change 배선이 있는지** 본다. 버튼만 오고 배선이
    빠지면 눌러도 아무 일이 없다.
    """
    html = (STATIC / "admin.html").read_text(encoding="utf-8")
    js = ADMIN_JS.read_text(encoding="utf-8")

    docs = html[html.index('id="panel_docs"'): html.index('id="panel_generate"')]
    assert 'id="docUploadInput"' in docs and "webkitdirectory" in docs, "폴더 입력칸이 없습니다"

    file_input = docs[docs.index('id="docFileInput"'):]
    file_input = file_input[: file_input.index(">")]
    assert "webkitdirectory" not in file_input, "파일 입력칸에 폴더 속성이 붙어 낱개 선택이 막힙니다"
    assert 'id="docFileBtn"' in docs, "파일 선택을 여는 버튼이 없습니다"

    for control in ["#docUploadInput", "#docFileInput", "#docFileBtn"]:
        assert control in js, f"화면에는 있는데 admin.js 가 읽지 않는 입력: {control}"


def test_category_import_is_reachable_and_wired():
    """카테고리 JSON 가져오기(탭 ③).

    버튼만 오고 모달이 빠지면 눌러도 아무 일이 없고, 모달만 오면 열 방법이 없다 —
    둘 다 조용히 실패하므로 함께 확인한다. 반영 버튼은 미리보기를 거치기 전에는 눌리면
    안 된다: 카테고리는 챗봇 첫 화면에 그대로 나간다.
    """
    html = (STATIC / "admin.html").read_text(encoding="utf-8")
    js = ADMIN_JS.read_text(encoding="utf-8")

    cats = html[html.index('id="panel_categories"'): html.index('id="panel_generate"')]
    assert 'id="catImportBtn"' in cats and 'id="catSpecBtn"' in cats, "탭에 진입 버튼이 없습니다"
    # 버튼은 **패널 머리**(전체 폭)에 있어야 한다. 아래 카테고리 카드는 화면을 반으로 나눈
    # 320px 칸이라, 거기에 버튼이 넷이 되면 카드 제목이 세로로 무너진다(실제로 겪음).
    head = cats[: cats.index("</div>")]
    assert 'id="catImportBtn"' in head and 'id="catSpecBtn"' in head, "좁은 카드 머리에 버튼이 들어갔습니다"
    assert 'id="catImportModal"' in html and 'id="catSpecModal"' in html, "모달이 없습니다"

    apply_btn = html[html.index('id="catImportApplyBtn"'):]
    assert "disabled" in apply_btn[: apply_btn.index(">")], "미리보기 없이 반영이 눌립니다"

    for control in ["#catImportBtn", "#catSpecBtn", "#catImportText", "#catImportFileInput",
                    "#catImportPreviewBtn", "#catImportApplyBtn", "#catSpecCopyBtn"]:
        assert control in js, f"화면에는 있는데 admin.js 가 읽지 않는 입력: {control}"


def test_category_spec_example_is_what_the_server_accepts():
    """`카테고리등록규격` 에 적힌 예시가 실제로 통과해야 한다.

    규격과 파서가 갈라지면 "규격대로 만들었는데 안 들어간다" 가 된다. 그 말을 듣는 사람은
    자기 파일을 의심하지 화면의 안내문을 의심하지 않는다 — 그래서 오래 헤맨다.
    """
    import html as html_mod
    import re as re_mod

    from app.core import category_import

    page = (STATIC / "admin.html").read_text(encoding="utf-8")
    spec = page[page.index('id="catSpecModal"'):]
    example = re_mod.search(r'<pre class="admin_guide_code">(.*?)</pre>', spec, re_mod.S)
    assert example, "규격에 형식 예시가 없습니다"

    store = category_import.parse(html_mod.unescape(example.group(1)))
    assert store.groups and store.groups[0].categories, "예시가 비어 있습니다"
    # 예시에 적은 quick_category_ids 도 실제 카테고리를 가리켜야 한다.
    ids = {c.category_id for g in store.groups for c in g.categories}
    assert set(store.quick_category_ids) <= ids


def test_docs_bulk_delete_is_wired_and_studio_only():
    """문서 목록의 체크박스 · 선택 삭제.

    지우는 버튼이 **아무것도 안 골랐을 때 눌리면 안 된다** — 확인 창이 '0건을 삭제할까요'로
    뜨는 것보다, 애초에 눌리지 않는 편이 낫다. 그리고 운영(serve)에는 보이면 안 된다:
    눌러도 403 이 나는 버튼은 오류보다 나쁘다(사람이 자기 권한을 의심하며 계속 누른다).
    """
    html = (STATIC / "admin.html").read_text(encoding="utf-8")
    js = ADMIN_JS.read_text(encoding="utf-8")

    docs = html[html.index('id="panel_docs"'): html.index('id="panel_generate"')]
    assert 'data-check-all="doc"' in docs, "전체 선택 체크박스가 없습니다"

    head_cell = docs[docs.index('data-check-all="doc"') - 120: docs.index('data-check-all="doc"')]
    assert "data-studio-only" in head_cell, "운영에서도 선택 열이 보입니다"

    button = docs[docs.index('id="docBulkDeleteBtn"'):]
    assert "disabled" in button[: button.index(">")], "아무것도 안 골라도 눌립니다"
    bar = docs[docs.index('id="docSelCount"') - 200: docs.index('id="docBulkDeleteBtn"')]
    assert "data-studio-only" in bar, "운영에서도 삭제 버튼이 보입니다"

    assert "/api/admin/docs/bulk-delete" in js, "화면이 일괄 삭제를 부르지 않습니다"
    handler = js[js.index("#docBulkDeleteBtn').on('click'"):]
    assert "askConfirm" in handler[:700], "지우기 전 확인 단계가 없습니다"


def test_qa_import_accepts_paste_and_is_reachable_from_the_generate_tab():
    """외부 AI로 만든 QA 들여오기 — 파일과 붙여넣기.

    붙여넣기는 **파일과 같은 경로**로 올라가야 한다. 서버에 텍스트용 입구를 따로 내면
    판단이 두 벌이 되고 언제 갈라졌는지 모르게 어긋난다. 그래서 화면이 붙여넣은 내용을
    파일처럼 만들어 보내는지(`pastedFile`), 그리고 부르는 곳이 하나인지 본다.
    """
    html = (STATIC / "admin.html").read_text(encoding="utf-8")
    js = ADMIN_JS.read_text(encoding="utf-8")

    start = html.index('id="panel_generate"')
    generate = html[start: html.index("<section", start + 10)]
    assert 'id="genImportBtn"' in generate and 'id="qaSpecBtn"' in generate, "⑥ 탭에 입구가 없습니다"

    assert 'id="qaImportText"' in html, "붙여넣기 칸이 없습니다"
    assert "function pastedFile" in js, "붙여넣은 내용을 파일처럼 보내지 않습니다"
    # 가져오기를 부르는 곳은 미리보기·반영 두 군데뿐이어야 한다.
    assert js.count("'/api/admin/qa/import/preview'") == 1
    # 두 입구가 같은 모달을 연다 — 들여오는 규칙이 한 곳에만 있어야 한다.
    assert "$('#genImportBtn').on('click', qaImpOpen)" in js


def test_qa_spec_example_is_what_the_importer_accepts():
    """`QA 등록 규격` 의 예시가 실제로 읽혀야 한다.

    규격과 파서가 갈라지면 "규격대로 만들었는데 안 들어간다" 가 된다. 그 말을 듣는 사람은
    자기 파일을 의심하지 화면의 안내문을 의심하지 않는다.
    """
    import html as html_mod
    import json
    import re as re_mod

    from app.qa import importer

    page = (STATIC / "admin.html").read_text(encoding="utf-8")
    spec = page[page.index('id="qaSpecModal"'):]
    example = re_mod.search(r'<pre class="admin_guide_code">(.*?)</pre>', spec, re_mod.S)
    assert example, "규격에 형식 예시가 없습니다"

    items = importer.read_items(json.loads(html_mod.unescape(example.group(1))))

    assert len(items) == 1 and items[0].question and items[0].answer
    assert len(items[0].variants) >= 3, "예시가 변형 질문의 중요성을 보여주지 못합니다"


def test_the_qa_request_template_matches_the_importer():
    """외부 AI에게 주는 요청서(`docs/QA-생성-요청서.md`)의 예시가 실제로 읽혀야 한다.

    이 파일은 사람이 복사해 AI에게 주는 것이라, 형식이 틀리면 **AI가 틀린 형식으로 수백 건을
    만든 뒤에야** 드러난다. 화면의 `QA 등록 규격` 과 같은 것을 지킨다.
    """
    import json
    import re as re_mod

    from app.qa import importer

    doc = (STATIC.parents[1] / "docs" / "QA-생성-요청서.md").read_text(encoding="utf-8")
    example = re_mod.search(r"```json\n(.*?)```", doc, re_mod.S)
    assert example, "요청서에 형식 예시가 없습니다"

    items = importer.read_items(json.loads(example.group(1)))

    assert len(items) == 1 and items[0].question and items[0].answer
    # 변형 질문 8~15개를 요구하면서 예시가 3개면 AI 는 예시를 따라 한다.
    assert len(items[0].variants) >= 8, "예시의 변형 질문이 규칙보다 적습니다"
    # 2026-10-06: 받아 본 QA 30건이 `category_id` 가 전부 비어 있었다. 규칙에 '필수'라고
    # 적어도 **예시가 비어 있으면** AI 는 예시를 따라 한다.
    assert items[0].category_id, "예시에 주제가 비어 있습니다"
    assert items[0].source_doc_ids, "예시에 근거 문서가 비어 있습니다"


def test_login_labels_are_not_mangled():
    """로그인 모달의 글자가 깨진 채로 들어온 적이 있다 — `비밀번호` 가 `별번호` 였다
    (첫 커밋부터 2026-10-03 까지).

    퍼블 산출물은 코드페이지가 다른 환경을 거쳐 오면서 **한글이 조용히 깨진다.** 아무도
    오류를 보지 못하고, 로그인하려던 사람이 "이게 뭐지" 하고 멈춘다. 두 화면이 같은 말을
    쓰는지까지 함께 본다 — 챗봇 쪽 로그인은 멀쩡했고 관리자만 깨져 있었다.
    """
    admin = (STATIC / "admin.html").read_text(encoding="utf-8")

    assert "별번호" not in admin
    assert ">비밀번호</label>" in admin, "비밀번호 라벨이 사라졌거나 깨졌습니다"
    # 챗봇에는 로그인 모달이 없다 — 머리의 `관리자` 는 /admin 으로 보내기만 한다(재설계 13).


def test_the_rag_document_template_actually_chunks(tmp_path, isolated_data):
    """외부 AI에게 주는 요청서(`docs/RAG문서-작성-요청서.md`)의 예시가 실제로 잘려야 한다.

    이 파일은 사람이 복사해 AI에게 주는 것이라, 형식이 틀리면 **AI가 수십 건을 틀린 형식으로
    쓴 뒤에야** 드러난다. 잘리는 규칙을 아는 것은 `app/ingestion/chunker.py` 뿐이므로
    설명이 아니라 그 코드에 통과시켜 본다.
    """
    import re as re_mod

    from app.core import config as config_module
    from app.ingestion.chunker import chunk_markdown_file

    doc = (STATIC.parents[1] / "docs" / "RAG문서-작성-요청서.md").read_text(encoding="utf-8")
    example = re_mod.search(r"````markdown\n(.*?)````", doc, re_mod.S)
    assert example, "요청서에 예시 문서가 없습니다"

    target = tmp_path / "api-등록.md"
    target.write_text(example.group(1), encoding="utf-8")
    _hash, chunks = chunk_markdown_file(target)

    assert len(chunks) >= 3, "소제목으로 나뉘지 않았습니다 — 예시가 규칙을 못 보여줍니다"
    assert chunks[0].metadata["title"] == "API 등록", "앞머리를 못 읽었습니다"
    # 한 절이 경고 기준을 넘으면 임베딩에서 뒷부분이 조용히 버려진다. 예시가 그래선 안 된다.
    limit = config_module.get_settings().embed_warn_chars
    assert all(len(c.text) <= limit for c in chunks), f"{limit}자를 넘는 절이 있습니다"
    # 쓰지 말라고 적어 둔 것을 예시가 쓰고 있으면 AI 는 예시를 따라 한다.
    body = example.group(1)
    assert "![" not in body and "[[" not in body


def test_the_category_request_template_matches_the_importer():
    """외부 AI에게 주는 요청서(`docs/카테고리-작성-요청서.md`)의 예시가 실제로 읽혀야 한다.

    규격과 파서가 갈라지면 "규격대로 만들었는데 안 들어간다" 가 된다. 사람이 복사해 AI에게
    주는 파일이라, 틀리면 **AI 가 수십 건을 틀린 형식으로 만든 뒤에야** 드러난다.
    """
    import json
    import re as re_mod

    from app.core import category_import

    doc = (STATIC.parents[1] / "docs" / "카테고리-작성-요청서.md").read_text(encoding="utf-8")
    example = re_mod.search(r"```json\n(.*?)```", doc, re_mod.S)
    assert example, "요청서에 형식 예시가 없습니다"

    store = category_import.parse(example.group(1))
    ids = {c.category_id for g in store.groups for c in g.categories}

    assert store.groups and ids
    # 추천 질문 2~4개를 요구하면서 예시가 비어 있으면 AI 는 예시를 따라 한다.
    assert all(c.questions for g in store.groups for c in g.categories), "예시에 추천 질문이 없습니다"
    assert set(store.quick_category_ids) <= ids, "자주 찾는 주제가 없는 ID 를 가리킵니다"

# ── 사용자 화면 (신규 디자인 · 자료 + AI 질문) ───────────────────────────────


def test_drive_screen_calls_only_the_six_server_seams():
    """퍼블 산출물의 샘플 데이터가 남아 있지 않은지, 서버는 정해진 자리에서만 부르는지.

    산출물은 `const folders = [...]` · `const files = [...]` 로 가짜 목록을 들고 옵니다.
    남겨 두면 서버 데이터 위에 가짜가 겹쳐 보이고, 비어 있는 설치가 꽉 찬 것처럼 보입니다.
    """
    drive = (STATIC / "drive.js").read_text(encoding="utf-8")

    for leftover in ("const folders = [", "const files = [", "let totalCount"):
        assert leftover not in drive, f"산출물의 샘플 데이터가 남아 있습니다: {leftover}"
    for url in ("'/api/drive'", "'/api/models'", "/api/chat/stream?", "'/api/feedback'",
                "'/api/support'", "'/api/admin/docs/upload'"):
        assert url in drive, f"{url} 를 부르지 않습니다"


def test_drive_assets_are_served_from_static():
    """산출물은 폴더째 열어 보는 전제라 `href="css/common.css"` 처럼 상대 경로로 옵니다.

    우리 서버는 화면을 `/` 에서 내려주므로 그대로 두면 404 가 되고 **화면이 아예 안 뜹니다.**
    폰트도 같습니다 — 산출물은 Google Fonts 를 부르는데 운영은 폐쇄망입니다.
    """
    html = (STATIC / "drive.html").read_text(encoding="utf-8")
    common = (STATIC / "common.css").read_text(encoding="utf-8")

    assert 'href="/static/drive.css"' in html and 'src="/static/drive.js"' in html
    assert "fonts.googleapis.com" not in html and "fonts.gstatic.com" not in html
    assert "fonts.googleapis.com" not in common, "CSS 가 외부 폰트를 부릅니다"
    assert "/static/fonts/" in common, "로컬 폰트를 안 씁니다"


def test_ai_controls_are_tied_together():
    """AI 답변이 꺼져 있으면 모델·추론은 쓸 수 없습니다.

    검수된 답변을 그대로 내보내는 길이라 모델도 추론도 개입하지 않습니다. 화면이 이 규칙을
    안 지키면 사용자가 모델을 고른 뒤 "왜 그 모델이 답을 안 하지"로 헤맵니다.
    """
    html = (STATIC / "drive.html").read_text(encoding="utf-8")
    drive = (STATIC / "drive.js").read_text(encoding="utf-8")

    for control in ('id="aiMode"', 'id="aiModel"', 'id="aiReasoning"'):
        assert control in html, f"{control} 가 없습니다"
    # 모델 목록이 비면(운영 = LLM 없음) AI 답변 자체를 잠급니다.
    assert "llmDown" in drive and "aiActive" in drive


def test_verified_and_ai_answers_never_wear_the_same_badge():
    """검수 전 답변에 `검수 완료` 표시가 섞이면 안 됩니다.

    이 제품에서 가장 하면 안 되는 혼동입니다 — 스위치를 켠 것을 잊은 사람이 AI 초안을
    검수된 답변으로 읽습니다. 말풍선이 `data-mode` 로만 갈립니다.
    """
    html = (STATIC / "drive.html").read_text(encoding="utf-8")
    drive = (STATIC / "drive.js").read_text(encoding="utf-8")

    for name in ("badge_verified", "badge_ai"):
        assert name in html, f"{name} 가 없습니다"
    assert "data-mode" in drive, "말풍선이 모드로 갈리지 않습니다"


def test_feedback_is_only_offered_on_reviewed_answers():
    """👍/👎 는 **검수된 답변에만** 붙습니다.

    AI 초안은 아직 검수 대상이 아니고, 서버가 이어 줄 `log_id` 도 주지 않습니다. 화면이
    아무 말풍선에나 붙이면 신고가 어느 답변 것인지 알 수 없는 상태로 쌓입니다.
    """
    drive = (STATIC / "drive.js").read_text(encoding="utf-8")

    assert "m.mode === 'verified' && !!m.logId" in drive, "피드백이 검수 답변에만 붙지 않습니다"
    # 사유 세 가지는 **서버가 정한 값**이다(app/core/feedback.py).
    for reason in ("mismatch", "wrong", "thin"):
        assert reason in (STATIC / "drive.html").read_text(encoding="utf-8"), f"{reason} 사유가 없습니다"


def test_the_screen_never_invents_a_ticket_number():
    """접수번호는 **서버가 준 값만** 보여 줍니다.

    화면이 만들면 사용자가 부르는 번호와 이력에 남은 번호가 달라져 담당자가 찾지 못합니다.
    2026-10-06 에 번호를 만드는 함수가 없는 채로 호출돼 자바스크립트가 거기서 멈춘 적이
    있습니다 — 그래서 '만들지 않는다'를 검사로 박아 둡니다.
    """
    drive = (STATIC / "drive.js").read_text(encoding="utf-8")

    assert "newTicketId" not in drive and "TCK-" not in drive, "화면이 접수번호를 만듭니다"
    assert "d.ticket_id" in drive, "서버가 준 접수번호를 안 씁니다"


def test_waiting_shows_elapsed_seconds():
    """AI 답변은 수십 초가 걸립니다. 경과 시간이 안 보이면 멈춘 것과 구분되지 않습니다."""
    drive = (STATIC / "drive.js").read_text(encoding="utf-8")

    assert "setInterval" in drive, "경과 시간이 올라가지 않습니다"


def test_streaming_contract_matches_the_server():
    """화면이 기다리는 이벤트와 서버가 보내는 이벤트가 같아야 합니다.

    둘이 어긋나면 오류가 나지 않고 **답이 영영 안 나옵니다.** 조용히 비어 있는 화면이 됩니다.
    """
    drive = (STATIC / "drive.js").read_text(encoding="utf-8")
    server = (STATIC.parents[1] / "app" / "api" / "chat_stream.py").read_text(encoding="utf-8")

    for event in ("thinking", "answer", "sources", "done"):
        assert f"'{event}'" in drive, f"화면이 {event} 를 안 받습니다"
        assert f'"{event}"' in server, f"서버가 {event} 를 안 보냅니다"


def test_markdown_rules_stay_in_step_with_the_review_preview():
    """사용자가 보는 답변과 검수 미리보기가 같은 규칙으로 그려져야 합니다.

    둘이 달라지면 검수가 의미를 잃습니다 — 검수자는 멀쩡해 보이는 것을 승인하고, 사용자는
    깨진 표를 봅니다. 렌더가 두 파일에 각각 있으므로(공용으로 못 빼는 이유는 인수인계
    문서 5-13) 적어도 다루는 문법이 같은지는 지킵니다.
    """
    drive = (STATIC / "drive.js").read_text(encoding="utf-8")
    admin = (STATIC / "admin.js").read_text(encoding="utf-8")

    for token in ("<ol>", "<ul>", "<table>", "<strong>", "<code>"):
        assert token in drive, f"사용자 화면이 {token} 을 안 그립니다"
        assert token in admin, f"검수 미리보기가 {token} 을 안 그립니다"

    # 제목(`#`·`##`). 자료 원문은 제목을 쓰므로 안 그리면 `## 제목` 이 글자 그대로 보입니다.
    for source, where in ((drive, "사용자 화면"), (admin, "검수 미리보기")):
        assert "#{1,6}" in source, f"{where} 가 마크다운 제목을 안 그립니다"

    # 덩이를 가르는 규칙도 같아야 합니다 — 빈 줄 거르기와 목록 판정(첫 줄로 본다)이
    # 어긋나면 같은 글이 한쪽에서는 목록, 한쪽에서는 `- ` 가 그대로 보입니다(2026-10-06).
    for rule in (r"l.trim() !== ''", r"/^\s*\d+\.\s/.test(lines[0])", r"/^\s*[-*]\s/.test(lines[0])"):
        assert rule in drive, f"사용자 화면의 덩이 판정이 다릅니다: {rule}"
        assert rule in admin, f"검수 미리보기의 덩이 판정이 다릅니다: {rule}"


def test_uploading_is_batched_like_the_server_expects():
    """자료를 한 요청에 다 보내지 않습니다.

    한 요청으로 몰면 (1) 진행 상황을 보여줄 수 없고 (2) 프록시 타임아웃 뒤에 무엇이
    들어갔는지 알 수 없습니다. 서버도 20건까지만 받습니다.
    """
    drive = (STATIC / "drive.js").read_text(encoding="utf-8")
    upload = (STATIC.parents[1] / "app" / "ingestion" / "doc_upload.py").read_text(encoding="utf-8")

    assert "UP_FILES = 20" in drive, "화면이 묶음 크기를 서버와 맞추지 않습니다"
    assert "MAX_FILES_PER_REQUEST = 20" in upload


def test_the_user_screen_shows_what_is_not_indexed():
    """원본만 올라와 검색에 안 걸리는 자료를 **눈에 보이게** 둡니다.

    숨기면 "올렸는데 AI가 모른다"의 원인을 사람이 짚을 수 없습니다.
    """
    drive = (STATIC / "drive.js").read_text(encoding="utf-8")
    css = (STATIC / "drive.css").read_text(encoding="utf-8")

    assert "색인 안 됨" in drive
    assert ".tag.t-raw" in css, "그 배지의 스타일이 없습니다"


def test_deferred_features_are_hidden_not_deleted():
    """후순위로 미룬 것(접근 권한)은 마크업을 지우지 않고 감춥니다.

    되살릴 때 디자인을 다시 받지 않기 위해서입니다 — 산출물이 이미 그 모양을 정해 뒀습니다.
    """
    html = (STATIC / "folder-new.html").read_text(encoding="utf-8")

    assert 'id="permCard" hidden' in html, "권한 카드가 감춰져 있지 않습니다"
    assert "perm-table" in html, "권한 마크업을 지웠습니다 — 되살릴 때 다시 받아야 합니다"


def _ids_in(html: str) -> set[str]:
    return set(re.findall(r'id="([^"]+)"', html))


@pytest.mark.parametrize("page,script", [
    ("drive.html", "drive.js"),
    ("folder-new.html", "folder-new.js"),
])
def test_every_element_the_screen_looks_for_exists(page, script):
    """화면이 찾는 `id` 가 마크업에 **전부 있는지.**

    없으면 `getElementById` 가 `null` 을 주고 그 줄에서 자바스크립트가 멈춥니다. 콘솔을
    열어 보지 않으면 "버튼이 안 눌린다" 로만 드러나고, 어디서 멈췄는지는 알 수 없습니다.
    실제로 그 상태로 하루를 쓴 적이 있습니다(2026-10-06, 접수번호 함수 누락).

    퍼블 산출물을 다시 받아 얹을 때 **가장 잘 깨지는 자리**이기도 합니다 — 산출물은 우리가
    더한 id 를 모르므로 조용히 빠뜨립니다.
    """
    html = (STATIC / page).read_text(encoding="utf-8")
    source = (STATIC / script).read_text(encoding="utf-8")

    available = _ids_in(html)
    wanted = set(re.findall(r"""\$\(['"]([A-Za-z][\w-]*)['"]\)""", source))
    missing = sorted(wanted - available)

    assert not missing, f"{script} 가 찾는데 {page} 에 없는 id: {', '.join(missing)}"


def test_every_template_the_screen_clones_exists():
    """`<template>` 이 없으면 복제하는 줄에서 멈춥니다 — 말풍선이 아예 안 생깁니다."""
    html = (STATIC / "drive.html").read_text(encoding="utf-8")
    source = (STATIC / "drive.js").read_text(encoding="utf-8")

    declared = set(re.findall(r'<template id="([^"]+)"', html))
    used = set(re.findall(r"""tpl\(['"]([\w-]+)['"]\)""", source))

    assert not (used - declared), f"없는 템플릿을 복제합니다: {', '.join(sorted(used - declared))}"
    # 쓰지 않는 템플릿은 죽은 마크업입니다. 다음 사람이 그것을 보고 있다고 믿습니다.
    assert not (declared - used), f"쓰지 않는 템플릿이 있습니다: {', '.join(sorted(declared - used))}"


def test_message_parts_the_screen_touches_are_in_the_template():
    """말풍선 안에서 찾는 클래스가 템플릿에 있어야 합니다.

    `q(el, '.msg_md')` 가 `null` 이면 답변 본문을 넣는 줄에서 멈추고, **글자가 흘러나오지
    않습니다.** 스트리밍은 오류 없이 조용히 비어 있는 모습이 됩니다.
    """
    html = (STATIC / "drive.html").read_text(encoding="utf-8")
    source = (STATIC / "drive.js").read_text(encoding="utf-8")

    start = html.index('<template id="tpl_bot">')
    bot = html[start:html.index("</template>", start)]
    present = {name for attr in re.findall(r'class="([^"]+)"', bot) for name in attr.split()}
    wanted = set(re.findall(r"""q\((?:el|m\.el), '\.([\w-]+)'\)""", source))
    missing = sorted(wanted - present)

    assert not missing, f"tpl_bot 에 없는 클래스를 찾습니다: {', '.join(missing)}"


def test_hidden_actually_hides_on_the_user_screen():
    """`hidden` 속성이 작성자 CSS 를 **이겨야** 합니다.

    브라우저 기본은 `[hidden]{display:none}` 이지만 작성자가 `display:flex` 를 주면 그쪽이
    이깁니다. 화면은 `hidden` 을 붙였다 떼어 상태를 바꾸므로(`show()`), 규칙이 없으면 감춘
    것이 그대로 보입니다 — 2026-10-06 에 답변이 다 나온 뒤에도 '자료를 읽는 중' 이 남고
    검수 배지와 AI 배지가 **함께** 떴습니다.

    오류가 아니라 **멈춘 것처럼 보이는** 종류라, 콘솔을 봐도 단서가 없습니다.
    """
    common = (STATIC / "common.css").read_text(encoding="utf-8")

    # 선택자 하나가 모든 상태 전환을 떠받칩니다. 약해지면(`!important` 가 빠지면) 조용히
    # 되살아나므로 둘을 함께 봅니다.
    rules = [line for line in common.splitlines() if "[hidden]" in line and "display" in line]
    assert rules, "`[hidden]` 을 감추는 규칙이 없습니다"
    assert any("!important" in line for line in rules), f"`[hidden]` 규칙이 약합니다: {rules}"


def test_the_knowledge_search_shows_one_answer_at_a_time():
    """**AI 지식 검색은 단건입니다.** 새로 물으면 앞의 답을 대체합니다.

    대화로 쌓아 두면 할 수 있는 것보다 많아 보입니다 — 이어 묻기(`더 자세히`)는 받지
    않습니다. 2026-10-07 에 재 보니 (1) 검수된 답변은 미리 써 둔 고정 글이라 "더"에 줄
    것이 없고 (2) 직전 질문을 합쳐 찾으면 멀쩡하던 질문까지 망가졌습니다
    (`그럼 TB 배포는?` 0.934 → 0.779).
    """
    drive = (STATIC / "drive.js").read_text(encoding="utf-8")
    html = (STATIC / "drive.html").read_text(encoding="utf-8")

    assert "ansBody.innerHTML = '';" in drive, "새 질문이 앞의 답을 대체하지 않습니다"
    for leftover in ("is_chat", "tpl_me", "chatMode", "새 대화"):
        assert leftover not in drive and leftover not in html, f"대화 잔재가 남아 있습니다: {leftover}"
    # 사용자 말풍선이 없어야 합니다 — 질문은 패널 머리(`ans-q`)에 한 줄로 들어갑니다.
    assert "msg_bubble" not in html
    assert 'id="ansQ"' in html


def test_no_two_functions_share_a_name_in_the_same_scope():
    """같은 칸에 같은 이름의 함수가 둘이면 **뒤엣것만 남습니다.**

    2026-10-07 에 관리자 화면에 프로젝트 표를 넣으면서 `renderProjects` 를 썼는데, 상단
    프로젝트 선택기가 이미 그 이름을 쓰고 있었습니다. 선언이 통째로 가려져 **표가 아무 말
    없이 안 그려졌습니다** — 오류도, 빈 목록 안내도 없었습니다. 파일이 3,600줄이라 눈으로는
    못 찾습니다.

    들여쓴 함수(다른 함수 안에 있는 것)는 범위가 달라 겹쳐도 됩니다. 그래서 **같은 칸**만
    봅니다 — 이 파일들은 IIFE 안을 2칸으로 씁니다.
    """
    import collections

    for name in ("admin.js", "drive.js", "folder-new.js", "dropdown.js"):
        source = (STATIC / name).read_text(encoding="utf-8")
        top = re.findall(r"^(?: {2})?function\s+([A-Za-z_$][\w$]*)\s*\(", source, re.M)
        dupes = [n for n, c in collections.Counter(top).items() if c > 1]
        assert not dupes, f"{name} 에 같은 칸의 같은 이름 함수가 있습니다: {', '.join(dupes)}"


def test_the_search_view_never_narrows_to_one_project():
    """`AI 지식 검색` 은 **늘 전체 범위**입니다.

    메뉴 이름이 '전체' 를 약속하는데, 앞서 고른 프로젝트가 남아 조용히 좁혀 찾으면
    사용자는 왜 안 나오는지 알 길이 없습니다. 둘러보기(`프로젝트`)에서만 좁힙니다.
    """
    drive = (STATIC / "drive.js").read_text(encoding="utf-8")

    assert "function searchProject()" in drive
    assert "state.view === 'search' ? ''" in drive, '검색 화면이 범위를 좁힐 수 있습니다'
    # 질문을 보낼 때 프로젝트를 **직접** 읽으면 그 약속이 깨집니다.
    assert "project: state.projectId" not in drive, "검색이 고른 프로젝트를 직접 씁니다"


def test_the_search_view_hides_the_file_list():
    """검색하러 온 사람에게 폴더·파일 목록이 먼저 보이면 안 됩니다."""
    html = (STATIC / "drive.html").read_text(encoding="utf-8")
    css = (STATIC / "drive.css").read_text(encoding="utf-8")

    for block in ('id="folders"', 'id="list"', 'id="chips"', 'id="dropzone"'):
        start = html.index(block)
        tag = html.rindex("<", 0, start)
        assert "data-browse" in html[tag:html.index(">", start)], f"{block} 에 표시가 없습니다"
    assert ".app.is_search [data-browse]" in css
