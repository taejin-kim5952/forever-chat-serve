"""청킹 — 검색 품질이 여기서 갈린다.

자르는 규칙이 바뀌면 예외는 안 나고 **검색 품질만 조용히** 달라진다. 그래서 규칙을
테스트로 고정한다.
"""

import pytest

from app.ingestion.chunker import chunk_markdown_file, oversize_chunks

DOC = """---
title: API 등록
category: API 관리 > API 등록
---

이 문서는 API 등록 화면을 설명합니다. 도입부입니다.

## 등록 절차

API 그룹을 먼저 만들고 등록 화면으로 들어갑니다.

### 1) 필수 항목

API 명, Path, Method 세 가지입니다.

## 승인과 배포

저장하면 담당자에게 승인 요청이 갑니다.
"""


@pytest.fixture
def doc(tmp_path):
    path = tmp_path / "api-등록.md"
    path.write_text(DOC, encoding="utf-8")
    return path


def test_headings_split_into_sections(doc):
    """`##` 뿐 아니라 `###` 까지 자른다. 한 절에 항목이 여럿이면 벡터가 뭉개진다."""
    _, chunks = chunk_markdown_file(doc)

    sections = [c.metadata["section_title"] for c in chunks]
    assert "등록 절차" in sections
    assert "승인과 배포" in sections
    # `###` 은 부모 절 이름을 잃기 쉽다. 화면 카드에 "1)" 만 뜨면 무슨 얘긴지 알 수 없다.
    assert "등록 절차 > 1) 필수 항목" in sections


def test_lead_before_first_heading_is_kept(doc):
    """첫 헤딩 앞 도입부도 버리지 않는다 — 문서를 요약한 문단이 거기 있다."""
    _, chunks = chunk_markdown_file(doc)

    assert any("도입부입니다" in c.text for c in chunks)


def test_document_hash_changes_only_with_content(doc, tmp_path):
    """앞머리(frontmatter)만 바뀐 문서는 다시 색인하지 않아도 된다."""
    first, _ = chunk_markdown_file(doc)

    doc.write_text(DOC.replace("title: API 등록", "title: API 등록 안내"), encoding="utf-8")
    second, _ = chunk_markdown_file(doc)

    assert first == second


# ─────────────────────────────────────────────── 임베딩 입력 상한


def test_long_chunk_is_reported_not_cut(doc, isolated_data, monkeypatch):
    """상한을 넘겨도 **자르지 않고 알리기만** 한다.

    임계값을 잘못 잡아 멀쩡한 문서를 자르면 그게 더 나쁘다. 대응은 대개 "그 절에 소제목을
    넣는 것"이라 사람이 문서를 고쳐야 한다.
    """
    monkeypatch.setattr(isolated_data, "embed_warn_chars", 20)
    _, chunks = chunk_markdown_file(doc)

    over = oversize_chunks(chunks)

    assert over                                   # 넘친 것을 찾아내고
    assert all(len(c.text) > 20 for c in over)
    # 원본은 그대로다 — 자르지 않는다.
    assert all(len(c.text) > 0 for c in chunks)


def test_short_chunks_are_not_reported(doc, isolated_data, monkeypatch):
    monkeypatch.setattr(isolated_data, "embed_warn_chars", 5000)
    _, chunks = chunk_markdown_file(doc)

    assert oversize_chunks(chunks) == []


def test_check_can_be_turned_off(doc, isolated_data, monkeypatch):
    """0이면 확인하지 않는다 — 상한이 아주 큰 모델을 쓸 때."""
    monkeypatch.setattr(isolated_data, "embed_warn_chars", 0)
    _, chunks = chunk_markdown_file(doc)

    assert oversize_chunks(chunks) == []
