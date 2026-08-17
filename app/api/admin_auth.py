"""로그인 · 로그아웃 · 세션 확인 — 화면의 `#authModal` 이 쓰는 세 개.

**이 라우터만 인증을 걸지 않는다.** 로그인하기 전에 부르는 경로이기 때문이다.
나머지 `/api/admin/*` 은 라우터 단위로 `require_admin` 이 걸려 있다.

### 실패를 서버에서도 막는다

화면도 5회 실패 후 30초 잠금을 하지만(`admin.js` 의 `AUTH_MAX_TRY`), 화면 코드는 사용자가
얼마든지 건너뛸 수 있다. 개발 서버에서 SSH 실패 로그인이 2,600건 넘게 관측된 적이 있는
프로젝트라, 비밀번호를 계속 찔러 보는 경로를 서버에서도 닫아 둔다.

메모리에만 기록한다 — 파일로 남기면 배포 대상이 하나 늘고, 재시작으로 풀려도 공격자가 얻는
것은 30초뿐이다.
"""

import threading
import time

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.core.auth import check_credentials, current_admin
from app.core.config import get_settings
from app.core.logging import get_logger, log_event
from app.core.session import issue
from app.models.schemas import LoginRequest, LoginResponse, SessionResponse

logger = get_logger("api.admin_auth")

router = APIRouter(prefix="/api/admin", tags=["admin-auth"])

# 화면(admin.js)의 AUTH_MAX_TRY / AUTH_LOCK_SEC 과 같은 값으로 맞춘다.
_MAX_FAILURES = 5
_LOCK_SECONDS = 30
_WINDOW_SECONDS = 300

_LOCK = threading.Lock()
_failures: dict[str, list[float]] = {}


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _locked_for(key: str) -> int:
    """남은 잠금 시간(초). 0이면 잠기지 않았다."""
    with _LOCK:
        now = time.time()
        recent = [t for t in _failures.get(key, []) if now - t < _WINDOW_SECONDS]
        _failures[key] = recent
        if len(recent) < _MAX_FAILURES:
            return 0
        remaining = int(_LOCK_SECONDS - (now - recent[-1]))
        return max(0, remaining)


def _record_failure(key: str) -> None:
    with _LOCK:
        _failures.setdefault(key, []).append(time.time())


def _clear_failures(key: str) -> None:
    with _LOCK:
        _failures.pop(key, None)


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, response: Response) -> LoginResponse:
    key = _client_key(request)
    locked = _locked_for(key)
    if locked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"로그인 시도가 많습니다. {locked}초 뒤에 다시 시도해 주세요.",
            headers={"Retry-After": str(locked)},
        )

    if not check_credentials(payload.username, payload.password):
        _record_failure(key)
        log_event(logger, "login failed", username=payload.username, client=key)
        # 아이디가 없는 건지 비밀번호가 틀린 건지 구분해 주지 않는다(계정 열거 방지).
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")

    _clear_failures(key)
    settings = get_settings()
    token, expires_at = issue(payload.username)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_minutes * 60,
        # httponly: 화면 스크립트가 토큰을 읽을 수 없다. XSS 가 나도 토큰은 못 가져간다.
        httponly=True,
        # lax: 다른 사이트에서 넘어온 요청에는 쿠키가 붙지 않는다(CSRF 완화).
        samesite="lax",
        path="/",
    )
    log_event(logger, "login", username=payload.username, client=key)
    return LoginResponse(username=payload.username, expires_at=expires_at)


@router.post("/logout")
def logout(response: Response) -> dict:
    # 인증을 요구하지 않는다 — 이미 만료된 상태에서 눌러도 쿠키는 지워져야 한다.
    response.delete_cookie(get_settings().session_cookie_name, path="/")
    return {"ok": True}


@router.get("/session", response_model=SessionResponse)
def session_info(request: Request) -> SessionResponse:
    """화면이 켜질 때 로그인 모달을 띄울지 정하는 데 쓴다. 인증 없이 부를 수 있다."""
    user = current_admin(request)
    return SessionResponse(
        authenticated=bool(user),
        username=user,
        mode=get_settings().app_mode,
    )
