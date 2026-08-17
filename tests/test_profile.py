"""납품처 프로필 — 파일이 없을 때 기존 동작이 그대로인지, 있을 때 실제로 바뀌는지.

가장 중요한 것은 **파일이 없을 때 아무것도 달라지지 않는 것**이다. 기존 설치는 프로필을
만들지 않으므로, 여기가 깨지면 배포된 화면과 프롬프트가 조용히 바뀐다.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.core.profile import Profile, load_profile
from app.main import app
from app.studio.generate import qa_rules
from app.studio.korean import is_expected_language


@pytest.fixture
def client():
    return TestClient(app)


def _write_profile(settings, **values) -> None:
    from pathlib import Path
    Path(settings.profile_file).write_text(
        json.dumps(values, ensure_ascii=False), encoding="utf-8",
    )


# ─────────────────────────────────────────────── 파일이 없을 때 = 지금까지의 값


def test_defaults_match_shipped_strings():
    profile = load_profile()
    assert profile.organization == "KT"
    assert profile.service_name == "API Manager 도우미"
    assert profile.language == "ko"


def test_prompt_is_unchanged_without_profile_file():
    """기본 프로필의 프롬프트는 프로필 도입 전과 **글자 하나까지** 같아야 한다."""
    rules = qa_rules()
    assert rules.startswith("당신은 KT OpenAPI Portal 'API Manager' 사용 가이드를 담당하는 사내 도우미입니다.")
    assert "6. **한국어로만 쓴다.** 영어·중국어 등 다른 언어의 문장을 섞지 않는다." in rules


def test_chat_page_shows_default_brand(client):
    html = client.get("/").text
    assert ">KT</span>" in html
    assert "API Manager 도우미" in html


# ─────────────────────────────────────────────────────── 파일이 있을 때 = 치환


def test_chat_page_uses_profile(client, isolated_data):
    _write_profile(
        isolated_data,
        organization="ACME", service_name="사내 도우미", service_desc="주문 · 배송 문의",
    )
    html = client.get("/").text

    assert ">ACME</span>" in html
    assert "사내 도우미" in html
    assert "주문 · 배송 문의" in html
    # 마크업(클래스·구조)은 그대로여야 한다 — 퍼블 산출물을 다시 받았을 때 배선이 남아야 한다.
    assert 'class="chat_logo" data-brand="{organization}"' in html
    assert "KT" not in html


def test_admin_page_keeps_fixed_labels(client, isolated_data):
    """브랜드만 바뀌고 화면 고정 문구('관리자')는 남는다."""
    _write_profile(isolated_data, service_name="사내 도우미")
    html = client.get("/admin").text
    assert "사내 도우미 · 관리자" in html


def test_logo_is_truncated_but_name_is_not(client, isolated_data):
    """로고 정사각형만 자른다. 서비스 이름은 자르지 않는다 — 잘린 이름은 틀린 이름이다."""
    long_name = "아주아주긴서비스이름입니다"
    _write_profile(isolated_data, organization="LONGCORP", service_name=long_name)
    html = client.get("/").text

    assert ">LONG</span>" in html
    assert long_name in html


def test_prompt_uses_profile_domain(isolated_data):
    _write_profile(isolated_data, domain_intro="사내 전자결재 사용 안내")
    assert qa_rules().startswith("당신은 사내 전자결재 사용 안내를 담당하는 사내 도우미입니다.")


# ────────────────────────────────────────────────────────────────── 언어


def test_korean_filter_still_applies_for_ko():
    assert is_expected_language("API 등록은 어떻게 하나요?", "ko")
    assert not is_expected_language("How do I register the API for this?", "ko")


def test_other_languages_are_not_dropped():
    """판정기가 없는 언어를 한국어 규칙으로 막으면 초안이 전부 버려진다 — 그걸 막는다."""
    assert is_expected_language("How do I register the API for this?", "en")
    assert not is_expected_language("   ", "en")


def test_language_rule_falls_back_for_unknown_language():
    assert "한국어" in Profile(language="ko").language_rule()
    assert "en" in Profile(language="en").language_rule()


def test_unknown_language_has_no_filter():
    assert Profile(language="ko").has_language_filter()
    assert not Profile(language="en").has_language_filter()


# ─────────────────────────────────────────────────────────── 망가진 프로필


def test_broken_profile_falls_back_to_defaults(isolated_data):
    """프로필 오타 하나로 화면이 통째로 죽으면 안 된다."""
    from pathlib import Path
    Path(isolated_data.profile_file).write_text("{ 이건 JSON 이 아닙니다", encoding="utf-8")
    assert load_profile().organization == "KT"


def test_unknown_placeholder_leaves_markup_alone(client):
    """`data-brand` 에 모르는 이름이 있어도 페이지는 떠야 한다."""
    from app.main import _apply_brand
    html = '<span data-brand="{없는이름}">원문</span>'
    assert _apply_brand(html) == html
