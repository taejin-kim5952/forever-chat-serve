"""AI 프로젝트 미팅의 **참가자**(기획자·개발자·운영자·PM…).

관리자가 미리 만들어 두고, 토론을 여는 사람이 그중에서 고른다.

### 왜 팩(`packs/`)이 아니라 설치 단위인가

역할의 성격은 프로젝트가 달라도 같다 — 기획자는 어느 프로젝트에서나 기획자다. 프로젝트마다
다시 만들게 하면 같은 글을 여러 벌 적게 되고, 한쪽만 고쳐져 같은 이름의 참가자가 프로젝트에
따라 다르게 말한다. 그래서 브랜드 로고(`data/brand/`)와 같은 자리에 둔다.

### `prompt` 는 **말투가 아니라 보는 눈**이다

"기획자처럼 말해 주세요" 가 아니라 "무엇을 먼저 보는 사람인가"를 적는다. 말투만 주면 네
참가자가 같은 말을 어미만 바꿔 되풀이한다 — 실제로 그렇게 되는지는 프롬프트를 고칠 때마다
소량으로 돌려 눈으로 봐야 한다(CLAUDE.md).
"""

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.jsonstore import read_json, write_json_atomic
from app.core.logging import get_logger, log_event
from pathlib import Path

logger = get_logger("core.personas")

# 한 토론에 들어갈 수 있는 수. 더 많으면 한 바퀴가 너무 길어 읽히지 않고, 모델 호출도
# 참가자 수만큼 늘어난다(항목당 수십 초다).
MAX_IN_MEETING = 6

# 처음 들어온 설치가 빈 화면을 보지 않게 두는 기본값. **지우거나 고칠 수 있다** — 납품처마다
# 역할 이름이 다르므로 박아 두지 않는다.
DEFAULTS: list[dict] = [
    {
        "persona_id": "planner",
        "name": "기획자",
        "title": "서비스 기획",
        "prompt": "사용자가 겪는 문제와 쓰임새를 먼저 봅니다. 누가 언제 이걸 쓰는지, "
                  "지금 방식으로는 무엇이 불편한지를 묻습니다. 기능보다 목적을 따집니다.",
    },
    {
        "persona_id": "developer",
        "name": "개발자",
        "title": "구현",
        "prompt": "만들 수 있는지와 무엇이 걸리는지를 먼저 봅니다. 데이터가 어디서 오는지, "
                  "기존 구조와 어긋나는 곳이 어디인지, 예외 상황에 무엇이 깨지는지를 짚습니다.",
    },
    {
        "persona_id": "operator",
        "name": "운영자",
        "title": "운영",
        "prompt": "만든 뒤에 누가 어떻게 돌보는지를 먼저 봅니다. 장애가 났을 때 무엇을 보는지, "
                  "손이 얼마나 가는지, 사람이 실수할 자리가 어디인지를 짚습니다.",
    },
    {
        "persona_id": "pm",
        "name": "PM",
        "title": "일정·우선순위",
        "prompt": "무엇을 먼저 하고 무엇을 미룰지를 봅니다. 범위가 넓어지는 곳을 잡고, "
                  "빠진 전제와 결정이 필요한 지점을 분명히 합니다. 결론을 내는 쪽으로 몹니다.",
    },
]


class Persona(BaseModel):
    """참가자 한 명."""

    persona_id: str
    name: str
    # 이름 아래 한 줄. 화면에서 누가 누군지 가르는 데 쓴다.
    title: str = ""
    # 이 사람이 **무엇을 먼저 보는가**. 모델에게 그대로 간다.
    prompt: str = ""
    # 이 참가자가 쓸 모델. **비우면 설치 기본 답변 모델**을 쓴다.
    #
    # 역할마다 잘하는 모델이 다르다 — 긴 글을 꼼꼼히 읽는 쪽과 짧고 날카롭게 짚는 쪽이
    # 같지 않다. 다만 **서로 다른 모델을 섞으면 GPU 적재가 발언마다 일어난다**(세 모델을
    # 합치면 GPU 에 다 안 올라간다, CLAUDE.md). 느려도 되는 자리에서만 섞는다.
    model: str = ""
    enabled: bool = True
    sort: int = 0


class PersonaStore(BaseModel):
    personas: list[Persona] = Field(default_factory=list)


def _path() -> Path:
    return Path(get_settings().personas_file)


def load() -> PersonaStore:
    """없으면 **기본값으로 시작한다.** 빈 목록을 주면 처음 들어온 사람이 무엇을 만들어야
    할지 모른 채 빈 화면을 본다. 저장하기 전까지 파일은 만들지 않는다."""
    data = read_json(_path())
    if not isinstance(data, dict):
        return PersonaStore(personas=[Persona(**p, sort=i) for i, p in enumerate(DEFAULTS)])
    try:
        return PersonaStore(**data)
    except ValueError as exc:
        log_event(logger, "personas unreadable", path=str(_path()), error=str(exc))
        return PersonaStore(personas=[Persona(**p, sort=i) for i, p in enumerate(DEFAULTS)])


def save(store: PersonaStore) -> None:
    for i, p in enumerate(sorted(store.personas, key=lambda x: x.sort)):
        p.sort = i
    write_json_atomic(_path(), store.model_dump_json(indent=2))
    log_event(logger, "personas saved", count=len(store.personas))


def enabled() -> list[Persona]:
    """토론에 부를 수 있는 사람. 꺼 둔 참가자는 고르는 목록에도 나오지 않는다."""
    return sorted((p for p in load().personas if p.enabled), key=lambda p: p.sort)


def pick(persona_ids: list[str]) -> list[Persona]:
    """고른 순서가 아니라 **정해 둔 순서**로 돌려준다.

    토론은 순서대로 발언하므로, 고른 순서를 쓰면 같은 참가자 조합인데 부른 순서에 따라
    대화가 달라진다. 관리자가 정한 순서를 쓰면 결과를 견줄 수 있다.
    """
    wanted = set(persona_ids)
    return [p for p in enabled() if p.persona_id in wanted][:MAX_IN_MEETING]
