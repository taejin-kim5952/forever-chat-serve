"""드라이브 — 자료 목록·원본 보관·프로젝트 교차 검색.

여기서 지키는 것은 **"원본과 본문이 한 건"** 이라는 규칙과 **"올렸는데 검색에 안 걸리는
상태가 눈에 보인다"** 는 것이다. 둘 다 틀려도 예외가 안 난다 — 사용자가 "자료를 올렸는데
AI가 모른다"를 겪고 나서야 드러나는 종류다.
"""

import base64

import pytest
from fastapi.testclient import TestClient

from app.core import config
from app.main import app
from app.pipeline import scope

AUTH = {"Authorization": "Basic " + base64.b64encode(b"tester:secret").decode()}

MD = """---
title: {title}
category: 이용가이드 > 절차
---

# {title}

## 절

{body}
"""

# 가짜 임베더는 글자 버킷을 세므로, 두 프로젝트의 자료는 **쓰는 글자가 겹치지 않아야**
# 고르는 판단을 검증할 수 있다. 한쪽은 한글, 한쪽은 영문으로 둔다.
KOREAN = "레지스트리에 게시하려면 먼저 매니페스트를 올리고 상태를 검토 중으로 바꿉니다."
ENGLISH = "Billing refunds require an invoice number and settlement happens monthly."

# 원본 파일 대신 쓰는 바이트. 내용은 보지 않고 보관·내려주기만 하므로 아무 바이트여도 된다.
BLOB = b"PK" + b"0" * 500


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def studio(monkeypatch):
    monkeypatch.setattr("app.api.admin_docs.is_studio", lambda: True)
    monkeypatch.setattr("app.api.admin_projects.is_studio", lambda: True)


def send(client, files, *, project="", overwrite=False):
    payload = [("files", (name, data, "application/octet-stream")) for name, data in files]
    payload += [("paths", (None, name)) for name, _ in files]
    url = "/api/admin/docs/upload" + (f"?project={project}" if project else "")
    return client.post(url, files=payload, data={"overwrite": str(overwrite).lower()}, headers=AUTH)


def drive(client, **params):
    return client.get("/api/drive", params=params).json()


# ── 원본과 본문이 한 건이 된다 ───────────────────────────────────────────────


def test_an_original_and_its_markdown_become_one_entry(client, studio, isolated_data):
    """`가이드.pptx` 와 `가이드.md` 를 함께 올리면 **한 줄**이다.

    짝을 맺는 화면을 따로 만들지 않기 위해 파일 이름으로 묶는다. 두 줄로 보이면 사람이
    "왜 같은 자료가 두 번 있지" 를 묻게 된다.
    """
    body = send(client, [
        ("가이드.md", MD.format(title="가이드", body=KOREAN).encode()),
        ("가이드.pptx", BLOB),
    ]).json()

    assert (body["created"], body["attached"]) == (1, 1)

    docs = drive(client)["docs"]
    assert len(docs) == 1
    doc = docs[0]
    assert doc["doc_id"] == "가이드"
    # 아이콘·크기는 **원본** 기준, 검색 가능 여부는 **본문** 기준이다.
    assert doc["kind"] == "ppt" and doc["file_name"] == "가이드.pptx"
    assert doc["bytes"] == len(BLOB)
    assert doc["indexed"] is True and doc["chunk_count"] > 0


def test_an_original_without_markdown_is_listed_but_not_indexed(client, studio, isolated_data):
    """본문이 없으면 **검색에 걸리지 않는다. 그래도 목록에는 뜬다.**

    숨기면 "올렸는데 AI가 모른다"의 원인을 짚을 수가 없다. 받지 않고 거절하면 "왜 안
    올라가지"가 된다. 그래서 받고 눈에 보이게 한다.
    """
    send(client, [("설계서.pdf", BLOB)])

    docs = drive(client)["docs"]
    assert len(docs) == 1
    assert docs[0]["kind"] == "pdf"
    assert docs[0]["indexed"] is False and docs[0]["chunk_count"] == 0


def test_only_the_markdown_still_works_on_its_own(client, studio, isolated_data):
    """원본 없이 `.md` 만 올리는 지금까지의 방식이 그대로 동작해야 한다."""
    send(client, [("개요.md", MD.format(title="개요", body=KOREAN).encode())])

    doc = drive(client)["docs"][0]
    assert doc["kind"] == "md" and doc["indexed"] is True
    assert doc["file_name"] == "개요.md"


