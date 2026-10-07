"""라이브 조회 (개발계획서 §4).

여기서 지키려는 것은 넷이다.

  1. **꺼져 있으면 지금까지와 같다** — 기존 설치가 영향을 받지 않아야 한다
  2. **엉뚱한 대상을 조회하지 않는다** — 답을 못 하는 것보다 나쁘다
  3. **실패하면 조용히 폴백한다** — 사이트가 죽어도 챗봇은 절차 안내를 계속한다
  4. **라이브 본문은 이력에 남지 않는다** — 그 시점의 사용자 데이터다
"""

import json
from pathlib import Path

import pytest

from app.core import config
from app.pipeline.lookup import entities
from app.pipeline.lookup.base import Principal
from app.pipeline.lookup.providers.mcp_portal import Forbidden, PortalClient, build
from app.pipeline.lookup.render import Whitelist, bullet, join, render


def _gazetteer(servers: list[dict]) -> None:
    path = Path(config.get_settings().var_dir) / "gazetteer.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"servers": servers}, ensure_ascii=False), encoding="utf-8")


# ───────────────────────────── 엔티티 ─────────────────────────────

def test_no_dictionary_means_no_lookup():
    """배치를 아직 안 돌렸으면 사전이 없다. 그때는 라이브로 가지 않는다."""
    target, confidence = entities.extract("agent-news 상태 어때")

    assert target == {}
    assert confidence == 0.0


def test_finds_server_by_name():
    _gazetteer([{"serverId": 6, "latestVersionId": 7, "name": "agent-news",
                 "registryKey": "com.theagenttimes/agent-news"}])

    target, confidence = entities.extract("agent-news 상태 어때?")

    assert target["version_id"] == 7
    assert target["name"] == "agent-news"
    assert confidence >= entities.MIN_CONFIDENCE


def test_longer_name_wins():
    """`agent-news` 가 `agent-news-v2` 를 가로채면 엉뚱한 서버를 조회한다."""
    _gazetteer([
        {"serverId": 1, "latestVersionId": 1, "name": "agent-news"},
        {"serverId": 2, "latestVersionId": 2, "name": "agent-news-v2"},
    ])

    target, _ = entities.extract("agent-news-v2 툴 목록 알려줘")

    assert target["name"] == "agent-news-v2"


def test_word_boundary_is_respected():
    """짧은 이름이 다른 이름 안에서 걸리면 안 된다."""
    _gazetteer([{"serverId": 1, "latestVersionId": 1, "name": "news"}])

    target, _ = entities.extract("agent-news 상태 어때")

    assert target == {}


def test_glossary_alias():
    """사람이 적은 통칭도 알아본다."""
    _gazetteer([{"serverId": 6, "latestVersionId": 7, "name": "agent-news"}])
    Path(config.get_settings().pack_dir).mkdir(parents=True, exist_ok=True)
    (Path(config.get_settings().pack_dir) / "glossary.json").write_text(
        json.dumps({"aliases": {"에이전트 뉴스": "agent-news"}}, ensure_ascii=False),
        encoding="utf-8")

    target, _ = entities.extract("에이전트 뉴스 지금 살아 있나요")

    assert target["version_id"] == 7


# ───────────────────────────── 렌더 ─────────────────────────────

def test_whitelist_drops_unknown_fields():
    """모르는 필드는 출력하지 않는 쪽이 기본값이어야 한다 — 언젠가 토큰이 섞인다."""
    values = Whitelist({"name": "serverName"}).values(
        {"serverName": "agent-news", "apiToken": "secret-please-do-not-print"})

    assert values == {"name": "agent-news"}


def test_render_skips_when_required_value_missing():
    """빈 칸이 들어간 문장은 틀린 답이다."""
    assert render("{a} 는 {b} 입니다", {"a": "서버"}, required=["b"]) is None


def test_render_survives_broken_template():
    """팩의 템플릿이 잘못돼도 챗봇이 죽지는 않는다."""
    assert render("{없는이름}", {"a": "1"}) is None


def test_join_and_bullet():
    assert join(["a", "b"]) == "a · b"
    assert join([]) == "없음"
    assert bullet(["첫째", "둘째"]) == "- 첫째\n- 둘째"


# ───────────────────────────── 프로바이더 ─────────────────────────────

CONFIG = {
    "patterns": ["상태", "검증", "왜"],
    "template": "**{server_name} {version}** 은 현재 **{status_label}** 입니다.\n{blocked_by}",
}


def _provider(client):
    return build("version_status", CONFIG, client)


def test_match_needs_both_target_and_pattern():
    provider = _provider(PortalClient("http://x"))

    # 대상은 있는데 말이 안 맞는다
    assert provider.match("오늘 날씨 어때", {"version_id": 7}) is None
    # 말은 맞는데 대상이 없다 — "어느 서버" 없이 상태를 답할 수 없다
    assert provider.match("상태 어때", {}) is None
    assert provider.match("agent-news 상태 어때", {"version_id": 7}) is not None


def test_render_uses_only_whitelisted_values():
    provider = _provider(PortalClient("http://x"))
    intent = provider.match("agent-news 상태", {"version_id": 7})

    answer = provider.render(intent, {
        "serverName": "agent-news", "version": "0.3.0", "statusLabel": "등록",
        "blockedBy": ["명세 형식 이(가) 통과하지 못했습니다"],
        "sessionCookie": "절대-나가면-안-되는-값",
    })

    assert "agent-news" in answer.text
    assert "등록" in answer.text
    assert "명세 형식" in answer.text
    assert "절대-나가면" not in answer.text
    # 언제 기준인지 없으면 사용자가 캐시된 값을 현재값으로 믿는다
    assert answer.fetched_at is not None


def test_forbidden_is_not_a_fallback():
    """권한 없음은 문서를 보여준다고 풀리지 않는다 — 그대로 안내해야 한다."""
    class _Client(PortalClient):
        def get(self, path, principal):
            raise Forbidden()

    provider = _provider(_Client("http://x"))
    intent = provider.match("agent-news 상태", {"version_id": 7})

    with pytest.raises(Forbidden):
        provider.fetch(intent, Principal(authenticated=True))


# ───────────────────────────── 화면 맥락 ─────────────────────────────

def test_context_supplies_target_when_question_has_no_name():
    """검증 화면에서 "왜 안 되나요" 만 쳐도 그 Version 을 짚는다 — 위젯의 값어치."""
    from app.pipeline.retrieve import Retriever

    target, confidence = Retriever._context_target(
        {"route": "verify", "serverId": 6, "versionId": 7})

    assert target["version_id"] == 7
    # 사용자가 그 화면을 보고 있다는 것은 추측이 아니라 사실이다
    assert confidence == 1.0


def test_context_without_version_is_ignored():
    from app.pipeline.retrieve import Retriever

    assert Retriever._context_target({"route": "verify"}) == ({}, 0.0)
    assert Retriever._context_target(None) == ({}, 0.0)


def test_anonymous_never_reaches_lookup():
    assert Principal().anonymous() is True
    assert Principal(authenticated=True).anonymous() is False
