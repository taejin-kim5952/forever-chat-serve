import re
from contextlib import asynccontextmanager
from html import escape
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.admin_analytics import router as admin_analytics_router
from app.api import project_context
from app.api.admin_auth import router as admin_auth_router
from app.api.brand import logo_url, router as brand_router
from app.api.chat_stream import router as chat_stream_router
from app.api.drive import router as drive_router
from app.api.library import router as library_router
from app.api.admin_categories import router as admin_categories_router
from app.api.admin_docs import router as admin_docs_router
from app.api.admin_jobs import router as admin_jobs_router
from app.api.admin_pipeline import router as admin_pipeline_router
from app.api.admin_projects import router as admin_projects_router
from app.api.admin_qa import router as admin_qa_router
from app.api.admin_questions import router as admin_questions_router
from app.api.admin_settings import router as admin_settings_router
from app.api.ask import router as ask_router
from app.api.health import router as health_router
from app.api.studio_eval import router as studio_eval_router
from app.api.studio_ask import router as studio_ask_router
from app.api.studio_generate import router as studio_generate_router
from app.core.auth import warn_if_default_password
from app.core.config import get_settings, is_studio
from app.core.logging import get_logger, log_event, setup_logging
from app.core.pack import load_pack
from app.ingestion.embedder import MODEL_FILE, TOKENIZER_FILE
from app.core.profile import load_profile

setup_logging()
logger = get_logger("main")

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    # 팩이 잘못됐으면 여기서 죽는다. 잡지 않는 것이 의도다 —
    # 잘못된 팩으로 조용히 서비스되는 것보다 안 뜨는 편이 낫다 (계획서 §3.5).
    pack = load_pack()
    log_event(
        logger, "server started",
        mode=settings.app_mode,
        embed_model=settings.embed_onnx_dir,
        qa_collection=settings.chroma_qa_collection,
        pack_id=pack.pack_id or "(매니페스트 없음)",
        pack_version=pack.pack_version,
        pack_dir=settings.pack_dir,
        var_dir=settings.var_dir,
    )
    warn_if_default_password()
    warn_if_embed_model_missing()
    yield


def warn_if_embed_model_missing() -> None:
    """모델 파일이 없으면 **모든 질문이 unresolved** 가 된다. 기동 로그에서 알려준다.

    기동 자체를 막지는 않는다 — 화면과 관리자 API 는 모델 없이도 떠야 하고(문서 편집·검수),
    무엇보다 서버가 안 뜨면 사람이 원인을 볼 곳이 없다.
    """
    model_dir = Path(get_settings().embed_onnx_dir)
    missing = [f for f in (MODEL_FILE, TOKENIZER_FILE) if not (model_dir / f).exists()]
    if missing:
        log_event(
            logger, "embedding model files missing — all questions will be unresolved",
            model_dir=str(model_dir), missing=missing,
            fix="python scripts/fetch_onnx_model.py",
        )


# /docs 의 제목. OpenAPI 메타데이터라 기동 시 한 번만 정해진다 — 프로필을 바꾸면 재시작해야
# 여기까지 반영된다(화면은 매 요청 반영된다).
app = FastAPI(
    title=f"{load_profile().service_name} (openapi-chat-serve)", version="0.1.0", lifespan=lifespan,
)

app.include_router(ask_router)
# 로그인 라우터는 인증을 걸지 않는다 — 로그인하기 전에 부르는 경로다.
# 프로젝트 컨텍스트는 **모든 라우터보다 먼저** 걸린다 — 엔드포인트가 경로를 읽기 전에
# "어느 프로젝트인가" 가 정해져 있어야 한다.
app.add_middleware(project_context.ProjectMiddleware)

