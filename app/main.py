from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.admin_docs import router as admin_docs_router
from app.api.admin_qa import router as admin_qa_router
from app.api.admin_questions import router as admin_questions_router
from app.api.admin_settings import router as admin_settings_router
from app.api.ask import router as ask_router
from app.api.health import router as health_router
from app.core.auth import require_admin, warn_if_default_password
from app.core.config import get_settings
from app.core.logging import get_logger, log_event, setup_logging

setup_logging()
logger = get_logger("main")

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    log_event(
        logger, "server started",
        mode=settings.app_mode,
        embed_model=settings.ollama_embed_model,
        qa_collection=settings.chroma_qa_collection,
    )
    warn_if_default_password()
    yield


app = FastAPI(title="API Manager 도우미 (openapi-chat-serve)", version="0.1.0", lifespan=lifespan)

app.include_router(ask_router)
app.include_router(admin_qa_router)
app.include_router(admin_docs_router)
app.include_router(admin_questions_router)
app.include_router(admin_settings_router)
app.include_router(health_router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def chat_ui() -> FileResponse:
    return FileResponse(STATIC_DIR / "chat.html")


@app.get("/admin", include_in_schema=False)
def admin_ui(_: str = Depends(require_admin)) -> HTMLResponse:
    """관리자 화면.

    `<body data-mode>` 를 **서버가 직접 박아서** 내려준다. 화면이 켜진 뒤 API로 모드를
    물어보게 하면, 응답이 오기 전 짧은 순간 studio 전용 탭이 보였다 사라진다.
    운영에서 동작하지 않는 버튼이 잠깐이라도 보이면 누르는 사람이 생긴다.
    """
    html = (STATIC_DIR / "admin.html").read_text(encoding="utf-8")
    html = html.replace('data-mode="serve"', f'data-mode="{get_settings().app_mode}"')
    return HTMLResponse(html)