def test_several_originals_can_belong_to_one_document(client, studio, isolated_data):
    """`가이드.pptx` 와 `가이드.pdf` 는 **둘 다 남는다.**

    본문 하나가 원본 여럿을 가리킬 수 있게 되면서(앞머리 `source_files`) '한 문서에 원본
    하나' 규칙이 사라졌다. 조용히 지우면 다른 본문이 가리키던 원본까지 없어진다.
    목록에는 한 줄로 보이고, 대표 하나가 아이콘이 된다.
    """
    send(client, [("가이드.md", MD.format(title="가이드", body=KOREAN).encode())])
    send(client, [("가이드.pptx", BLOB), ("가이드.pdf", BLOB)])

    docs = drive(client)["docs"]
    assert len(docs) == 1
    assert {f["name"] for f in docs[0]["files"]} == {"가이드.pptx", "가이드.pdf"}
    assert docs[0]["bytes"] == len(BLOB) * 2, "크기는 묶인 원본 전부의 합이어야 한다"


# ── 내려받기 ─────────────────────────────────────────────────────────────────


def test_download_gives_the_original_when_there_is_one(client, studio, isolated_data):
    send(client, [
        ("가이드.md", MD.format(title="가이드", body=KOREAN).encode()),
        ("가이드.pptx", BLOB + b"pptx-bytes"),
    ])

    response = client.get("/api/drive/가이드/file")

    assert response.status_code == 200
    assert response.content.endswith(b"pptx-bytes")


def test_download_falls_back_to_the_markdown(client, studio, isolated_data):
    """원본이 없으면 `.md` 원문을 준다. 버튼이 아무 일도 안 하는 것보다 낫다."""
    send(client, [("개요.md", MD.format(title="개요", body=KOREAN).encode())])

    response = client.get("/api/drive/개요/file")

    assert response.status_code == 200
    assert KOREAN.encode() in response.content


def test_a_path_in_the_doc_id_is_refused(client, isolated_data):
    """인증이 없는 경로다. 문서 ID가 경로로 해석되면 서버 파일이 그대로 나간다."""
    assert client.get("/api/drive/..%2F..%2F.env/file").status_code in (400, 404)


def test_download_of_a_missing_document_is_404(client, isolated_data):
    assert client.get("/api/drive/없는문서/file").status_code == 404


# ── 지우면 원본도 함께 ───────────────────────────────────────────────────────


def test_deleting_a_document_also_deletes_its_original(client, studio, isolated_data):
    """원본이 남으면 목록에 `색인 안 됨` 으로 되살아난다."""
    send(client, [
        ("가이드.md", MD.format(title="가이드", body=KOREAN).encode()),
        ("가이드.pptx", BLOB),
    ])

    assert client.delete("/api/admin/docs/가이드", headers=AUTH).status_code == 200
    assert drive(client)["docs"] == []


def test_an_original_only_document_can_be_deleted(client, studio, isolated_data):
    """본문이 없는 자료도 지울 길이 있어야 한다 — 없으면 목록에서 치울 수가 없다."""
    send(client, [("설계서.pdf", BLOB)])

    body = client.post("/api/admin/docs/bulk-delete", headers=AUTH,
                       json={"doc_ids": ["설계서"]}).json()

    assert body["deleted"] == 1
    assert drive(client)["docs"] == []


# ── 프로젝트별 묶음 ──────────────────────────────────────────────────────────


def make_projects(client, *ids):
    for project_id in ids:
        client.post("/api/admin/projects", headers=AUTH,
                    json={"project_id": project_id, "name": project_id.upper()})


def test_drive_lists_every_project_with_its_own_size(client, studio, isolated_data):
    """폴더 카드가 프로젝트다. 용량은 **보관 중인 원본** 합계다."""
    make_projects(client, "mcp", "pay")
    send(client, [("게시절차.md", MD.format(title="게시절차", body=KOREAN).encode())], project="mcp")
    send(client, [("정산.md", MD.format(title="정산", body=ENGLISH).encode())], project="pay")
    send(client, [("정산.xlsx", BLOB + b"0" * 2000)], project="pay")

    body = drive(client)
    sizes = {p["project_id"]: (p["doc_count"], p["bytes"]) for p in body["projects"]}

    assert sizes["mcp"][0] == 1 and sizes["pay"][0] == 1
    assert sizes["pay"][1] > sizes["mcp"][1]
    assert body["total_bytes"] == sum(p["bytes"] for p in body["projects"])
    assert {d["project"] for d in body["docs"]} == {"mcp", "pay"}


# ── 프로젝트 교차 검색 ───────────────────────────────────────────────────────


