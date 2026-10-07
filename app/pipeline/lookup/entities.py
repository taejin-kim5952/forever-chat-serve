"""질문에서 대상을 뽑아낸다 (개발계획서 §4.4).

"payment-mcp 상태 어때" 의 **payment-mcp 를 알아보는** 일이다. 임베딩을 쓰지 않는다 —
사전 대조는 결정적이라 같은 질문에 같은 답이 나오고, 왜 그렇게 잡혔는지 설명할 수 있다.

### 사전은 두 벌이다

  gazetteer  야간 배치가 사이트에서 받아 만든다. 서버·Tool 이름 (`var/<pack>/gazetteer.json`)
  glossary   사람이 적는 별칭·약어 (`packs/<pack>/glossary.json`)

기계가 만든 것과 사람이 적은 것을 나눈 이유는, 배치가 덮어쓸 때 사람이 적은 별칭이
날아가면 안 되기 때문이다.

### 왜 긴 이름을 먼저 보나

`agent-news` 와 `agent-news-v2` 가 함께 있으면 짧은 쪽이 먼저 걸려 **엉뚱한 서버를 조회**한다.
긴 이름부터 대조해 그 사고를 막는다.
"""

import json
import re
from pathlib import Path

from app.core.config import get_settings
from app.core.jsonstore import read_json
from app.core.logging import get_logger, log_event

logger = get_logger("pipeline.lookup.entities")

GAZETTEER_NAME = "gazetteer.json"
GLOSSARY_NAME = "glossary.json"

# 이 미만이면 무시한다. 엉뚱한 서버를 조회해 답하는 것이
# 답을 못 하는 것보다 나쁘다 (계획서 §4.3).
MIN_CONFIDENCE = 0.6


def _gazetteer_path() -> Path:
    return Path(get_settings().var_dir) / GAZETTEER_NAME


def _glossary_path() -> Path:
    return Path(get_settings().pack_dir) / GLOSSARY_NAME


def load_dictionary() -> dict[str, dict]:
    """`표기 → 대상` 사전. 소문자로 눌러 담는다.

    사전이 없으면 빈 값이다 — 배치를 아직 안 돌렸다는 뜻이고, 그때는 라이브로 가지 않고
    지금까지처럼 문서 검색으로 답한다.
    """
    table: dict[str, dict] = {}

    gazetteer = read_json(_gazetteer_path(), default={}) or {}
    for server in gazetteer.get("servers", []):
        if not isinstance(server, dict):
            continue
        target = {
            "kind": "server",
            "server_id": server.get("serverId"),
            "version_id": server.get("latestVersionId"),
            "name": server.get("name"),
            "registry_key": server.get("registryKey"),
        }
        for label in filter(None, [server.get("name"), server.get("registryKey")]):
            table[str(label).lower()] = target

    glossary = read_json(_glossary_path(), default={}) or {}
    # 사람이 적은 별칭이 기계 목록을 덮는다 — "결제 MCP" 같은 통칭을 붙이는 자리다.
    for alias, canonical in (glossary.get("aliases") or {}).items():
        target = table.get(str(canonical).lower())
        if target:
            table[str(alias).lower()] = target
        else:
            log_event(logger, "glossary alias points at unknown server",
                      alias=alias, canonical=canonical)
    return table


def extract(question: str, table: dict[str, dict] | None = None) -> tuple[dict, float]:
    """질문에서 대상 하나를 찾는다. 못 찾으면 `({}, 0.0)`.

    :return: (대상, 확신도)
    """
    table = load_dictionary() if table is None else table
    if not table:
        return {}, 0.0

    text = question.lower()
    # 긴 이름부터 — `agent-news` 가 `agent-news-v2` 를 가로채지 않게.
    for label in sorted(table, key=len, reverse=True):
        if not label:
            continue
        if _contains(text, label):
            # 이름이 길수록, 질문에서 차지하는 비중이 클수록 확신한다.
            ratio = len(label) / max(len(text), 1)
            confidence = min(1.0, 0.6 + ratio)
            return dict(table[label], matched=label), round(confidence, 3)
    return {}, 0.0


def _contains(text: str, label: str) -> bool:
    """말 경계를 본다.

    `mcp` 라는 짧은 이름이 `mcp-manager` 안에서 걸리면 엉뚱한 대상이 잡힌다.
    한글에는 공백 경계가 없는 경우가 많아 `\\b` 만으로는 부족하므로, 영숫자·하이픈이
    앞뒤에 붙어 있지 않은지 직접 본다.
    """
    for match in re.finditer(re.escape(label), text):
        before = text[match.start() - 1] if match.start() else ""
        after = text[match.end()] if match.end() < len(text) else ""
        if not _is_word_char(before) and not _is_word_char(after):
            return True
    return False


def _is_word_char(ch: str) -> bool:
    return bool(ch) and (ch.isalnum() or ch in "-_.")


def save_gazetteer(payload: dict) -> Path:
    """야간 배치가 부른다 (`scripts/sync_catalog.py`)."""
    path = _gazetteer_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log_event(logger, "gazetteer saved", path=str(path),
              servers=len(payload.get("servers", [])))
    return path
