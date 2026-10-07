"""도메인 팩 (개발계획서 §3).

여기서 지키려는 것은 **기존 설치가 아무것도 하지 않아도 그대로 도는 것**이다.
`pack.json` 이 없으면 지금까지와 똑같아야 하고, 있으면 그 값이 코드 기본값을 덮어야 한다.
"""

import json
from pathlib import Path

import pytest

from app.core import config
from app.core.pack import ENGINE_VERSION, PackError, load_pack
from app.core.profile import load_profile


def _write_manifest(payload: dict) -> Path:
    path = Path(config.get_settings().pack_dir)
    path.mkdir(parents=True, exist_ok=True)
    target = path / "pack.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return target


def test_missing_manifest_is_not_an_error():
    """기존 설치에는 매니페스트가 없다. 없다고 막으면 멀쩡한 설치가 죽는다."""
    pack = load_pack()

    assert pack.exists() is False
    assert pack.pack_id == ""
    # 아무것도 덮지 않는다
    assert pack.matching.qa_match_threshold is None
    assert pack.route_enabled("lookup") is False


def test_manifest_is_loaded():
    _write_manifest({
        "pack_id": "mcp-manager",
        "pack_version": "1.0.0",
        "matching": {"qa_match_threshold": 0.85, "related_docs_floor": 0.55},
        "routes": {"lookup": True},
        "copy": {"unresolved_notice": "접수번호 {ticket_id} 로 회신드립니다."},
    })

    pack = load_pack()

    assert pack.exists() is True
    assert pack.pack_id == "mcp-manager"
    assert pack.matching.qa_match_threshold == 0.85
    assert pack.route_enabled("lookup") is True
    # JSON 키는 규격대로 `copy` 다 — 필드명만 파이썬 사정으로 다르다
    assert "접수번호" in pack.text("unresolved_notice", "기본")


def test_unknown_copy_key_falls_back():
    _write_manifest({"pack_id": "x", "copy": {}})

    assert load_pack().text("nope", "기본 문구") == "기본 문구"


def test_engine_too_old_stops_startup():
    """엔진이 모자란 팩으로 조용히 서비스되는 것보다 안 뜨는 편이 낫다."""
    _write_manifest({"pack_id": "future", "engine_min_version": "99.0.0"})

    with pytest.raises(PackError) as exc:
        load_pack()
    assert "99.0.0" in str(exc.value)
    assert ENGINE_VERSION in str(exc.value)


def test_threshold_inversion_stops_startup():
    """하한이 답변 임계값보다 높으면 related_docs 구간이 사라진다 —
    예외가 나지 않아 알아채기 어려운 종류라 여기서 막는다."""
    _write_manifest({
        "pack_id": "broken",
        "matching": {"qa_match_threshold": 0.5, "related_docs_floor": 0.9},
    })

    with pytest.raises(PackError):
        load_pack()


def test_manifest_that_is_not_an_object():
    path = Path(config.get_settings().pack_dir)
    path.mkdir(parents=True, exist_ok=True)
    (path / "pack.json").write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(PackError):
        load_pack()


def test_profile_falls_back_to_pack_manifest():
    """`profile.json` 이 없으면 매니페스트의 profile 을 쓴다."""
    _write_manifest({
        "pack_id": "mcp-manager",
        "profile": {"organization": "KT", "service_name": "MCP 서버 도우미"},
    })

    profile = load_profile()

    assert profile.service_name == "MCP 서버 도우미"


def test_profile_file_beats_manifest():
    """관리자 화면이 저장하는 곳은 파일이다. 화면에서 고친 값을 팩이 되돌리면 안 된다."""
    _write_manifest({"pack_id": "x", "profile": {"service_name": "팩이 준 이름"}})
    Path(config.get_settings().profile_file).write_text(
        json.dumps({"service_name": "화면에서 저장한 이름"}, ensure_ascii=False),
        encoding="utf-8",
    )

    assert load_profile().service_name == "화면에서 저장한 이름"


def test_broken_manifest_does_not_break_the_screen():
    """팩이 잘못된 것은 기동 때 막을 몫이다.
    화면을 그리는 길목인 `load_profile` 이 여기서 터지면 브랜드 하나로 화면이 통째로 죽는다."""
    path = Path(config.get_settings().pack_dir)
    path.mkdir(parents=True, exist_ok=True)
    (path / "pack.json").write_text("{ 깨진", encoding="utf-8")

    profile = load_profile()          # 터지지 않아야 한다

    assert profile.organization == "KT"          # 코드 기본값으로 계속 간다
    assert profile.service_name == "API Manager 도우미"