def test_a_question_lands_on_the_project_that_has_the_material(client, studio, isolated_data):
    """폴더를 고르지 않은 '전체' 가 기본 상태다. 그때 **답이 있는 프로젝트**로 가야 한다.

    아무 프로젝트 하나를 집으면 "자료를 올렸는데 모른다"가 되고, 사용자는 그 이유를
    알 방법이 없다.
    """
    make_projects(client, "mcp", "pay")
    send(client, [("게시절차.md", MD.format(title="게시절차", body=KOREAN).encode())], project="mcp")
    send(client, [("정산.md", MD.format(title="정산", body=ENGLISH).encode())], project="pay")

    picked, vector = scope.pick("레지스트리에 게시하려면 매니페스트를 어떻게 올립니까")

    assert picked == "mcp"
    # 임베딩은 한 번만 계산해 고른 프로젝트의 본 검색에 그대로 넘긴다.
    assert vector and len(vector) == 64


def test_the_project_the_screen_chose_is_not_second_guessed(client, studio, isolated_data):
    """화면이 폴더를 골랐으면 서버가 다시 고르지 않는다 — 고른 것과 답이 어긋난다."""
    make_projects(client, "mcp")

    token = config.use_project("mcp")
    try:
        assert scope.pick("아무 질문") == ("", None)
    finally:
        config.reset_project(token)


def test_without_projects_nothing_changes(client, isolated_data):
    """단일 팩 설치는 예전과 똑같이 동작한다 — 고를 것이 없다."""
    assert scope.pick("아무 질문") == ("", None)


# ── 추론 과정 보기 ───────────────────────────────────────────────────────────


def fake_compose(question, hits, model=None, on_think=None, across=False):
    if on_think is not None:
        on_think("생각하는 중입니다")
    return "정리한 답입니다.", "fake-llm", hits[:1]


def ask_stream(client, question, **params):
    qs = {"question": question, "ai": "true", "reasoning": "true", "model": ""}
    qs.update(params)
    return client.get("/api/chat/stream", params=qs).text


@pytest.fixture
def ai_ready(client, studio, monkeypatch):
    """AI 답변 경로를 열고 모델 호출만 가짜로 바꾼다."""
    monkeypatch.setattr("app.api.chat_stream.is_studio", lambda: True)
    monkeypatch.setattr("app.studio.ask.compose", fake_compose)
    send(client, [("게시절차.md", MD.format(title="게시절차", body=KOREAN).encode())])


def test_reasoning_stays_off_while_the_setting_is_off(client, ai_ready, isolated_data):
    """설정이 꺼져 있으면 **화면이 요청해도** 사고 과정을 내보내지 않는다.

    주소만 고쳐 켜지면, 관리자가 끈 이유(느림·불안정)가 조용히 무시된다.
    """
    body = ask_stream(client, KOREAN)

    assert "event: answer" in body
    assert "event: thinking" not in body


def test_reasoning_streams_when_the_setting_is_on(client, ai_ready, isolated_data, monkeypatch):
    """켜면 모델의 생각이 조각마다 흘러나온다 — 수십 초를 기다리는 동안 보여 줄 것이다."""
    monkeypatch.setattr("app.api.chat_stream.get_settings",
                        lambda: isolated_data.model_copy(update={"ai_reasoning": True}))

    body = ask_stream(client, KOREAN)

    assert "event: thinking" in body
    assert "생각하는 중입니다" in body
    # 모델을 부르기 전에 **무엇을 근거로 삼을지**를 먼저 알려 준다. 사실인 것 하나다.
    assert "자료" in body and "찾았습니다" in body
    assert "event: answer" in body


# ── 앞머리로 원본을 가리키기 ─────────────────────────────────────────────────

LINKED_MD = """---
title: {title}
source_files: [{files}]
---

# {title}

## 절

{body}
"""


def test_the_markdown_can_name_the_original_it_came_from(client, studio, isolated_data):
    """본문이 **어떤 원본에서 왔는지** 앞머리에 적으면 그것으로 묶인다.

    실제 원본 이름은 `2026_하반기_API가이드_v3.pptx` 처럼 생겼고, 본문은 읽기 좋게 쪼개
    쓴다. 파일 이름이 같아야만 묶이는 규칙으로는 그 경우가 영영 안 맺어진다.
    """
    send(client, [("2026_하반기_API가이드_v3.pptx", BLOB)])
    send(client, [("api-등록-절차.md",
                   LINKED_MD.format(title="API 등록 절차",
                                    files="2026_하반기_API가이드_v3.pptx",
                                    body=KOREAN).encode())])

    docs = {d["doc_id"]: d for d in drive(client)["docs"]}

    assert len(docs) == 1, "원본이 따로 한 줄로 남으면 안 된다"
    doc = docs["api-등록-절차"]
    assert doc["kind"] == "ppt" and doc["indexed"] is True
    assert [f["name"] for f in doc["files"]] == ["2026_하반기_API가이드_v3.pptx"]


