"""원본 파일 보관 — 사람이 올린 `.pptx` · `.pdf` · `.xlsx` 를 그대로 두고 내려준다.

### 왜 원본과 `.md` 를 나누는가

AI 가 읽는 것은 사람이 정리한 `.md` 하나뿐이다. 원본은 **색인하지 않는다.** hwp·ppt 에서
본문을 뽑는 파서를 넣으면 폐쇄망 반입물이 커지고, 더 나쁜 것은 추출 품질이 떨어졌을 때
**예외 없이 답변 품질만** 조용히 나빠진다는 점이다. 사람이 읽을 원본과 AI 가 읽을 요약을
따로 받는 쪽이 이 제품의 전제(미리 검수해 둔 답변만 내보낸다)에 맞다.

그래서 답변에 붙는 참고 자료는 두 가지 일을 한다 — 근거는 `.md`, 내려받는 것은 원본.

### 짝을 맺는 두 가지 길

    raw_docs/mcp-개념-개요.md          ← 색인된다
    raw_docs/files/mcp-개념-개요.pptx   ← ① 이름이 같으면 자동으로 묶인다

① **파일 이름이 같으면** 자동이다. `doc_upload.py` 가 이미 "파일 이름이 곧 문서 ID" 로
돌고 있어서, 두 파일을 함께 끌어다 놓기만 하면 된다. 짝을 짓는 화면이 필요 없다.

② **앞머리에 적어도 된다.** 실제 원본 이름은 `2026_하반기_API가이드_v3.pptx` 처럼 생겼고,
본문은 읽기 좋게 `api-등록-절차.md` 로 쪼개 쓴다. 그럴 때 ①로는 맺어지지 않는다.

    ---
    title: API 등록 · 배포 절차
    source_files: [2026_하반기_API가이드_v3.pptx, 등록항목_정리.xlsx]
    ---

**본문 하나가 원본 여럿을 가리킬 수 있고, 원본 하나를 본문 여럿이 나눠 가질 수도 있다.**
긴 발표자료를 주제별로 쪼개 쓰는 것이 흔하기 때문이다. 그래서 '한 문서에 원본 하나' 가
아니라 **목록**으로 다룬다.

어느 본문도 가리키지 않는 원본은 **주인 없는 자료**로 목록에 남는다(`색인 안 됨`).
숨기면 "올렸는데 AI가 모른다"의 원인을 사람이 짚을 수 없다.
"""

import unicodedata
from pathlib import Path

import frontmatter

from app.core.config import get_settings
from app.core.logging import get_logger, log_event

logger = get_logger("ingestion.doc_files")

