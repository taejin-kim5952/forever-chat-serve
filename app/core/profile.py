"""납품처 프로필 — 조직 이름 · 서비스 이름 · 도메인 소개 · 언어.

이 서비스는 특정 조직 전용이 아니라 **어느 조직에나 설치할 수 있는 형태**를 목표로 한다.
그런데 조직 이름과 도메인 설명이 화면 마크업과 생성 프롬프트에 직접 박혀 있으면 설치할
때마다 소스를 고쳐야 한다 — 그건 배포가 아니라 포크다. 조직마다 달라지는 문자열만 여기
한 파일로 모았다.

### 파일이 없으면 지금까지의 값

`data/profile.json` 이 없으면 기본값(KT / API Manager 도우미 / 한국어)이 나온다. 기존
설치는 아무것도 하지 않아도 동작이 달라지지 않는다. 새 조직에 설치할 때만 파일을 만든다.

### 왜 언어가 여기 있나 ★

`app/studio/korean.py` 의 한국어 판정이 **생성 결과 필터**로 쓰인다. 한국어가 아닌 조직에
그대로 설치하면 만든 초안이 전부 버려지고, 로그에 `dropped_language` 만 쌓이면서
"완료, 0건"으로 끝난다. 예외가 나지 않는 종류의 실패라 원인을 찾는 데 오래 걸린다.
그래서 언어를 프로필로 올려, **판정기가 없는 언어는 막지 않고 통과**시킨다.

### 로고만 길이를 자르는 이유

로고 자리는 34x34 정사각형에 글자를 그린다(퍼블 산출물). 줄임표를 넣을 공간이 없어서 값이
들어올 때 자르고 로그를 남긴다. 서비스 이름·설명은 **자르지 않는다** — 가로로 밀리는 것은
화면에서 바로 보이지만 잘린 이름은 눈치채기 어렵고, 잘린 이름은 틀린 이름이다.
이미지 로고나 긴 조직명이 실제로 필요해지면 퍼블에 보완을 요청한다(`docs/퍼블요청/`).
"""

from pathlib import Path

from pydantic import BaseModel

from app.core.config import get_settings
from app.core.jsonstore import read_json, write_json_atomic
from app.core.logging import get_logger, log_event

logger = get_logger("core.profile")

# 로고 정사각형에 들어가는 최대 글자 수.
LOGO_MAX_CHARS = 4

# 언어별 생성 규칙 문장. 프롬프트의 언어 규칙 줄에 그대로 들어간다.
# **판정기가 있는 언어만** 여기 적는다 — 없는 언어를 적으면 규칙만 있고 검증이 없는 상태가 된다.
_LANGUAGE_RULES: dict[str, str] = {
    "ko": "**한국어로만 쓴다.** 영어·중국어 등 다른 언어의 문장을 섞지 않는다.",
}


class Profile(BaseModel):
    """기본값은 **지금 화면·프롬프트에 박혀 있던 값 그대로**다. 바꾸면 기존 설치의 동작이 바뀐다."""

    # 로고 자리(정사각형)에 들어간다. 길면 잘린다.
    organization: str = "KT"
    # 화면 제목과 브라우저 탭.
    service_name: str = "API Manager 도우미"
    # 챗봇 헤더의 한 줄 소개.
    service_desc: str = "API 등록 · 그룹 · 템플릿"
    # 생성 프롬프트의 첫 문장에 들어간다 — "당신은 {domain_intro}를 담당하는 사내 도우미입니다".
    # 조사 '를'이 뒤에 붙으므로 명사구로 쓴다.
    domain_intro: str = "KT OpenAPI Portal 'API Manager' 사용 가이드"
    # 생성 결과 언어 판정. 판정기가 있는 값은 `_LANGUAGE_RULES` 참고.
    language: str = "ko"

    def logo_text(self) -> str:
        text = self.organization.strip()
        if len(text) <= LOGO_MAX_CHARS:
            return text
        log_event(
            logger, "organization name truncated for logo",
            organization=self.organization, limit=LOGO_MAX_CHARS,
        )
        return text[:LOGO_MAX_CHARS]

    def language_rule(self) -> str:
        """생성 프롬프트에 넣을 언어 규칙 한 줄."""
        return _LANGUAGE_RULES.get(
            self.language,
            f"**{self.language} 로만 쓴다.** 다른 언어의 문장을 섞지 않는다.",
        )

    def has_language_filter(self) -> bool:
        """생성 결과를 실제로 걸러낼 판정기가 있는 언어인가."""
        return self.language in _LANGUAGE_RULES

    def template_values(self) -> dict[str, str]:
        """화면 치환에 쓸 값들(`data-brand` 포맷 문자열의 자리표시자)."""
        return {
            "organization": self.logo_text(),
            # 로고가 아닌 곳(본문 등)에서 자르지 않은 조직명이 필요할 때.
            "organization_full": self.organization,
            "service_name": self.service_name,
            "service_desc": self.service_desc,
        }


def save_profile(profile: Profile) -> None:
    """관리자 화면(설정 → 납품처)이 저장한다.

    저장 즉시 반영된다 — 화면은 매 요청 `load_profile()` 을 거치므로 재시작이 필요 없다.
    다만 `/docs` 제목만은 기동 시 한 번 정해지므로 그대로다(`app/main.py`).
    """
    write_json_atomic(Path(get_settings().profile_file), profile.model_dump_json(indent=2))
    log_event(logger, "profile saved", organization=profile.organization, language=profile.language)


def load_profile() -> Profile:
    """매번 파일을 다시 읽는다 — `runtime_config` 와 같은 이유로 재시작 없이 반영된다.

    화면 렌더와 생성 배치 시작 시점에만 불리므로 요청당 비용이 아니다.
    """
    data = read_json(Path(get_settings().profile_file))
    if data is None:
        return Profile()
    try:
        return Profile(**data)
    except ValueError as exc:
        # 여기서 예외를 올리면 프로필 오타 하나로 화면이 통째로 안 뜬다. 기본값으로 계속하되
        # 조용히 넘어가지는 않는다 — 브랜드가 기본값으로 나오는 이유가 로그에 남아야 한다.
        log_event(logger, "profile file unreadable — using defaults", error=str(exc))
        return Profile()
