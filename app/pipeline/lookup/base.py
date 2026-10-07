"""라이브 조회 계약 (개발계획서 §4.3).

사전 생성 QA 로는 답할 수 없는 질문이 있다 — "내 서버 지금 왜 죽었어", "이 서버 툴 뭐야".
값이 수시로 바뀌어서 미리 답을 만들어 두면 **틀린 답을 확신을 갖고 말하는** 챗봇이 된다.

### 지켜야 할 선

  - **LLM 을 부르지 않는다.** 데이터를 문장으로 만드는 일은 템플릿이 한다
  - **인텐트 판정에 임베딩을 쓰지 않는다.** 사전 + 정규식으로 충분하고, 결정적이라 재현된다
  - **실패하면 조용히 폴백한다.** 사이트 API 가 죽어도 챗봇은 절차 안내를 계속한다
  - **권한을 판단하지 않는다.** 사용자 자격을 그대로 넘기고, 사이트가 403 을 주면 그대로 안내한다
  - **조회 시각을 함께 낸다.** 없으면 사용자가 캐시된 값을 현재값으로 믿는다

### 프로바이더는 팩이 아니라 코드에 둔다

외부 HTTP 호출이라 타임아웃·시험 관리가 필요하고, 팩(데이터)에 실행 코드를 넣으면
**팩 반입이 곧 코드 반입**이 된다. 팩에는 어떤 프로바이더를 켤지와 문구만 둔다.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass
class Principal:
    """질문한 사람. 챗봇은 이 값을 **판단하지 않고 그대로 사이트에 넘긴다.**

    :param headers: 사이트 API 에 실어 보낼 자격 (세션 쿠키 · SSO 헤더)
    """

    authenticated: bool = False
    headers: dict[str, str] = field(default_factory=dict)

    def anonymous(self) -> bool:
        # 자격이 없으면 라이브 경로를 아예 타지 않는다 (계획서 §4.5).
        return not self.authenticated


@dataclass
class LookupIntent:
    """무엇을 물어본 것으로 봤는가.

    :param confidence: 사전 매칭 강도(0~1). 임계 미만이면 무시한다 —
                       엉뚱한 서버를 조회해 답하는 것이 답을 못 하는 것보다 나쁘다
    """

    intent_id: str
    entities: dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0


@dataclass
class Action:
    """화면 버튼 → 사이트 딥링크. 챗봇이 답만 하고 끝내지 않게 한다."""

    label: str
    url: str


@dataclass
class LiveAnswer:
    """조회 결과를 문장으로 만든 것.

    :param stale: 캐시를 썼는가. 화면이 "N초 전 기준" 으로 표기한다
    """

    text: str
    fetched_at: datetime
    source_label: str
    actions: list[Action] = field(default_factory=list)
    stale: bool = False


class LookupProvider(Protocol):
    """인텐트 하나를 맡는다.

    셋을 나눈 이유는 각각 실패하는 방식이 다르기 때문이다 — `match` 는 조용히 비껴가고,
    `fetch` 는 망·권한으로 실패하며, `render` 는 값이 모자라 실패한다. 한 덩어리로 두면
    "왜 라이브로 안 갔는지" 를 로그에서 가릴 수 없다.
    """

    id: str

    def match(self, question: str, entities: dict[str, str]) -> LookupIntent | None:
        """이 프로바이더가 답할 질문인가. 아니면 None."""
        ...

    def fetch(self, intent: LookupIntent, principal: Principal) -> dict | None:
        """사이트 API 를 부른다. 실패·권한 없음이면 None — 호출부가 폴백한다."""
        ...

    def render(self, intent: LookupIntent, data: dict) -> LiveAnswer | None:
        """템플릿으로 문장을 만든다. 값이 모자라면 None."""
        ...