def test_one_original_can_be_shared_by_several_documents(client, studio, isolated_data):
    """긴 발표자료를 주제별로 쪼개 쓰는 경우. **원본은 하나, 본문은 여럿**이다.

    한쪽 본문을 지웠다고 원본을 없애면 남은 본문의 내려받기가 조용히 깨진다.
    """
    send(client, [("가이드원본.pptx", BLOB)])
    for name in ("등록편", "배포편"):
        send(client, [(f"{name}.md", LINKED_MD.format(title=name, files="가이드원본.pptx",
                                                      body=KOREAN).encode())])

    docs = {d["doc_id"]: d for d in drive(client)["docs"]}
    assert set(docs) == {"등록편", "배포편"}
    assert all(d["files"][0]["name"] == "가이드원본.pptx" for d in docs.values())

    # 한쪽을 지워도 원본은 남는다.
    assert client.delete("/api/admin/docs/등록편", headers=AUTH).status_code == 200
    left = {d["doc_id"]: d for d in drive(client)["docs"]}
    assert set(left) == {"배포편"}
    assert left["배포편"]["files"][0]["name"] == "가이드원본.pptx"

    # 마지막 본문까지 지우면 원본도 따라간다 — 주인 없는 자료로 남겨 두지 않는다.
    assert client.delete("/api/admin/docs/배포편", headers=AUTH).status_code == 200
    assert drive(client)["docs"] == []


def test_a_document_can_point_at_several_originals(client, studio, isolated_data):
    """발표자료와 정산표를 함께 읽고 쓴 본문. 둘 다 내려받을 수 있어야 한다."""
    send(client, [("설계서.pptx", BLOB), ("항목표.xlsx", BLOB)])
    send(client, [("정리.md", LINKED_MD.format(title="정리", files="설계서.pptx, 항목표.xlsx",
                                              body=KOREAN).encode())])

    doc = {d["doc_id"]: d for d in drive(client)["docs"]}["정리"]

    assert {f["name"] for f in doc["files"]} == {"설계서.pptx", "항목표.xlsx"}
    assert doc["bytes"] == len(BLOB) * 2
    for name in ("설계서.pptx", "항목표.xlsx"):
        response = client.get("/api/drive/정리/file", params={"name": name})
        assert response.status_code == 200, name


def test_a_file_not_linked_to_the_document_is_refused(client, studio, isolated_data):
    """`?name=` 으로 아무 파일이나 받아 갈 수 없어야 한다.

    인증이 없는 경로다. 이름만 바꿔 보내 다른 문서의 원본을 가져가는 길이 되면 안 된다.
    """
    send(client, [("남의자료.pptx", BLOB)])
    send(client, [("내문서.md", MD.format(title="내문서", body=KOREAN).encode())])

    assert client.get("/api/drive/내문서/file", params={"name": "남의자료.pptx"}).status_code == 404


# ── 화면이 서버보다 더 아는 척하지 않는가 ──────────────────────────────────


def test_the_stream_says_what_kind_of_answer_it_was(client, studio, isolated_data):
    """`done` 이 **무엇으로 답했는지** 알려줘야 한다.

    없으면 화면이 '검수된 답변' 과 '자료만' 과 '접수' 를 구분할 수 없다. 실제로 AI 스위치
    상태로만 배지를 골라서, 답변이 없어 자료만 보여 준 질문에 초록색 체크와 함께
    **'담당자 검수 답변'** 이 붙었다(2026-10-07). 본문은 바로 아래에서 "답변이 아직
    준비되지 않았습니다" 라고 말하고 있었다.
    """
    send(client, [("게시절차.md", MD.format(title="게시절차", body=KOREAN).encode())])

    body = client.get("/api/chat/stream", params={"question": KOREAN, "ai": "false"}).text

    assert "event: done" in body
    assert '"result_type"' in body, "done 이 result_type 을 알려주지 않습니다"


def test_the_screen_only_claims_review_for_a_reviewed_answer():
    """배지와 바닥글이 `result_type` 을 보고 정해져야 한다.

    초록 체크와 '담당자 검수 완료' 는 **사람이 확인했다**는 뜻이다. 자료만 찾아 준 것에
    붙이면 확인하지 않은 것을 확인했다고 말하게 된다 — 이 제품에서 가장 비싼 거짓말이다.
    """
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "app" / "static" / "drive.js").read_text(
        encoding="utf-8")

    assert "m.resultType === 'answer'" in source, (
        "화면이 result_type 을 보지 않고 검수 배지를 붙입니다"
    )
    # 바닥글도 같은 기준이어야 한다. **코드 줄 자체**를 본다 — 주석에도 같은 문구가 있어서
    # 둘레를 뭉뚱그려 보면 주석에 걸려 틀려도 통과한다.
    assert "m.resultType === 'answer') parts.push('담당자 검수 완료'" in source, (
        "'담당자 검수 완료' 가 result_type 과 무관하게 붙습니다"
    )
