"""문서에 들어가는 그림 — 출처 모달에서 도식을 보여주는 경로.

**답변에는 그림을 넣지 않는다.** 화면 캡처나 도식을 답변마다 박으면 제품 UI가 바뀔 때
그 그림을 인용한 답변을 전부 찾아 고쳐야 한다. 그림은 원본 문서 한 곳에만 두고 사용자는
출처 문서에서 본다 — 갱신 지점이 하나로 모인다.

여기서 지키는 것 셋:
- 저장은 원문, **임베딩은 그림 표기를 걷어낸 것**(파일 경로가 검색 벡터를 흐리지 않게)
- 출처 배지는 문서 **전체**를 연다(도식이 아래쪽 절에 있어도 보여야 한다)
- 그림 경로가 `raw_docs/img/` 밖으로 나가지 못한다(인증 없는 공개 경로다)
"""

from pathlib import Path

from fastapi.testclient import TestClient

from app.core import config
from app.ingestion.chunker import excerpt, strip_media
from app.ingestion.doc_index import DocIndex
from app.main import app


def raw_dir() -> Path:
    """**`from ... import get_settings` 로 가져오지 않는다.** 그러면 conftest 의 monkeypatch
    가 바꾸기 전의 원본을 붙잡게 되어 실제 `data/` 를 가리킨다(conftest 상단 참고)."""
    return Path(config.get_settings().raw_docs_dir)

SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
    '<rect width="10" height="10" fill="#309ba2"/></svg>'
)

DOC = """---
title: 가입 절차
category: 계정
url: /join
updated: 2026-08-17
---

# 가입 절차

가입만으로는 끝나지 않습니다.

## 전체 흐름

![가입 절차 흐름도](img/join.svg)

승인은 사람이 직접 처리합니다.

## 단계

| # | 단계 |
|---|---|
| 1 | 회원가입 |
"""


def _write_doc() -> Path:
    raw = raw_dir()
    (raw / "img").mkdir(parents=True, exist_ok=True)
    (raw / "img" / "join.svg").write_text(SVG, encoding="utf-8")
    path = raw / "가입-절차.md"
    path.write_text(DOC, encoding="utf-8")
    return path


# ── 임베딩 전에 걷어내기 ──────────────────────────────────────────────────────


def test_strip_media_keeps_the_alt_text():
    """대체 텍스트는 남긴다 — '가입 절차 흐름도' 자체가 좋은 검색 재료다."""
    assert strip_media("앞 ![가입 절차 흐름도](img/join.svg) 뒤") == "앞 가입 절차 흐름도 뒤"


def test_strip_media_drops_the_path():
    """`img/join.svg` 는 사람이 검색창에 치지 않는 문자열이다. 벡터를 흐리기만 한다."""
    assert "img/join.svg" not in strip_media("![도식](img/join.svg)")


def test_excerpt_has_no_image_markup():
    """관련 문서 카드 발췌에 `![...]` 가 찍히면 그대로 사용자에게 보인다."""
    assert "![" not in excerpt("![가입 절차 흐름도](img/join.svg)\n\n승인은 사람이 처리합니다.")


def test_stored_text_keeps_the_image_but_embedding_does_not(monkeypatch):
    """저장은 원문, 임베딩은 걷어낸 것 — 화면은 그려야 하고 벡터는 깨끗해야 한다."""
    _write_doc()
    index = DocIndex()

    embedded: list[str] = []
    original = index.embedder.embed_batch
    monkeypatch.setattr(
        index.embedder, "embed_batch",
        lambda texts, task="similarity": embedded.extend(texts) or original(texts, task=task),
    )
    index.ingest_file(raw_dir() / "가입-절차.md", force=True)

    assert any("![" in t for t in [index.get_chunk("가입-절차::1")["text"]]), "저장된 원문에 그림이 없습니다"
    assert not any("img/join.svg" in t for t in embedded), "임베딩에 파일 경로가 섞였습니다"


# ── 출처 배지가 여는 문서 ────────────────────────────────────────────────────


def test_source_badge_opens_the_whole_document():
    """예전에는 첫 청크(도입부)만 열렸다. 그러면 아래쪽 절의 도식을 볼 방법이 없다."""
    _write_doc()
    DocIndex().ingest_file(raw_dir() / "가입-절차.md", force=True)

    body = TestClient(app).get("/api/docs/가입-절차").json()["text"]
    assert "![가입 절차 흐름도](img/join.svg)" in body
    assert "## 단계" in body, "문서 아래쪽 절이 빠졌습니다"


def test_related_card_still_opens_the_matched_chunk():
    """관련 문서 카드는 '왜 이 문서가 나왔나'가 질문이라 실제로 걸린 절을 열어야 한다."""
    _write_doc()
    DocIndex().ingest_file(raw_dir() / "가입-절차.md", force=True)

    chunk = TestClient(app).get("/api/docs/chunk/가입-절차::1").json()
    assert chunk["section"] == "전체 흐름"
    assert "## 단계" not in chunk["text"]


# ── 그림 서빙 ────────────────────────────────────────────────────────────────


def test_image_is_served():
    _write_doc()
    response = TestClient(app).get("/api/docs/img/join.svg")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")


def test_missing_image_is_404():
    _write_doc()
    assert TestClient(app).get("/api/docs/img/없는그림.svg").status_code == 404


def test_image_route_refuses_path_traversal():
    """인증이 없는 경로다. 여기가 뚫리면 서버 파일이 그대로 나간다."""
    _write_doc()
    secret = raw_dir().parent / "qa_index.json"
    secret.write_text("{}", encoding="utf-8")
    client = TestClient(app)

    for attack in ["../qa_index.json", "..%2Fqa_index.json", "....//qa_index.json"]:
        assert client.get(f"/api/docs/img/{attack}").status_code == 404, attack


def test_image_route_refuses_other_file_types():
    """확장자 흰 목록. `.md` 를 내주면 검수 전 초안까지 열람 대상이 된다."""
    raw = raw_dir()
    (raw / "img").mkdir(parents=True, exist_ok=True)
    (raw / "img" / "leak.md").write_text("비밀", encoding="utf-8")

    assert TestClient(app).get("/api/docs/img/leak.md").status_code == 404
