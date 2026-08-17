"""관리자 세션 쿠키 — 서명된 토큰 하나로 끝낸다.

화면에 로그인 모달(`#authModal`)이 생기면서 필요해졌다. 브라우저 기본 인증 창을 쓰던 때는
브라우저가 매 요청에 아이디·비밀번호를 붙여 줬지만, 우리 폼으로 받으려면 "로그인했다"는
사실을 어딘가에 남겨야 한다.

**세션 저장소를 두지 않는다.** 토큰 안에 사용자와 만료 시각을 적고 HMAC 으로 서명해서, 서버는
서명만 확인한다. 이유:

- 저장소를 두면 배포 대상 파일이 하나 더 늘고, 파드가 여러 개면 공유 저장소까지 필요해진다.
  이 프로젝트는 "파일 3개 복사로 배포가 끝난다"를 지키려고 만들었다.
- 계정이 하나뿐이라 세션별로 관리할 것이 없다. 로그아웃은 쿠키를 지우면 된다.

서명 키는 기본적으로 **기동할 때마다 새로 만든다.** 서버를 재시작하면 로그인이 풀리지만,
키를 코드나 파일에 남기지 않는 편이 안전하다. 파드를 여러 개로 늘려 한쪽에서 로그인하고
다른 쪽으로 요청이 가는 구성이 되면 그때 `SESSION_SECRET` 을 준다.
"""

import base64
import hashlib
import hmac
import secrets
import time

from app.core.config import get_settings

# 설정에 키가 없을 때 쓰는 기동 시 1회용 키. 프로세스가 살아 있는 동안만 유효하다.
_RUNTIME_SECRET = secrets.token_urlsafe(32)


def _secret() -> bytes:
    return (get_settings().session_secret or _RUNTIME_SECRET).encode("utf-8")


def _sign(payload: bytes) -> str:
    digest = hmac.new(_secret(), payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def issue(username: str, ttl_seconds: int | None = None) -> tuple[str, int]:
    """`(토큰, 만료 epoch)`. 만료 시각을 함께 돌려주는 것은 화면이 남은 시간을 보여줄 수 있게."""
    ttl = ttl_seconds if ttl_seconds is not None else get_settings().session_ttl_minutes * 60
    expires_at = int(time.time()) + ttl
    payload = f"{username}|{expires_at}".encode("utf-8")
    body = _b64(payload)
    return f"{body}.{_sign(payload)}", expires_at


def verify(token: str | None) -> str | None:
    """유효하면 사용자 이름, 아니면 None. 예외를 내지 않는다 — 쿠키는 사용자가 조작할 수 있다."""
    if not token or "." not in token:
        return None
    body, _, signature = token.partition(".")
    try:
        payload = _unb64(body)
    except (ValueError, TypeError):
        return None

    # 서명 비교는 compare_digest 로. `==` 는 앞자리부터 비교하다 멈춰서 응답 시간으로 새어 나간다.
    if not hmac.compare_digest(signature, _sign(payload)):
        return None

    try:
        username, _, expires_raw = payload.decode("utf-8").rpartition("|")
        expires_at = int(expires_raw)
    except (ValueError, UnicodeDecodeError):
        return None

    if not username or expires_at < time.time():
        return None
    return username
