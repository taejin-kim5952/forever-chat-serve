"""관리자 인증 — 세션 쿠키 또는 HTTP Basic.

계정은 하나뿐이고 환경변수(`ADMIN_USERNAME` / `ADMIN_PASSWORD`)로만 주입한다.
사내 폐쇄망 도구라 역할 구분까지는 두지 않는다. 대신 지켜야 할 것 둘:

1. 비교는 `secrets.compare_digest` 로 한다. `==` 는 앞자리부터 순서대로 비교하다 틀리면
   즉시 멈춰서, 응답 시간 차이로 비밀번호를 한 글자씩 알아낼 수 있다.
2. 비밀번호가 기본값(`change-me`)이면 기동 시 경고를 남긴다. 개발 서버가 인터넷에
   노출된 적이 있어 기본값 그대로 뜨는 상황을 조용히 넘기면 안 된다.

### 두 가지를 함께 받는 이유

- **세션 쿠키**: 관리자 화면의 로그인 모달(`#authModal`)이 쓴다. 사람이 쓰는 경로다.
- **Basic**: `curl -u admin:비밀번호 ... /reindex` 같은 스크립트가 쓴다. 배포·점검 절차가
  이미 이 방식으로 적혀 있어서 걷어내면 문서와 손이 전부 어긋난다.

### `WWW-Authenticate` 를 더 이상 붙이지 않는다

이 헤더가 있으면 브라우저가 **자기 로그인 창**을 띄운다. 우리 로그인 모달을 만들어 둔 지금은
두 개가 겹쳐 뜨고, 브라우저 창으로 로그인하면 우리 화면은 로그인 사실을 모른다.
`curl -u` 는 처음부터 헤더를 붙여 보내므로 이 헤더 없이도 그대로 동작한다.
"""

import secrets

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.core import session
from app.core.config import get_settings
from app.core.logging import get_logger, log_event

logger = get_logger("core.auth")

DEFAULT_PASSWORD = "change-me"

# auto_error=False: 헤더가 없어도 여기서 401을 내지 않는다. 쿠키를 먼저 봐야 하기 때문이다.
_basic = HTTPBasic(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="관리자 인증이 필요합니다.",
)


def warn_if_default_password() -> None:
    if get_settings().admin_password == DEFAULT_PASSWORD:
        logger.warning("ADMIN_PASSWORD 가 기본값입니다. 운영 배포 전에 환경변수로 반드시 바꾸세요.")


def check_credentials(username: str, password: str) -> bool:
    """아이디·비밀번호 확인. 로그인 엔드포인트와 Basic 인증이 함께 쓴다.

    **바이트로 바꿔서 비교한다.** `compare_digest` 는 문자열을 받으면 ASCII 만 허용해서,
    한글이 한 글자라도 섞이면 `TypeError` 를 낸다 — 로그인 실패(401)가 아니라 서버 오류(500)가
    된다. 사용자가 로그인 칸에 한글을 치는 일은 흔하다(오타·한영 전환).
    """
    settings = get_settings()
    # 아이디가 틀려도 비밀번호 비교를 끝까지 수행한다 — 어느 쪽이 틀렸는지 시간으로 새지 않게.
    id_ok = secrets.compare_digest(username.encode("utf-8"), settings.admin_username.encode("utf-8"))
    pw_ok = secrets.compare_digest(password.encode("utf-8"), settings.admin_password.encode("utf-8"))
    return id_ok and pw_ok


def current_admin(request: Request) -> str | None:
    """로그인한 사용자 이름 또는 None. 401을 내지 않는다 — `/api/admin/session` 이 쓴다."""
    user = session.verify(request.cookies.get(get_settings().session_cookie_name))
    return user


def require_admin(
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(_basic),
) -> str:
    user = current_admin(request)
    if user:
        return user

    if credentials is None:
        raise _UNAUTHORIZED

    if not check_credentials(credentials.username, credentials.password):
        log_event(logger, "admin auth failed", username=credentials.username)
        raise _UNAUTHORIZED

    return credentials.username
