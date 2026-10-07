"""MCP 서버 관리 사이트 조회 (개발계획서 §4.3 · §5.7).

사이트가 열어 둔 조회 API 를 부른다. **사용자 자격을 그대로 실어** 보내고, 사이트가
403 을 주면 그대로 안내한다 — 챗봇은 권한을 판단하지 않는다 (§4.5).

    GET /api/user/assistant/versions/{versionId}/status   상태 · 검증이 막힌 사유
    GET /api/user/assistant/versions/{versionId}/health   지금 살아 있나 · 가용률
    GET /api/user/assistant/versions/{versionId}/tools    Tool 목록

### 재시도하지 않는다

사용자가 답을 기다리는 중이다. 1.5 초 안에 안 오면 문서 검색으로 내려가는 편이
두 번째 시도를 기다리는 것보다 낫다.
"""

import json
import urllib.error
import urllib.request
from datetime import datetime

from app.core.logging import get_logger, log_event
from app.pipeline.lookup.base import Action, LiveAnswer, LookupIntent, Principal
from app.pipeline.lookup.render import Whitelist, bullet, join, now_label, render

logger = get_logger("pipeline.lookup.mcp_portal")


class PortalClient:
    """사이트 조회 API 클라이언트."""

    def __init__(self, base_url: str, timeout_ms: int = 1500) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_ms / 1000

    def get(self, path: str, principal: Principal) -> dict | None:
        """실패하면 None. **사유는 로그에만 남기고 사용자에게는 폴백을 보여준다.**

        예외는 403 뿐이다 — 권한 없음은 "지금 답할 수 없다" 가 아니라
        "당신은 볼 수 없다" 라서, 문서 검색으로 내려가면 사용자가 계속 헤맨다.
        """
        url = f"{self.base_url}{path}"
        request = urllib.request.Request(url, headers=principal.headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code == 403:
                raise Forbidden() from exc
            log_event(logger, "portal lookup failed", url=path, status=exc.code)
            return None
        except Exception as exc:  # noqa: BLE001 - 망·타임아웃·깨진 JSON 모두 폴백이다
            log_event(logger, "portal lookup failed", url=path, error=str(exc))
            return None


class Forbidden(Exception):
    """사용자가 볼 수 없는 대상. 문서 검색으로 내려가지 않고 그대로 안내한다."""


# ─────────────────────────── 프로바이더 ───────────────────────────

# 사이트 응답에서 템플릿에 넘길 값. **여기 없는 필드는 답변에 나가지 않는다.**
_STATUS_FIELDS = {
    "server_name": "serverName",
    "version": "version",
    "status_label": "statusLabel",
    "registry_key": "registryKey",
    "tool_count": "toolCount",
    "blocked_by": ("blockedBy", bullet),
    "next_actions": ("nextActions", join),
}

_HEALTH_FIELDS = {
    "server_name": "serverName",
    "version": "version",
    "result_label": "resultLabel",
    "last_check": "lastCheckedAt",
    "uptime": "uptimeRate",
    "uptime_hours": "uptimeHours",
    "messages": ("messages", bullet),
}

_TOOLS_FIELDS = {
    "server_name": "serverName",
    "version": "version",
    "tool_count": "toolCount",
}


class _PortalProvider:
    """세 인텐트가 같은 뼈대를 쓴다 — 경로·화이트리스트·필수 값만 다르다."""

    def __init__(self, provider_id: str, client: PortalClient, config: dict,
                 path: str, fields: dict, required: list[str]) -> None:
        self.id = provider_id
        self.client = client
        self.patterns = [p.lower() for p in config.get("patterns", [])]
        self.template = config.get("template", "")
        self.site_url = config.get("site_url", "")
        self.path = path
        self.whitelist = Whitelist(fields)
        self.required = required

    def match(self, question: str, entities: dict) -> LookupIntent | None:
        # 대상을 못 짚었으면 라이브로 가지 않는다 — "어느 서버" 없이 상태를 답할 수 없다.
        if not entities.get("version_id"):
            return None
        text = question.lower()
        if not any(pattern in text for pattern in self.patterns):
            return None
        return LookupIntent(
            intent_id=self.id,
            entities={k: str(v) for k, v in entities.items() if v is not None},
            confidence=float(entities.get("confidence", 0.0)),
        )

    def fetch(self, intent: LookupIntent, principal: Principal) -> dict | None:
        version_id = intent.entities.get("version_id")
        if not version_id:
            return None
        return self.client.get(self.path.format(version_id=version_id), principal)

    def render(self, intent: LookupIntent, data: dict) -> LiveAnswer | None:
        values = self.whitelist.values(data)
        text = render(self.template, values, required=self.required)
        if not text:
            return None

        actions = []
        if self.site_url:
            actions.append(Action(
                label=f"{values.get('server_name', '서버')} 열기",
                url=self.site_url.format(**intent.entities),
            ))
        return LiveAnswer(
            text=text,
            fetched_at=datetime.now(),
            source_label="MCP 포털",
            actions=actions,
        )


def build(provider_id: str, config: dict, client: PortalClient):
    """`lookup.yaml` 의 정의 하나를 프로바이더로 만든다. 모르는 id 면 None."""
    spec = {
        "version_status": (
            "/api/user/assistant/versions/{version_id}/status",
            _STATUS_FIELDS, ["server_name", "status_label"],
        ),
        "server_health": (
            "/api/user/assistant/versions/{version_id}/health",
            _HEALTH_FIELDS, ["server_name", "result_label"],
        ),
        "server_tools": (
            "/api/user/assistant/versions/{version_id}/tools",
            _TOOLS_FIELDS, ["server_name"],
        ),
    }.get(provider_id)
    if spec is None:
        log_event(logger, "unknown lookup provider", provider_id=provider_id)
        return None
    path, fields, required = spec
    return _PortalProvider(provider_id, client, config, path, fields, required)


__all__ = ["PortalClient", "Forbidden", "build", "now_label"]
