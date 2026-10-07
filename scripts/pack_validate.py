"""팩이 쓸 만한 상태인지 검사한다 (개발계획서 §3.5).

    python scripts/pack_validate.py packs/mcp-manager

기동 때 `load_pack()` 이 보는 것은 **조용히 나빠지는 것**뿐이다(엔진 판·임계값 역전).
여기서는 그보다 넓게 본다 — 팩을 만드는 사람이 반입 전에 스스로 확인하는 자리다.

### 오류와 경고를 가른다

  오류  이대로면 서비스가 성립하지 않는다. 종료 코드 1
  경고  돌기는 하는데 나중에 문제가 된다. 종료 코드 0

문서가 없으면 오류가 아니라 경고인 이유는, 팩을 만드는 첫 단계가 골격만 만들어 두고
문서를 모으는 것이기 때문이다 — 그때마다 실패하면 도구를 안 쓰게 된다.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.pack import ENGINE_VERSION, Pack, _as_tuple   # noqa: E402

# 청크가 이보다 길면 임베딩에서 뒷부분이 잘린다 (config.embed_warn_chars 와 같은 값).
CHUNK_WARN_CHARS = 1800


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def print(self, pack_dir: Path) -> int:
        print(f"팩 검사 — {pack_dir}")
        for message in self.errors:
            print(f"  [오류] {message}")
        for message in self.warnings:
            print(f"  [경고] {message}")
        if not self.errors and not self.warnings:
            print("  이상 없음")
        print()
        print(f"  오류 {len(self.errors)}건 · 경고 {len(self.warnings)}건")
        return 1 if self.errors else 0


def _read_json(path: Path, report: Report) -> object | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        report.error(f"{path.name} 를 읽을 수 없습니다: {exc}")
        return None


def check_manifest(pack_dir: Path, report: Report) -> Pack | None:
    raw = _read_json(pack_dir / "pack.json", report)
    if raw is None:
        # 기존 설치(data/)에는 매니페스트가 없다. 없다고 못 쓰는 팩은 아니다.
        report.warn("pack.json 이 없습니다. 프로필·임계값이 코드 기본값으로 갑니다.")
        return None
    if not isinstance(raw, dict):
        report.error("pack.json 이 객체가 아닙니다.")
        return None
    try:
        pack = Pack.model_validate(raw)
    except ValueError as exc:
        report.error(f"pack.json 형식이 맞지 않습니다: {exc}")
        return None

    if not pack.pack_id:
        report.error("pack_id 가 비어 있습니다.")
    if not pack.pack_version:
        report.warn("pack_version 이 없습니다. 어느 판이 배포됐는지 되짚을 수 없습니다.")
    if pack.engine_min_version and _as_tuple(pack.engine_min_version) > _as_tuple(ENGINE_VERSION):
        report.error(
            f"엔진 {pack.engine_min_version} 이상을 요구합니다 (지금 {ENGINE_VERSION})."
        )
    return pack


def check_categories(pack_dir: Path, report: Report) -> set[str]:
    """카테고리 ID 집합을 돌려준다. QA 가 가리키는 카테고리가 실제로 있는지 볼 때 쓴다."""
    raw = _read_json(pack_dir / "categories.json", report)
    if raw is None:
        report.error("categories.json 이 없습니다. 화면 주제 목록과 QA 분류가 성립하지 않습니다.")
        return set()

    ids: set[str] = set()
    groups = raw.get("groups", raw) if isinstance(raw, dict) else raw
    if not isinstance(groups, list):
        report.error("categories.json 의 구조를 알아볼 수 없습니다.")
        return ids

    for group in groups:
        if not isinstance(group, dict):
            continue
        for category in group.get("categories", []) or []:
            if not isinstance(category, dict):
                continue
            # 실제 파일의 키는 `category_id` 다. `id` 도 함께 보는 이유는 손으로 쓴 팩에서
            # 흔히 줄여 쓰기 때문이고, 둘 다 없으면 그 카테고리는 고를 수 없다.
            category_id = category.get("category_id") or category.get("id")
            if category_id:
                ids.add(str(category_id))
    if not ids:
        report.error("카테고리가 하나도 없습니다.")
    return ids


def check_qa(pack_dir: Path, category_ids: set[str], report: Report) -> None:
    raw = _read_json(pack_dir / "qa_index.json", report)
    if raw is None:
        report.warn("qa_index.json 이 없습니다. 모든 질문이 unresolved 로 떨어집니다.")
        return

    items = raw.get("items", raw) if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        report.error("qa_index.json 의 구조를 알아볼 수 없습니다.")
        return
    if not items:
        report.warn("검수된 QA 가 없습니다. 모든 질문이 unresolved 로 떨어집니다.")
        return

    unknown: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        category_id = item.get("category_id")
        if category_id and category_ids and category_id not in category_ids:
            unknown.add(str(category_id))
    if unknown:
        # 화면 주제 목록에서 고를 수 없는 답변이 된다 — 검색으로만 닿는다.
        report.error(f"카테고리에 없는 QA 분류: {', '.join(sorted(unknown))}")


def check_docs(pack_dir: Path, report: Report) -> None:
    """**엔진과 같은 청커로 나눠 본다.**

    처음에는 이 파일이 스스로 잘라 보았는데, 문서가 YAML front-matter 로 시작한다는 것을
    놓쳐 40건 전부에 "제목이 없다" 는 경고를 냈다. 전부에 뜨는 경고는 없느니만 못하다.
    검사기가 엔진과 다르게 짐작하면 이런 일이 반복되므로 `chunk_markdown_file` 을 그대로 부른다.
    """
    from app.ingestion.chunker import chunk_markdown_file

    docs_dir = pack_dir / "raw_docs"
    if not docs_dir.is_dir():
        report.warn("raw_docs/ 가 없습니다. 관련 문서를 보여줄 수 없습니다.")
        return
    # 하위 폴더도 훑는다 — 자동 생성분이 raw_docs/catalog/ 로 들어간다 (계획서 §3.2 · §5.4).
    files = sorted(docs_dir.rglob("*.md"))
    if not files:
        report.warn("문서가 없습니다.")
        return

    for path in files:
        try:
            _, chunks = chunk_markdown_file(path)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            report.error(f"{path.name} 을 읽을 수 없습니다: {exc}")
            continue

        if not chunks:
            report.warn(f"{path.name} 에서 만들어진 청크가 없습니다. 본문이 비었는지 보세요.")
            continue

        long_chunks = [c for c in chunks if len(c.text) > CHUNK_WARN_CHARS]
        if long_chunks:
            # 임베딩 상한(embed_max_tokens)에 걸려 뒷부분이 **예외 없이 버려진다.**
            titles = ", ".join(c.metadata.get("section_title", "?") for c in long_chunks[:2])
            report.warn(
                f"{path.name} 에 {CHUNK_WARN_CHARS}자를 넘는 청크가 {len(long_chunks)}건 있습니다"
                f" ({titles}) — 뒷부분이 잘립니다. 절을 더 쪼개 주세요."
            )


def main() -> int:
    if len(sys.argv) < 2:
        print("사용법: python scripts/pack_validate.py <팩 경로>")
        return 2
    pack_dir = Path(sys.argv[1])
    if not pack_dir.is_dir():
        print(f"팩 경로가 없습니다: {pack_dir}")
        return 2

    report = Report()
    check_manifest(pack_dir, report)
    category_ids = check_categories(pack_dir, report)
    check_qa(pack_dir, category_ids, report)
    check_docs(pack_dir, report)
    return report.print(pack_dir)


if __name__ == "__main__":
    raise SystemExit(main())
