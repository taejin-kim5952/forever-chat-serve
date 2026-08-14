"""관리자 화면 인증 (HTTP Basic).

계정은 하나뿐이고 환경변수(`ADMIN_USERNAME` / `ADMIN_PASSWORD`)로만 주입한다.
사내 폐쇄망 도구라 역할 구분·세션 저장소까지는 두지 않는다. 대신 지켜야 할 것 둘:

1. 비교는 `secrets.compare_digest` 로 한다. `==` 는 앞자리부터 순서대로 비교하다 틀리면
   즉시 멈춰서, 응답 시간 차이로 비밀번호를 한 글자씩 알아낼 수 있다.
2. 비밀번호가 기본값(`change-me`)이면 기동 시 경고를 남긴다. 개발 서버가 인터넷에
   노출된 적이 있어 기본값 그대로 뜨는 상황을 조용히 넘기면 안 된다.
"""

import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.core.config import get_settings
from app.core.logging import get_logger, log_event

logger = get_logger("core.auth")

DEFAULT_PASSWORD = "change-me"

# auto_error=False: 401 을 우리가 직접 만들어 WWW-Authenticate 헤더를 붙인다.
# 이 헤더가 있어야 브라우저가 로그인 창을 띄운다.
_basic = HTTPBasic(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="관리자 인증이 필요합니다.",
    headers={"WWW-Authenticate": 'Basic realm="openapi-chat-serve admin"'},
)


def warn_if_default_password() -> None:
    if get_settings().admin_password == DEFAULT_PASSWORD:
        logger.warning("ADMIN_PASSWORD 가 기본값입니다. 운영 배포 전에 환경변수로 반드시 바꾸세요.")


def require_admin(credentials: HTTPBasicCredentials | None = Depends(_basic)) -> str:
    if credentials is None:
        raise _UNAUTHORIZED

    settings = get_settings()
    # 아이디가 틀려도 비밀번호 비교를 끝까지 수행한다 — 어느 쪽이 틀렸는지 시간으로 새지 않게.
    id_ok = secrets.compare_digest(credentials.username, settings.admin_username)
    pw_ok = secrets.compare_digest(credentials.password, settings.admin_password)
    if not (id_ok and pw_ok):
        log_event(logger, "admin auth failed", username=credentials.username)
        raise _UNAUTHORIZED

    return credentials.username
