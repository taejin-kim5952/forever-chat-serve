"""로고 이미지 — 설치 전체에 하나.

### 왜 팩 안이 아니라 따로 두나

문서·카테고리·QA 는 팩(`packs/<프로젝트>/`)에 들어간다. **로고는 회사 것**이지 자료가
아니다. 팩에 넣으면 (1) 프로젝트를 바꿀 때마다 로고가 깜빡이고 (2) 팩을 반입할 때 만든
쪽의 로고가 따라와 받는 쪽 화면을 덮는다. 그래서 `brand_dir`(기본 `data/brand/`)에 둔다.

### 글자 로고는 그대로 둔다

이미지가 없으면 지금처럼 네모 안에 글자를 그린다(`APP_LOGO` 또는 프로필의 조직명).
이미지를 지우면 글자로 돌아간다 — **되돌릴 길이 있어야** 잘못 올린 그림에 갇히지 않는다.

### SVG 를 받는 이유와 그 대가

로고는 벡터로 받는 것이 가장 깨끗하다(일러스트레이터에서 바로 나온다). 다만 SVG 는 안에
스크립트를 품을 수 있다. 화면은 이 파일을 **`<img>` 로만** 띄우므로 그 안의 스크립트는
실행되지 않는다. 주소를 직접 열면 다르지만, 올리는 사람이 관리자뿐이라 거기까지 막지
않는다 — 막으려고 SVG 를 빼면 로고가 전부 래스터가 된다.
"""

import hashlib
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

from app.core.auth import require_admin
from app.core.config import get_settings
from app.core.logging import get_logger, log_event

logger = get_logger("api.brand")

router = APIRouter(prefix="/api", tags=["brand"])

# 확장자 → 내려줄 때 붙일 형식. 목록에 없는 것은 받지 않는다 — 로고 자리에 임의의 파일을
# 올릴 수 있으면 그것은 업로드 기능이지 로고 기능이 아니다.
ALLOWED = {
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
# 로고 하나에 이보다 크면 화면이 뜨는 데 시간이 걸린다. 벡터면 보통 수십 KB다.
MAX_BYTES = 1024 * 1024


def logo_path() -> Path | None:
    """지금 쓰이는 로고 파일. 없으면 `None`(= 글자 로고).

    확장자가 여럿일 수 있어 폴더를 훑는다. 두 개가 남아 있으면 **먼저 오는 것**을 쓰고,
    업로드할 때 옛 파일을 지우므로 평소에는 한 개뿐이다.
    """
    folder = Path(get_settings().brand_dir)
    if not folder.is_dir():
        return None
    for suffix in ALLOWED:
        found = folder / f"logo{suffix}"
        if found.exists():
            return found
    return None


def logo_url() -> str:
    """화면이 쓸 주소. 없으면 빈 문자열.

    파일 내용 해시를 붙인다 — 로고를 바꿨는데 브라우저가 옛 그림을 계속 보여주면
    "바꿨는데 안 바뀐다"가 된다. 캐시를 끄는 것보다 주소를 바꾸는 편이 싸다.
    """
    found = logo_path()
    if found is None:
        return ""
    digest = hashlib.sha256(found.read_bytes()).hexdigest()[:8]
    return f"/api/brand/logo?v={digest}"


@router.get("/brand/logo")
def get_logo() -> Response:
    """챗봇 화면이 쓰는 공개 경로. 인증이 없다 — 로고는 로그인 전에도 보여야 한다."""
    found = logo_path()
    if found is None:
        raise HTTPException(status_code=404, detail="등록된 로고가 없습니다.")
    return FileResponse(found, media_type=ALLOWED[found.suffix.lower()])


@router.post("/admin/brand/logo", dependencies=[Depends(require_admin)])
async def upload_logo(file: UploadFile = File(...)) -> dict:
    """로고를 올린다. **운영에서도 된다.**

    문서 편집을 studio 로 묶어 둔 것과 다르다 — 로고는 자료가 아니라 설정이고, 납품처가
    운영 화면에서 자기 로고를 올리는 것이 자연스럽다(설정 탭의 다른 값과 같은 성격).
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(
            status_code=400,
            detail=f"{' · '.join(sorted(ALLOWED))} 만 올릴 수 있습니다.",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")
    if len(data) > MAX_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"로고는 {MAX_BYTES // 1024}KB 까지입니다. 지금 {len(data) // 1024}KB 입니다.",
        )

    folder = Path(get_settings().brand_dir)
    folder.mkdir(parents=True, exist_ok=True)
    # 옛 로고를 먼저 지운다. 확장자가 다른 파일이 남아 있으면 둘 중 어느 것이 나갈지
    # 폴더 훑는 순서가 정한다 — "올렸는데 옛 그림이 나온다"가 된다.
    for suffix_old in ALLOWED:
        old = folder / f"logo{suffix_old}"
        if old.exists():
            old.unlink()
    (folder / f"logo{suffix}").write_bytes(data)

    log_event(logger, "brand logo saved", suffix=suffix, bytes=len(data))
    return {"logo_url": logo_url()}


@router.delete("/admin/brand/logo", dependencies=[Depends(require_admin)])
def delete_logo() -> dict:
    """로고를 지우고 글자 배지로 돌아간다."""
    found = logo_path()
    if found is None:
        raise HTTPException(status_code=404, detail="등록된 로고가 없습니다.")
    found.unlink()
    log_event(logger, "brand logo removed")
    return {"logo_url": ""}
