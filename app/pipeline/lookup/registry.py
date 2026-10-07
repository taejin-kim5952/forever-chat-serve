"""팩의 `lookup.yaml` 을 읽어 프로바이더를 세운다 (개발계획서 §4.3).

팩에는 **어떤 프로바이더를 켤지와 문구만** 둔다. 실행 코드는
`app/pipeline/lookup/providers/` 에 있다 — 팩에 코드를 넣으면 팩 반입이 곧 코드 반입이 된다.

### 정의가 없으면 라이브를 안 켠다

`lookup.yaml` 이 없거나 `routes.lookup` 이 꺼져 있으면 **지금까지와 완전히 같은 경로**가
된다. 기존 설치는 이 파일이 없으므로 아무 영향도 받지 않는다.
"""

from pathlib import Path

import yaml

from app.core.config import get_settings
from app.core.logging import get_logger, log_event
from app.core.pack import load_pack
from app.pipeline.lookup.providers import mcp_portal

logger = get_logger("pipeline.lookup.registry")

LOOKUP_NAME = "lookup.yaml"


def _config_path() -> Path:
    return Path(get_settings().pack_dir) / LOOKUP_NAME


def load_providers() -> list:
    """켜져 있는 프로바이더 목록. 하나라도 세우지 못하면 그것만 빠진다.

    하나가 잘못돼 전체가 안 도는 것보다, 그것만 빼고 나머지를 쓰는 편이 낫다 —
    라이브가 통째로 죽으면 사용자는 이유를 알 수 없다.
    """
    try:
        pack = load_pack()
    except Exception as exc:  # noqa: BLE001 - 팩 오류는 기동에서 막을 몫이다
        log_event(logger, "lookup disabled — pack unreadable", error=str(exc))
        return []

    if not pack.route_enabled("lookup"):
        return []

    path = _config_path()
    if not path.exists():
        log_event(logger, "lookup enabled but lookup.yaml missing", path=str(path))
        return []

    try:
        config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        log_event(logger, "lookup.yaml unreadable", error=str(exc))
        return []

    settings = get_settings()
    client = mcp_portal.PortalClient(
        settings.lookup_api_base, settings.lookup_timeout_ms)

    providers = []
    for entry in config.get("providers", []) or []:
        if not isinstance(entry, dict) or not entry.get("enabled", True):
            continue
        provider = mcp_portal.build(str(entry.get("id", "")), entry, client)
        if provider is not None:
            providers.append(provider)

    log_event(logger, "lookup providers loaded",
              count=len(providers), ids=[p.id for p in providers])
    return providers
