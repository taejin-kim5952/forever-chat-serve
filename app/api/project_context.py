"""요청 하나가 어느 프로젝트를 볼지 정하는 자리.

### 왜 미들웨어인가

경로를 읽는 코드가 11개 파일에 흩어져 있고 전부 `get_settings()` 를 거친다. 엔드포인트마다
`project` 인자를 받아 아래로 넘기게 고치면 56개 경로와 그 아래 호출을 전부 손대야 하고,
**한 군데라도 빠뜨리면 다른 프로젝트의 파일을 조용히 읽는다.** 틀려도 예외가 안 나고
"가끔 엉뚱한 답이 나온다"로만 드러나는 종류라, 들어오는 자리에서 한 번 정한다.

### 어디서 읽는가

    ?project=mcp         쿼리 (화면이 쓰는 길)
    X-Project: mcp       헤더 (스크립트·위젯이 쓰는 길)

**본문(JSON)은 보지 않는다.** 미들웨어에서 본문을 읽으면 스트림을 소비해 엔드포인트가 빈
본문을 받는다. 되감는 방법도 있지만, 큰 업로드(폴더 등록)까지 매 요청 메모리에 올리게 된다.

### 못 찾으면 어떻게 되는가

없는 프로젝트를 주면 **400 으로 막는다.** 조용히 기본 프로젝트로 떨어뜨리면, 오타 하나로
다른 프로젝트의 문서를 지우거나 QA를 승인하는 일이 생긴다.

아무것도 안 주면 프로젝트를 고르지 않은 것으로 두고 **기본 프로젝트**(목록의 첫 번째)를
쓴다. 프로젝트가 없으면(= `PACK_DIR` 로 띄운 단일 설치) 예전과 똑같이 동작한다.
"""

from urllib.parse import unquote_plus

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core import projects
from app.core.config import reset_project, use_project
from app.core.logging import get_logger

logger = get_logger("api.project_context")

HEADER = b"x-project"
QUERY = "project"

# 프로젝트와 무관한 경로. 여기까지 프로젝트를 강제하면 프로젝트가 하나도 없는 새 설치에서
# 관리자 화면 자체를 못 연다.
_FREE_PREFIXES = ("/api/admin/projects", "/health", "/docs", "/openapi.json", "/static")


def _wanted(scope: Scope) -> str:
    """쿼리와 헤더에서 프로젝트를 꺼낸다. **본문은 보지 않는다**(위 독스트링 참고)."""
    raw = (scope.get("query_string") or b"").decode("latin-1")
    for pair in raw.split("&"):
        if pair.startswith(QUERY + "="):
            return unquote_plus(pair[len(QUERY) + 1:]).strip()
    for name, value in scope.get("headers") or []:
        if name.lower() == HEADER:
            return value.decode("latin-1").strip()
    return ""


class ProjectMiddleware:
    """요청 하나가 볼 프로젝트를 정한다.

    **순수 ASGI 미들웨어다.** Starlette 의 `BaseHTTPMiddleware`(`@app.middleware("http")`)는
    요청을 별도 태스크로 넘기면서 수신 스트림을 감싼다. 우리는 헤더와 쿼리만 보면 되므로
    감쌀 이유가 없고, 감싸지 않으면 큰 업로드(폴더 등록)가 미들웨어를 그냥 지나간다.
    같은 태스크에서 도는 덕에 ContextVar 가 동기 엔드포인트(스레드풀)까지 그대로 전달되는
    것도 확인했다.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        wanted = _wanted(scope)
        if wanted and not projects.exists(wanted):
            # 조용히 기본 프로젝트로 떨어뜨리지 않는다. 오타 하나로 다른 프로젝트의 문서를
            # 지우거나 QA를 승인하는 일이 생긴다.
            await JSONResponse(
                status_code=400, content={"detail": f"없는 프로젝트입니다: {wanted}"},
            )(scope, receive, send)
            return

        chosen = wanted
        source = "request"
        if not chosen and not scope.get("path", "").startswith(_FREE_PREFIXES):
            # 기본값으로 채운다. 다만 **채웠다는 것을 남긴다** — 공개 질문 경로는 '전체'
            # 상태에서 가장 가까운 자료가 있는 프로젝트를 찾아야 하고, 기본값을 '화면이
            # 골랐다' 로 읽으면 빈 프로젝트에서 찾다 답을 못 찾는다(app/pipeline/scope.py).
            chosen = projects.default_project()
            source = "default"

        token = use_project(chosen, source=source)
        try:
            await self.app(scope, receive, send)
        finally:
            # 되돌리지 않으면 이 컨텍스트를 물려받는 다음 작업이 남의 프로젝트를 본다.
            reset_project(token)
