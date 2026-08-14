"""마크다운 문서를 검색 단위(청크)로 자른다.

`##` 뿐 아니라 **`###` 까지 쪼갠다.** 이전 프로젝트는 `##` 단위였는데, 한 절에 항목 설명이
여러 개 들어 있으면 청크가 3천 자에 달했다. 그러면 두 가지가 나빠진다.

- 검색: 한 청크 안에 주제가 여럿 섞여 벡터가 뭉개진다. "권한그룹"을 물었는데 그 문단이
  들어 있는 거대한 절이 다른 절과 비슷한 점수로 나온다.
- 화면: `related_docs` 카드에 발췌 2~3줄을 보여줘야 하는데, 어느 부분을 잘라야 할지 모른다.

대신 `###` 청크는 부모 `##` 제목을 잃어버리기 쉬우므로 `section_path` 에 `부모 > 자식` 으로
남긴다. 화면 카드의 섹션명이 "1)" 같은 조각으로 뜨는 것을 막기 위한 것이다.
"""

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

import frontmatter

_HEADING = re.compile(r"^(#{2,3})[ \t]+(\S.*)$", flags=re.MULTILINE)


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    text: str
    metadata: dict = field(default_factory=dict)


def _doc_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _split_sections(body: str) -> list[tuple[str, str]]:
    """`(섹션 경로, 본문)` 목록. 헤딩이 없으면 문단(빈 줄) 단위로 자른다."""
    matches = list(_HEADING.finditer(body))
    if not matches:
        paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
        return [("", p) for p in paragraphs]

    sections: list[tuple[str, str]] = []

    # 첫 헤딩 앞의 도입부도 버리지 않는다 — 문서 전체를 요약한 한두 문단이 여기 있다.
    lead = body[: matches[0].start()].strip()
    if lead:
        sections.append(("", lead))

    parent = ""
    for idx, match in enumerate(matches):
        level = len(match.group(1))
        title = match.group(2).strip()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        text = body[match.start(): end].strip()
        if level == 2:
            parent = title
            path = title
        else:
            path = f"{parent} > {title}" if parent else title
        sections.append((path, text))
    return sections


def chunk_markdown_file(path: Path) -> tuple[str, list[Chunk]]:
    """마크다운 문서를 frontmatter 메타데이터를 보존한 채 섹션 단위 청크로 분할.

    Returns: (doc_hash, chunks)
    """
    post = frontmatter.load(path)
    doc_id = path.stem
    doc_hash = _doc_hash(post.content)

    base_metadata = {
        "doc_id": doc_id,
        "title": post.get("title", doc_id),
        "category": post.get("category", ""),
        "url": post.get("url", ""),
        "updated": str(post.get("updated", "")),
        "source_file": path.name,
    }

    chunks: list[Chunk] = []
    for idx, (section_path, text) in enumerate(_split_sections(post.content)):
        chunks.append(
            Chunk(
                chunk_id=f"{doc_id}::{idx}",
                doc_id=doc_id,
                text=text,
                metadata={
                    **base_metadata,
                    "section_title": section_path or base_metadata["title"],
                    "chunk_index": idx,
                },
            )
        )
    return doc_hash, chunks


def excerpt(text: str, max_chars: int = 160) -> str:
    """`related_docs` 카드에 넣을 발췌. 헤딩 줄과 마크다운 기호를 걷어낸 본문 앞부분."""
    lines = [
        line.strip() for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    plain = " ".join(lines)
    plain = re.sub(r"[*`>]|^\s*[-*]\s+", "", plain).strip()
    if len(plain) <= max_chars:
        return plain
    return plain[:max_chars].rstrip() + "…"