app.include_router(brand_router)
app.include_router(library_router)
app.include_router(drive_router)
app.include_router(chat_stream_router)
app.include_router(admin_auth_router)
app.include_router(admin_qa_router)
app.include_router(admin_docs_router)
app.include_router(admin_questions_router)
app.include_router(admin_settings_router)
app.include_router(admin_categories_router)
app.include_router(admin_projects_router)
app.include_router(admin_analytics_router)
app.include_router(admin_pipeline_router)
app.include_router(admin_jobs_router)
# studio 전용 라우터도 항상 등록한다. serve 에서는 각 엔드포인트가 403을 낸다 —
# 등록 자체를 모드에 따라 바꾸면 운영에서 404가 나서 "경로가 틀렸나"를 먼저 의심하게 된다.
app.include_router(studio_ask_router)
app.include_router(studio_generate_router)
app.include_router(studio_eval_router)
app.include_router(health_router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def drive_ui() -> HTMLResponse:
    """사용자 화면 — 자료 목록과 AI 질문이 한 화면에 있다.

    2026-10-06 에 말풍선 전용 화면(`chat.html`)에서 이 화면으로 옮겼다. 기획이 '자료를
    올리고 관리하고, 그 자료로 답한다' 로 넓어졌고, 자료 목록과 질문이 다른 화면에 있으면
    사용자가 둘을 오가며 무엇을 물을 수 있는지 다시 찾게 된다. 대화는 없어지지 않았다 —
    `AI 질문` 줄에서 물으면 그 자리에서 펼쳐진다.
    """
    return _render("drive.html")


@app.get("/projects/new", include_in_schema=False)
def project_new_ui() -> HTMLResponse:
    """새 프로젝트 만들기.

    **studio 에서만 연다.** 운영은 만들어진 팩 폴더를 복사받는 쪽이다 — 운영에서 빈
    프로젝트를 만들 수 있으면 사용자 화면에 자료가 없는 폴더가 생긴다.
    """
    if not is_studio():
        raise HTTPException(status_code=404, detail="운영에서는 프로젝트를 만들 수 없습니다.")
    return _render("folder-new.html")


# `data-brand="포맷 문자열"` 이 붙은 **잎 요소**의 텍스트를 프로필 값으로 갈아 끼운다.
# 열림표그/내용/닫힘표그를 나눠 잡으므로 마크업(클래스·속성)은 그대로 남는다.
_BRAND_TAG = re.compile(r'(<(\w+)[^>]*\sdata-brand="([^"]*)"[^>]*>)(.*?)(</\2>)', re.DOTALL)


def _apply_brand(html: str) -> str:
    """납품처 프로필을 화면 문자열에 반영한다.

    산출물 안에 `{organization}` 같은 자리표시자를 직접 쓰지 않고 **속성에 포맷을 두고 기본
    텍스트는 그대로 남긴** 이유는, 퍼블이 산출물 파일을 그냥 열어봐도 화면이 성립해야 하기
    때문이다. 다음 산출물이 왔을 때 다시 손대는 것도 속성 한 개씩이라 배선이 가볍다.

    포맷에 모르는 이름이 들어 있으면 **원문을 그대로 둔다.** 화면 문구 하나 때문에 페이지
    전체가 500으로 죽는 쪽이 훨씬 나쁘다.
    """
    values = load_profile().template_values()

    def _replace(match: re.Match) -> str:
        try:
            text = match.group(3).format(**values)
        except (KeyError, IndexError, ValueError):
            log_event(logger, "unknown data-brand placeholder", template=match.group(3))
            return match.group(0)
        return f"{match.group(1)}{escape(text, quote=False)}{match.group(5)}"

    return _BRAND_TAG.sub(_replace, html)


# 로고 자리. 이미지가 있으면 **글자 대신 그림**을 넣는다.
_LOGO_TAG = re.compile(r'(<(\w+)[^>]*\sdata-brand-logo[^>]*>)(.*?)(</\2>)', re.DOTALL)


def _apply_logo(html: str) -> str:
    """로고 이미지가 등록돼 있으면 그 자리의 글자를 `<img>` 로 바꾼다.

    화면이 켜진 뒤 JS 로 바꾸게 하면 **글자 로고가 한 번 보였다 그림으로 바뀐다.** 브랜드를
    서버가 직접 박는 것과 같은 이유로 여기서 처리한다(`_apply_brand` 독스트링 참고).

    등록된 로고가 없으면 **아무것도 하지 않는다** — 마크업에 남아 있는 글자가 그대로 쓰인다.
    """
    url = logo_url()
    if not url:
        return html

    def _replace(match: re.Match) -> str:
        alt = escape(match.group(3).strip(), quote=True)
        return f'{match.group(1)}<img src="{url}" alt="{alt}">{match.group(4)}'

    return _LOGO_TAG.sub(_replace, html)


# 화면이 참조하는 우리 정적 파일. 주소 뒤에 파일이 바뀐 시각을 붙인다.
_STATIC_REF = re.compile(r'(?:src|href)="(/static/[^"?]+\.(?:css|js))"')


def _bust_cache(html: str) -> str:
    """`/static/admin.js` → `/static/admin.js?v=<수정시각>`.

    **이것이 없으면 코드를 고쳐도 브라우저가 옛 파일을 계속 쓴다.** 고친 사람은 바뀐 줄 알고,
    보는 사람은 안 바뀌었다고 한다 — 2026-10-03·10-06 에 두 번 같은 일로 시간을 썼다
    (프로젝트 선택기가 안 보인다 · 로고가 안 고쳐진다). `Ctrl+F5` 를 기억하게 하는 것은
    해결이 아니다. 기억하지 못하는 쪽이 정상이다.

    파일이 없으면 주소를 그대로 둔다 — 화면 하나 때문에 페이지가 죽는 쪽이 훨씬 나쁘다.
    `vendor/` 의 라이브러리도 같이 붙는데, 그쪽은 바뀌지 않으므로 값도 바뀌지 않는다.
    """
    def _replace(match: re.Match) -> str:
        ref = match.group(1)
        target = STATIC_DIR / ref[len("/static/"):]
        try:
            stamp = int(target.stat().st_mtime)
        except OSError:
            return match.group(0)
        return match.group(0).replace(ref, f"{ref}?v={stamp}")

    return _STATIC_REF.sub(_replace, html)


def _render(filename: str) -> HTMLResponse:
    """`<body data-mode>` 와 브랜드 문자열을 **서버가 직접 박아서** 내려준다.

    화면이 켜진 뒤 API로 물어보게 하면, 응답이 오기 전 짧은 순간 studio 전용 탭이나 기본
    브랜드가 보였다 바뀐다. 운영에서 동작하지 않는 버튼이 잠깐이라도 보이면 누르는 사람이
    생기고, 조직 이름이 깜빡이는 화면은 완성돼 보이지 않는다.
    """
    html = (STATIC_DIR / filename).read_text(encoding="utf-8")
    # 제품 이름도 함께 박는다. 화면이 프로필을 저장한 뒤 브랜드를 **다시 그릴 때**
    # (`admin.js` 의 `applyBrand`) 이 값이 필요한데, 그때 서버에 또 물어보면 제목이 한 번
    # 깜빡인다. `data-mode` 와 같은 자리에 둔다.
    values = load_profile().template_values()
    settings = get_settings()
    html = html.replace(
        'data-mode="serve"',
        f'data-mode="{settings.app_mode}" data-app-name="{escape(values["app_name"], quote=True)}"'
        f' data-reasoning="{"on" if settings.ai_reasoning else "off"}"'
        f' data-ai-default="{"on" if settings.ai_answer_default else "off"}"',
    )
    return HTMLResponse(_bust_cache(_apply_logo(_apply_brand(html))))


@app.get("/admin", include_in_schema=False)
def admin_ui() -> HTMLResponse:
    """관리자 화면.

    **이 페이지 자체에는 인증을 걸지 않는다.** 로그인 모달(`#authModal`)이 이 안에 들어 있어서,
    페이지를 못 받으면 로그인할 화면도 못 받는다. 실제 데이터는 전부 `/api/admin/*` 에서
    오고 그쪽은 인증이 걸려 있으므로, 로그인 없이 여기서 볼 수 있는 것은 빈 껍데기뿐이다.

    2026-08-16 까지 있던 `/admin/review` 임시 화면은 걷어냈다. 검수는 이 화면의 `검수`
    항목이 맡는다 — 두 곳에 두면 한쪽만 고쳐지고 검수자가 본 모습과 사용자가 보는 모습이
    갈린다(같은 이유로 편집 폼도 QA 인덱스와 공용 컴포넌트다).
    """
    if not (STATIC_DIR / "admin.html").exists():
        return HTMLResponse(
            "<!DOCTYPE html><html lang=ko><meta charset=utf-8>"
            "<title>관리자 화면 없음</title>"
            "<body style='font-family:sans-serif;padding:40px;line-height:1.7'>"
            "<h1 style='font-size:18px'>관리자 화면 파일이 없습니다.</h1>"
            "<p><code>app/static/admin.html</code> 이 있어야 합니다."
            " 퍼블 산출물 이식이 빠지지 않았는지 확인해 주세요.</p>"
            "</body></html>",
            status_code=200,
        )
    return _render("admin.html")
