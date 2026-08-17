"""폴더째 올린 파일을 원본 문서(`data/raw_docs/*.md`)로 등록한다.

탭 ⑤의 '새 문서'는 한 건씩 ID를 입력하고 본문을 붙여넣는 화면이다. 문서가 40개면 그 방식이
성립하지 않는다. 여기서는 **파일 이름이 곧 문서 ID** 다 — `api-등록.md` → `api-등록`.
사람이 ID를 다시 적지 않으니 오타로 같은 문서가 두 벌 생기지 않고, 폐쇄망에 `data/raw_docs/`
를 그대로 복사해 넣는 배포 방식과 결과가 정확히 같아진다.

**한 요청에 폴더 전체를 받지 않는다.** 문서 하나를 등록할 때마다 청킹 + 임베딩이 돌아 몇 초가
걸린다. 40건을 한 요청으로 받으면 (1) 진행 상황을 보여줄 방법이 없고 (2) 프록시 타임아웃에
걸린 뒤 무엇이 들어갔는지 알 수 없게 된다. 화면이 몇 건씩 나눠 보내고 이 모듈은 그 묶음만
처리한다 — 서버는 상태를 들고 있지 않다.

한 파일이 실패해도 나머지는 계속 등록한다. 40건 중 1건이 깨졌다고 전부 되돌리면, 고쳐서 다시
올릴 때 이미 들어간 39건을 또 처리하게 된다.
"""

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import frontmatter

from app.core.config import get_settings
from app.core.logging import get_logger, log_event

logger = get_logger("ingestion.doc_upload")

# 청커가 마크다운 기준으로 자르므로 텍스트 계열만 받는다. `.txt` 는 헤딩이 없으면
# 문단 단위로 잘린다(app/ingestion/chunker.py).
ALLOWED_SUFFIXES = {".md", ".markdown", ".txt"}

# 한 요청의 상한. 화면이 이 크기로 나눠 보낸다.
MAX_FILES_PER_REQUEST = 20
MAX_FILE_BYTES = 1_000_000

# 파일 이름에는 들어갈 수 있지만 문서 ID로는 못 쓰는 글자. 경로 문자가 섞이면
# `admin_docs._doc_path()` 가 400을 내므로 여기서 미리 '-' 로 바꾼다.
_UNSAFE_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


@dataclass
class UploadItem:
    """화면이 보낸 파일 한 건. `path` 는 하위 폴더를 포함한 표시용 경로다."""

    path: str
    data: bytes


@dataclass
class UploadResult:
    path: str
    doc_id: str = ""
    title: str = ""
    # created  : 새로 등록  · updated : 같은 ID를 덮어씀
    # skipped  : 등록하지 않음(사유 있음) · failed : 등록하려다 실패
    status: str = "skipped"
    chunks: int = 0
    reason: str = ""


def doc_id_from_filename(name: str) -> str:
    """`상위폴더/api-등록.md` → `api-등록`. 만들 수 없으면 빈 문자열."""
    base = PurePosixPath(name.replace("\\", "/")).name
    stem = Path(base).stem
    # macOS 에서 올라온 한글 이름은 자모가 분리(NFD)돼 있다. 그대로 두면 눈에는 같아 보이는데
    # 문자열 비교가 어긋나 `api-등록` 이 두 벌 생긴다.
    stem = unicodedata.normalize("NFC", stem)
    stem = _UNSAFE_CHARS.sub("-", stem)
    stem = re.sub(r"\s+", " ", stem)
    # 앞의 '.' 은 숨김 파일, 뒤의 '.' 과 공백은 Windows 가 파일 이름으로 받지 않는다.
    return stem.strip(" .")


def decode_text(data: bytes) -> str | None:
    """사내 PC에서 만든 문서는 UTF-8 이 아닐 수 있다(메모장 ANSI 저장 = CP949).

    되는 대로 바꿔 넣으면 글자가 깨진 채 색인돼 **예외 없이 검색 품질만** 무너진다.
    확실히 읽히는 인코딩이 없으면 그 파일만 건너뛴다.
    """
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        candidates = ("utf-16",)   # 메모장의 '유니코드' 저장
    else:
        candidates = ("utf-8-sig", "cp949")
    for encoding in candidates:
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return None


