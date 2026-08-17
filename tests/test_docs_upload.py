"""폴더 업로드 — 파일 이름이 문서 ID가 되는 경로.

여기서 확인하는 것은 "여러 건이 들어간다"가 아니라 **하나가 잘못돼도 나머지가 들어가는지**,
그리고 **잘못 들어가지 않는지**(모드 게이팅·경로 문자·인코딩)다. 실사용에서 한 번에 40건을
올리는데, 조용히 건너뛴 파일이 생기면 며칠 뒤 "그 질문은 답을 못 한다"로만 드러난다.
"""

import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.ingestion.doc_upload import decode_text, doc_id_from_filename
from app.main import app

DOC = "---\ntitle: 문서 제목\n---\n\n# 제목\n\n## 절\n\n내용입니다.\n"


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


def upload(client, auth, files, *, overwrite=False):
    """(경로, 바이트) 목록을 화면과 같은 모양으로 보낸다."""
    payload = [("files", (Path(path).name, data, "text/markdown")) for path, data in files]
    payload += [("paths", (None, path)) for path, _ in files]
    return client.post(
        "/api/admin/docs/upload",
        files=payload,
        data={"overwrite": str(overwrite).lower()},
        headers=auth,
    )


# ─────────────────────────────────────────────────────── 파일 이름 → 문서 ID


@pytest.mark.parametrize("name,expected", [
    ("api-등록.md", "api-등록"),
    ("raw_docs/api-등록.md", "api-등록"),
    ("raw_docs\\하위\\포털-전체개요.markdown", "포털-전체개요"),
    ("a.tar.md", "a.tar"),
    ("  띄어  쓰기 .md", "띄어 쓰기"),
    # 경로 문자가 ID로 새면 문서 디렉터리 밖의 파일을 덮어쓸 수 있다.
    ("../../etc/passwd.md", "passwd"),
    # 앞의 '.' 은 떼어낸다 — 숨김 파일로 저장되면 목록(`*.md` 글롭)에는 뜨는데 탐색기에서 안 보인다.
    (".가이드.md", "가이드"),
])
def test_doc_id_comes_from_the_file_name(name, expected):
    assert doc_id_from_filename(name) == expected


def test_decomposed_korean_file_name_is_normalized():
    """macOS 에서 올라온 이름은 자모가 분리(NFD)돼 있다 — 같은 문서가 두 벌 생기는 원인."""
    assert doc_id_from_filename("가이드.md") == "가이드"


@pytest.mark.parametrize("raw,encoding", [("한글 문서", "utf-8"), ("한글 문서", "cp949")])
def test_cp949_files_are_read(raw, encoding):
    """메모장 ANSI 저장은 CP949 다. 깨진 채 색인되면 예외 없이 검색만 조용히 망가진다."""
    assert decode_text(raw.encode(encoding)) == raw


def test_undecodable_file_is_rejected_not_mangled():
    assert decode_text(b"\xff\xfe\x00" + bytes([0x80, 0x81]) * 3) is None


# ─────────────────────────────────────────────────────── 등록


def test_serve_mode_blocks_upload(client, auth):
    """운영에서 문서를 올리면 요청 처리 중에 전체 임베딩 비용을 치르게 된다."""
    response = upload(client, auth, [("api-등록.md", DOC.encode())])
    assert response.status_code == 403


def test_upload_requires_auth(client):
    response = client.post("/api/admin/docs/upload", files=[("files", ("a.md", b"# a", "text/markdown"))])
    assert response.status_code == 401


def test_folder_upload_registers_every_file(client, auth, studio, isolated_data):
    response = upload(client, auth, [
        ("문서폴더/api-등록.md", DOC.encode()),
        ("문서폴더/포털-전체개요.md", DOC.encode()),
        ("문서폴더/하위/설정파일-구조.md", DOC.encode()),
    ])

    assert response.status_code == 200
    body = response.json()
    assert (body["created"], body["skipped"], body["failed"]) == (3, 0, 0)
    assert all(item["chunks"] > 0 for item in body["items"])
    # 하위 폴더는 평평하게 들어간다 — raw_docs 는 한 겹이다.
    assert sorted(p.name for p in Path(isolated_data.raw_docs_dir).glob("*.md")) == [
        "api-등록.md", "설정파일-구조.md", "포털-전체개요.md",
    ]
    # 등록 즉시 검색에 잡혀야 한다. 파일만 들어가고 색인이 비면 "답을 못 하는 문서"가 된다.
    assert client.get("/api/admin/docs", headers=auth).json()[0]["chunk_count"] > 0


