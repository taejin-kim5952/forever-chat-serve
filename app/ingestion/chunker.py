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

from app.core.config import get_settings
from app.core.logging import log_event

_HEADING = re.compile(r"^(#{2,3})[ \t]+(\S.*)$", flags=re.MULTILINE)

# `![대체텍스트](img/파일.svg)` — 문서의 그림.
_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def strip_media(text: str) -> str:
    """벡터로 만들기 **전에** 그림 표기를 걷어낸다. 대체 텍스트는 남긴다.

    걷어내지 않으면 두 가지가 조용히 나빠진다.

    - **검색**: `img/가입-절차-흐름도.svg` 같은 파일 경로가 그대로 임베딩에 섞인다. 사람이
      쓰지 않는 문자열이라 벡터를 흐리기만 한다.
    - **생성**: 청크가 그대로 프롬프트에 들어가므로 모델이 `![...](...)` 를 답변에 베껴 쓴다.
      `[[문서ID]]` 로 이미 겪은 것과 같은 종류다(`app/studio/generate.py` 의 `clean_answer`).

    대체 텍스트는 남긴다 — "가입 절차 흐름도" 라는 말 자체가 그 절이 무엇에 관한 것인지
    알려주는 좋은 검색 재료다. **저장되는 원문은 건드리지 않는다**: 화면은 그림을 그려야 한다.
    """
    return _IMAGE.sub(lambda m: m.group(1), text)


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


def oversize_chunks(chunks: list[Chunk], log_to=None) -> list[Chunk]:
    """임베딩 모델의 입력 상한을 넘길 만한 조각을 찾아 남긴다.

    모델마다 한 번에 읽는 길이가 정해져 있고(`bge-m3` 8192 · `embeddinggemma` 2048 토큰),
    **넘치면 예외 없이 뒷부분이 버려진 채** 벡터가 만들어진다. 그 뒷부분을 묻는 질문은 영영
    걸리지 않는데, 화면에는 문서가 멀쩡히 색인된 것으로 보인다. 1차의 "컨텍스트 창 초과로
    조용히 잘림"과 같은 종류다.

    자르거나 막지 않는다. **로그로 알리기만 한다** — 임계값을 잘못 잡아 멀쩡한 문서를 자르면
    그게 더 나쁘고, 대응은 대개 "그 절에 소제목을 넣는 것"이라 사람이 문서를 고쳐야 한다.
    기준은 `.env` 의 `EMBED_WARN_CHARS` 이며, 한국어는 대략 1자 ≈ 1토큰이다.
    """
    limit = get_settings().embed_warn_chars
    if limit <= 0:
        return []

    over = [c for c in chunks if len(c.text) > limit]
    if over and log_to is not None:
        log_event(
            log_to, "chunk may exceed embedding input limit",
            limit_chars=limit, count=len(over),
            worst=f"{over[0].doc_id} :: {over[0].metadata.get('section_title', '')}",
            worst_chars=max(len(c.text) for c in over),
        )
    return over


def excerpt(text: str, max_chars: int = 160) -> str:
    """`related_docs` 카드에 넣을 발췌. 헤딩 줄과 마크다운 기호를 걷어낸 본문 앞부분."""
    lines = [
        line.strip() for line in strip_media(text).splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    plain = " ".join(lines)
    plain = re.sub(r"[*`>]|^\s*[-*]\s+", "", plain).strip()
    if len(plain) <= max_chars:
        return plain
    return plain[:max_chars].rstrip() + "…"