# 받는 원본 확장자. 화면의 `문서 종류` 필터가 이 분류를 그대로 쓴다.
# 실행 파일(.exe · .bat · .js …)은 받지 않는다 — 사내 공유 폴더가 전달 경로가 되면 안 된다.
KIND_SUFFIXES: dict[str, set[str]] = {
    "pdf": {".pdf"},
    "ppt": {".ppt", ".pptx", ".key", ".odp"},
    "doc": {".doc", ".docx", ".rtf", ".odt"},
    "xls": {".xls", ".xlsx", ".csv", ".ods"},
    "hwp": {".hwp", ".hwpx"},
    "zip": {".zip", ".7z", ".tar", ".gz"},
    "img": {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ai", ".psd"},
}
ALLOWED_SUFFIXES: set[str] = {s for group in KIND_SUFFIXES.values() for s in group}

# 원본은 `.md` 와 크기가 다른 세계다 — 발표자료 한 건이 수십 MB 다.
MAX_ORIGINAL_BYTES = 50_000_000


def kind_of(suffix: str) -> str:
    """`.pptx` → `ppt`. 화면의 아이콘·필터가 쓰는 분류. 모르는 것은 `etc`."""
    suffix = suffix.lower()
    for kind, suffixes in KIND_SUFFIXES.items():
        if suffix in suffixes:
            return kind
    return "etc"


def files_dir() -> Path:
    """원본을 두는 곳. `raw_docs/` 아래에 둬서 **폐쇄망 배포가 폴더 복사 하나**로 끝난다.

    경로 설정을 새로 만들지 않은 것은 일부러다 — 설정이 하나 늘면 `tests/conftest.py` 의
    `overrides` 에 넣는 것을 잊은 날 테스트가 실제 `data/` 를 건드린다(CLAUDE.md).
    """
    return Path(get_settings().raw_docs_dir) / "files"


def _key(name: str) -> str:
    """이름 비교용. 앞머리에 적은 이름과 실제 파일 이름이 **보기에는 같은데** 안 맞는 일을
    막는다 — macOS 에서 올라온 한글은 자모가 분리(NFD)돼 있고, 사람은 대소문자를 섞어 적는다.
    """
    return unicodedata.normalize("NFC", (name or "").strip()).lower()


def declared(path: Path) -> list[str]:
    """본문 앞머리가 가리키는 원본 이름들. `source_files` 또는 `source_file`.

    앞머리가 깨진 파일 하나가 목록 전체를 막으면 안 되므로, 못 읽으면 빈 목록이다.
    """
    try:
        post = frontmatter.load(path)
    except Exception:  # noqa: BLE001 - YAML 파서가 던지는 예외 종류가 넓다
        return []
    raw = post.get("source_files", post.get("source_file", []))
    if isinstance(raw, str):
        raw = [raw]
    return [str(x).strip() for x in (raw or []) if str(x).strip()]


def pairs() -> tuple[dict[str, list[Path]], dict[str, Path]]:
    """`(doc_id → 원본들, 주인 없는 원본)`.

    목록 화면이 한 번에 쓴다. 문서마다 앞머리를 다시 읽지 않도록 여기서 한 바퀴만 돈다.
    """
    everything = {p.name: p for p in _files()}
    by_key = {_key(name): path for name, path in everything.items()}
    # 확장자를 안 적고 이름만 적는 경우도 받는다 — 사람이 `source_files: [API가이드]` 라고
    # 적는 쪽이 자연스럽다. 같은 이름의 `.pptx` 와 `.pdf` 가 함께 있을 수 있으므로 **목록**이다.
    by_stem: dict[str, list[Path]] = {}
    for path in everything.values():
        by_stem.setdefault(_key(path.stem), []).append(path)

    docs_dir = Path(get_settings().raw_docs_dir)
    out: dict[str, list[Path]] = {}
    claimed: set[str] = set()
    for md in (sorted(docs_dir.glob("*.md")) if docs_dir.is_dir() else []):
        found: list[Path] = []
        # ① 이름이 같은 원본 (`.pptx` 와 `.pdf` 가 함께 있으면 둘 다)
        found.extend(by_stem.get(_key(md.stem), []))
        # ② 앞머리가 가리키는 원본
        for name in declared(md):
            exact = by_key.get(_key(name))
            matches = [exact] if exact is not None else by_stem.get(_key(Path(name).stem), [])
            for path in matches:
                if path not in found:
                    found.append(path)
        if found:
            out[md.stem] = found
            claimed.update(p.name for p in found)

    loose = {name: path for name, path in everything.items() if name not in claimed}
    return out, loose


def find(doc_id: str) -> Path | None:
    """이 문서의 **대표** 원본. 여럿이면 첫 번째. 없으면 `None`.

    대표를 정하는 이유: 목록의 아이콘과 내려받기 버튼은 하나씩만 둘 수 있다. 나머지는
    자료 원문 모달에서 전부 보여 준다.
    """
    found = pairs()[0].get(doc_id)
    return found[0] if found else None


def find_all(doc_id: str) -> list[Path]:
    return pairs()[0].get(doc_id, [])


def find_named(doc_id: str, name: str) -> Path | None:
    """이 문서에 묶인 원본 중 이름이 맞는 것. **묶이지 않은 파일은 돌려주지 않는다** —
    이름만 바꿔 보내면 다른 문서의 원본이 나가는 길이 된다."""
    for path in find_all(doc_id):
        if _key(path.name) == _key(name):
            return path
    return None


def _files() -> list[Path]:
    directory = files_dir()
    if not directory.is_dir():
        return []
    return [p for p in sorted(directory.iterdir()) if p.is_file()]


def exists(name: str) -> bool:
    """같은 이름의 원본이 이미 보관돼 있는가. **덮어쓰기 판정에만** 쓴다."""
    return any(_key(p.name) == _key(name) for p in _files())


def save(doc_id: str, suffix: str, data: bytes) -> Path:
    """원본을 **올린 이름 그대로** 넣는다.

    형제 파일을 지우지 않는다. 본문 하나가 원본 여럿을 가리킬 수 있게 되면서(`pairs()`)
    `가이드.pptx` 와 `가이드.pdf` 가 함께 있는 것이 정상이 됐다. 예전처럼 조용히 지우면
    다른 본문이 가리키던 원본이 사라진다.
    """
    directory = files_dir()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{doc_id}{suffix.lower()}"
    target.write_bytes(data)
    return target


def remove_file(name: str) -> bool:
    """원본 한 개를 지운다(목록에서 고른 것)."""
    for path in _files():
        if _key(path.name) == _key(name):
            path.unlink(missing_ok=True)
            log_event(logger, "original removed", name=path.name)
            return True
    return False


def remove(doc_id: str) -> bool:
    """문서를 지울 때 원본도 함께 지운다. 남기면 목록에 '색인 안 됨' 으로 되살아난다.

    **다른 본문도 가리키는 원본은 남긴다.** 긴 발표자료를 여러 본문이 나눠 가질 수 있어서,
    한쪽을 지웠다고 원본을 없애면 남은 본문의 내려받기가 조용히 깨진다.
    """
    linked, loose = pairs()
    mine = linked.get(doc_id) or [p for name, p in loose.items() if _key(p.stem) == _key(doc_id)]
    if not mine:
        return False
    shared = {p.name for other, paths in linked.items() if other != doc_id for p in paths}
    for path in mine:
        if path.name not in shared:
            path.unlink(missing_ok=True)
    return True


def remove_orphans(paths: list[Path]) -> int:
    """어느 본문도 더는 가리키지 않는 원본을 지운다.

    본문을 지운 **뒤에** 부른다. 지우기 전에 묶여 있던 목록을 미리 잡아 두고 넘겨야 한다 —
    본문이 사라지고 나면 무엇이 묶여 있었는지 알 길이 없다.
    """
    linked, _ = pairs()
    still = {p.name for group in linked.values() for p in group}
    removed = 0
    for path in paths:
        if path.name not in still and path.exists():
            path.unlink(missing_ok=True)
            removed += 1
    return removed


def listing() -> dict[str, Path]:
    """`파일 이름` → 경로. 보관 중인 원본 전부."""
    return {p.name: p for p in _files()}


def total_bytes() -> int:
    """보관 중인 원본 용량 합계. 사이드바의 `N GB 사용` 이 이 값이다."""
    return sum(p.stat().st_size for p in listing().values())