def _normalize_newlines(text: str) -> str:
    """줄바꿈을 `\\n` 하나로 맞춘다.

    Windows 에서 만든 파일은 CRLF 로 올라온다. 그대로 텍스트 모드로 쓰면 `\\n` 이 다시
    `\\r\\n` 으로 바뀌어 `\\r\\r\\n` 이 된다. 청커가 헤딩을 `^#{2,3} ` 로 찾으므로 줄바꿈이
    망가지면 문서 하나가 통째로 한 청크가 된다.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")


def register_uploads(items: list[UploadItem], *, index, overwrite: bool = False) -> list[UploadResult]:
    """묶음 하나를 등록한다. `index` 는 `DocIndex` — 여기서 싱글턴을 잡지 않아 테스트가 쉽다."""
    docs_dir = Path(get_settings().raw_docs_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)

    results: list[UploadResult] = []
    seen: dict[str, str] = {}   # doc_id → 이 묶음에서 먼저 온 파일 경로

    for item in items:
        result = UploadResult(path=item.path)
        results.append(result)

        suffix = Path(PurePosixPath(item.path.replace("\\", "/")).name).suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            result.reason = "문서 파일이 아닙니다 (.md · .markdown · .txt 만 등록합니다)"
            continue

        doc_id = doc_id_from_filename(item.path)
        if not doc_id:
            result.reason = "파일 이름에서 문서 ID를 만들 수 없습니다"
            continue
        result.doc_id = doc_id

        if not item.data:
            result.reason = "빈 파일입니다"
            continue
        if len(item.data) > MAX_FILE_BYTES:
            result.reason = f"파일이 너무 큽니다 (최대 {MAX_FILE_BYTES // 1000}KB)"
            continue

        # 하위 폴더가 달라도 파일 이름이 같으면 문서 ID가 겹친다. 먼저 온 쪽만 넣는다 —
        # 나중 것으로 덮으면 어느 파일이 들어갔는지 결과 표만 보고는 알 수 없다.
        if doc_id in seen:
            result.reason = f"이 묶음의 '{seen[doc_id]}' 와 문서 ID가 같습니다"
            continue
        seen[doc_id] = item.path

        text = decode_text(item.data)
        if text is None:
            result.reason = "글자 인코딩을 알 수 없습니다 (UTF-8 로 저장해 주세요)"
            continue
        text = _normalize_newlines(text)

        # 앞머리(frontmatter)가 깨져 있으면 색인 단계에서 터진다. 파일을 쓰기 **전에** 걸러야
        # 색인 안 된 문서가 목록에 남지 않는다.
        try:
            post = frontmatter.loads(text)
        except Exception as exc:   # noqa: BLE001 — YAML 파서가 던지는 예외 종류가 넓다
            result.status = "failed"
            result.reason = f"문서 앞머리(--- 사이 YAML)를 읽지 못했습니다: {exc}"
            continue
        result.title = str(post.get("title") or doc_id)

        path = docs_dir / f"{doc_id}.md"
        exists = path.exists()
        if exists and not overwrite:
            result.reason = "같은 ID의 문서가 이미 있습니다 (덮어쓰기를 켜면 갱신합니다)"
            continue

        try:
            path.write_text(text, encoding="utf-8", newline="\n")
        except OSError as exc:
            result.status = "failed"
            result.reason = f"파일을 저장하지 못했습니다: {exc}"
            continue

        # 파일 먼저, 벡터 다음. 색인이 실패해도 원본은 남는다 — 재색인으로 복구할 수 있다.
        try:
            result.chunks = index.ingest_file(path, force=True)
        except Exception as exc:   # noqa: BLE001 — 임베딩 서버가 죽으면 여기서 걸린다
            result.status = "failed"
            result.reason = f"파일은 저장했지만 색인에 실패했습니다 (재색인으로 복구): {exc}"
            log_event(logger, "doc upload indexing failed", doc_id=doc_id, error=str(exc))
            continue

        result.status = "updated" if exists else "created"

    log_event(
        logger, "docs uploaded",
        files=len(items),
        created=sum(1 for r in results if r.status == "created"),
        updated=sum(1 for r in results if r.status == "updated"),
        skipped=sum(1 for r in results if r.status == "skipped"),
        failed=sum(1 for r in results if r.status == "failed"),
    )
    return results