def test_non_document_files_are_skipped_with_a_reason(client, auth, studio, isolated_data):
    """폴더에는 이미지·`.DS_Store` 가 섞여 있다. 조용히 버리지 않고 사유를 돌려준다."""
    response = upload(client, auth, [
        ("문서폴더/api-등록.md", DOC.encode()),
        ("문서폴더/화면.png", b"\x89PNG\r\n"),
        ("문서폴더/.DS_Store", b"\x00\x01"),
    ])

    body = response.json()
    assert (body["created"], body["skipped"]) == (1, 2)
    assert all(item["reason"] for item in body["items"] if item["status"] == "skipped")
    assert not (Path(isolated_data.raw_docs_dir) / "화면.png").exists()


def test_existing_doc_is_kept_unless_overwrite_is_on(client, auth, studio, isolated_data):
    upload(client, auth, [("api-등록.md", DOC.encode())])

    again = upload(client, auth, [("api-등록.md", (DOC + "\n## 새 절\n\n새 내용\n").encode())]).json()
    assert again["skipped"] == 1
    assert "이미 있습니다" in again["items"][0]["reason"]
    assert "새 절" not in (Path(isolated_data.raw_docs_dir) / "api-등록.md").read_text(encoding="utf-8")

    forced = upload(client, auth, [("api-등록.md", (DOC + "\n## 새 절\n\n새 내용\n").encode())], overwrite=True).json()
    assert forced["updated"] == 1
    assert "새 절" in (Path(isolated_data.raw_docs_dir) / "api-등록.md").read_text(encoding="utf-8")


def test_same_file_name_in_two_subfolders_keeps_the_first(client, auth, studio, isolated_data):
    """폴더가 달라도 파일 이름이 같으면 문서 ID가 겹친다. 나중 것으로 덮으면 어느 쪽이
    들어갔는지 결과 표만 보고는 알 수 없다."""
    body = upload(client, auth, [
        ("가이드/api-등록.md", DOC.encode()),
        ("초안/api-등록.md", (DOC + "\n초안입니다\n").encode()),
    ]).json()

    assert (body["created"], body["skipped"]) == (1, 1)
    assert "가이드/api-등록.md" in body["items"][1]["reason"]
    assert "초안입니다" not in (Path(isolated_data.raw_docs_dir) / "api-등록.md").read_text(encoding="utf-8")


def test_broken_frontmatter_fails_alone(client, auth, studio, isolated_data):
    """앞머리 YAML 이 깨진 파일은 색인 단계에서 터진다. 파일을 쓰기 전에 걸러
    '목록에는 있는데 청크가 0인 문서'를 만들지 않는다."""
    body = upload(client, auth, [
        ("문서폴더/깨진문서.md", b"---\ntitle: [\n---\n\n\xeb\x82\xb4\xec\x9a\xa9\n"),
        ("문서폴더/api-등록.md", DOC.encode()),
    ]).json()

    assert (body["failed"], body["created"]) == (1, 1)
    assert not (Path(isolated_data.raw_docs_dir) / "깨진문서.md").exists()
    assert (Path(isolated_data.raw_docs_dir) / "api-등록.md").exists()


def test_crlf_file_still_splits_into_sections(client, auth, studio, isolated_data):
    """Windows 파일은 CRLF 로 올라온다. 줄바꿈이 망가지면 문서 하나가 통째로 한 청크가 된다."""
    body = upload(client, auth, [("문서.md", DOC.replace("\n", "\r\n").encode())]).json()

    assert body["items"][0]["chunks"] > 1
    assert "\r" not in (Path(isolated_data.raw_docs_dir) / "문서.md").read_text(encoding="utf-8")


def test_uploaded_doc_is_editable_and_deletable_afterwards(client, auth, studio):
    """올린 문서는 '새 문서'로 만든 것과 구분이 없어야 한다 — 같은 파일 한 벌이다."""
    upload(client, auth, [("api-등록.md", DOC.encode())])

    assert client.get("/api/admin/docs/api-등록", headers=auth).status_code == 200
    assert client.delete("/api/admin/docs/api-등록", headers=auth).status_code == 200
    assert client.get("/api/admin/docs/api-등록", headers=auth).status_code == 404


def test_too_many_files_in_one_request_are_refused(client, auth, studio):
    """묶음 크기는 화면이 지킨다. 서버도 막아야 화면을 거치지 않은 호출에서 타임아웃이 안 난다."""
    response = upload(client, auth, [(f"문서{i}.md", DOC.encode()) for i in range(21)])
    assert response.status_code == 400
