"""AI 프로젝트 미팅 — 역할이 다른 참가자들이 한 주제를 두고 이야기한다.

### 왜 `app/studio/` 에 있는가

LLM 을 부르기 때문이다. 운영 경로(`app/pipeline/retrieve.py`)에서 이 패키지를 import 하면
"운영에서는 LLM 을 쓰지 않는다"는 이 프로젝트의 전제가 깨진다(CLAUDE.md).

### 자료를 읽고 말한다

주제로 프로젝트 문서를 한 번 검색해 발췌를 뽑고, 참가자 **전원이 같은 발췌**를 본다. 사람의
회의에서 같은 자료를 펴 놓고 이야기하는 것과 같다. 참가자마다 따로 검색하면 서로 다른 것을
보고 말해 대화가 엇갈리고, 임베딩 호출도 참가자 수만큼 늘어난다.

발췌가 없으면 **그렇다고 말하고 시작한다.** 자료 없이 그럴듯한 말을 지어내는 것은 이 제품이
가장 피하려는 것이다.

### 한 바퀴씩 돈다

참가자가 차례로 한 번씩 말하는 것을 한 라운드로 본다. 뒤에 말하는 사람은 앞사람의 말을
본다 — 그래야 '토론'이 되고, 안 그러면 같은 자료에 대한 독백 네 개가 된다.

마지막에 **정리**를 한 번 더 부른다. 읽는 사람이 필요한 것은 네 사람의 말이 아니라 그래서
무엇을 하면 되는가다.
"""

from collections.abc import Iterator

from app.core.logging import get_logger, log_event
from app.core.personas import Persona
from app.studio.ask import build_context
from app.core.profile import load_profile
from app.studio.generate import qa_rules
from app.studio.llm import StudioLlm

logger = get_logger("studio.meeting")

# 한 사람이 한 번에 말하는 길이. 길어지면 읽히지 않고, 뒤에 말하는 사람의 프롬프트도
# 그만큼 길어져 컨텍스트가 빨리 찬다.
#
# **프롬프트로 부탁하고, 서버에서 한 번 더 자른다.** 부탁만 하면 작은 모델이 지키지 않는다
# (실제로 2,000자가 넘는 발언이 나왔다, 2026-10-07).
MAX_TURN_CHARS = 700

# 컨텍스트 창을 셋으로 나눈다. 발췌와 이력이 서로를 밀어내지 않게 몫을 미리 정해 둔다 —
# 안 나누면 발췌가 다 먹고 이력이 통째로 사라지거나 그 반대가 된다.
#
#   발췌 45% · 이력 45% · 나머지(고정 문구·주제·역할 설명) 10%
_SOURCE_SHARE = 0.45
_HISTORY_SHARE = 0.45

_TURN_PROMPT = """[회의 주제]
{topic}

[참고 자료] {source_note}
{context}

[지금까지 나온 이야기]
{history}

[당신]
{name}{title} 입니다. {prompt}
{opener}

위 주제에 대해 **{name} 의 눈으로** 한 번 말하세요.

- **앞사람이 한 말을 되풀이하지 마세요.** 같은 생각이면 "동의한다" 고 한 줄로 적고 넘어가고,
  당신만 볼 수 있는 것을 더하세요.
- 참고 자료에 있는 것은 **근거로 쓰고**, 없는 것은 **없다고 말하세요.** 자료에 없는 사실을
  지어내지 마세요. 짐작이면 "확인이 필요하다" 고 적습니다.
- 질문을 남겨도 됩니다. 결론이 날 때까지 혼자 끌고 가지 마세요.
- 발췌에 붙은 **번호(`[1]` · `근거 자료 [2]`)를 글에 쓰지 마세요.** 회의록을 읽는 사람에게는
  그 번호가 가리키는 것이 없습니다. 필요하면 문서 이름으로 적습니다.
- {limit}자 안쪽으로, 문단 한두 개로 씁니다. 제목을 달지 마세요.

- {language_rule}

당신이 할 말만 쓰세요. 이름이나 `{name}:` 같은 머리말을 붙이지 마세요."""

# 첫 발언자에게만 붙는다. 회의를 여는 사람이 주제를 못 박으면 뒤에 말하는 사람들이 그
# 틀 안에서 말한다 — 안 그러면 발췌에 끌려가 **자료 요약**이 되어 버린다(2026-10-07 에
# "이름을 바꾼다면" 을 물었는데 넷 다 포털 기능을 요약했다).
_OPENER = """
**당신이 회의를 엽니다.** 첫 줄에 **이 회의에서 무엇을 정해야 하는지**를 한 문장으로
다시 적고 시작하세요. 주제를 그대로 베끼지 말고, 무엇을 결정하려는 자리인지로 바꿔 적습니다.
    예) 주제가 "이름을 바꾼다면" 이면 → "이 회의에서 정할 것은 새 이름의 후보와 고르는 기준입니다."
그다음 당신의 눈으로 말합니다."""

_SUMMARY_PROMPT = """[회의 주제]
{topic}

[나온 이야기]
{history}

위 회의를 정리하세요. 읽는 사람이 필요한 것은 네 사람의 말이 아니라 **그래서 무엇을 하면
되는가**입니다.

아래 세 묶음으로만 씁니다. 해당하는 것이 없는 묶음은 **통째로 빼세요** — 빈 제목만 남으면
정리가 안 된 것처럼 보입니다.

## 합의된 것
## 갈린 것
## 확인이 필요한 것

- 각 묶음은 `-` 글머리 목록으로, 항목마다 한 줄입니다.
- **나온 말만 적습니다.** 회의에서 안 나온 것을 정리에서 새로 만들지 마세요.
- 누가 말했는지는 적지 않습니다. 결론만 남깁니다.
- {language_rule}"""


def _clip(text: str, limit: int) -> str:
    """길면 자르고 **잘렸다고 적는다.** 조용히 자르면 읽는 사람이 말이 끊긴 이유를 모른다."""
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + " …(길어서 줄였습니다)"


def _history(turns: list[dict], budget: int) -> str:
    """지금까지 나온 이야기. **예산을 넘으면 오래된 것부터 뺀다.**

    뒤에서부터 채우는 이유: 바로 앞사람의 말을 보는 것이 가장 중요하다. 앞쪽을 남기고
    뒤를 자르면 "앞사람 말을 되풀이하지 마세요" 가 지켜질 수 없다.

    뺐으면 **뺐다고 적는다.** 말없이 사라지면 참가자가 안 나온 이야기를 다시 꺼낸다.
    """
    if not turns:
        return "(아직 없습니다. 당신이 첫 발언입니다.)"

    kept: list[str] = []
    used = 0
    for t in reversed(turns):
        line = f"[{t['name']}] {t['text']}"
        if kept and used + len(line) > budget:
            kept.insert(0, f"(앞선 발언 {len(turns) - len(kept)}건은 길어서 줄였습니다)")
            break
        kept.insert(0, line)
        used += len(line)
    return "\n\n".join(kept)


def run(topic: str, personas: list[Persona], hits: list[dict], rounds: int = 1,
        model: str | None = None) -> Iterator[tuple[str, dict]]:
    """회의를 진행하며 발언이 끝날 때마다 하나씩 내보낸다.

    `("turn", {...})` 과 `("summary", {...})` 를 순서대로 돌려준다. 화면이 기다리지 않고
    한 사람씩 그릴 수 있어야 한다 — 참가자 넷이면 한 바퀴에 수십 초가 걸린다.

    **예외를 밖으로 내지 않는다.** 한 사람이 실패해도 회의는 이어지고, 그 자리는 '말하지
    못했다'로 남는다. 모델이 하나 죽었다고 회의 전체가 사라지면 앞의 발언까지 잃는다.
    """
    # 참가자마다 모델이 다를 수 있다. **발췌는 한 번만 만든다** — 모델마다 다시 자르면
    # 같은 회의에서 사람마다 다른 분량을 보게 되고, 그때 대화가 어긋나는 이유를 알 수 없다.
    # 예산은 기본 모델 기준으로 잡는다.
    base = StudioLlm(model=model or None)
    # 참가자마다 컨텍스트 창이 다를 수 있지만 **가장 작은 쪽에 맞춘다** — 큰 모델 기준으로
    # 만들면 작은 모델에서만 조용히 잘려, 그 사람 발언만 이상해지는 이유를 알 수 없다.
    budget = base.source_budget_chars()
    context = build_context(hits, budget=int(budget * _SOURCE_SHARE)) if hits else ""
    history_budget = int(budget * _HISTORY_SHARE)
    llms: dict[str, StudioLlm] = {}

    def _llm(name: str) -> StudioLlm:
        """같은 모델은 한 번만 만든다. 참가자 넷이 같은 모델이면 객체도 하나다."""
        if not name:
            return base
        if name not in llms:
            llms[name] = StudioLlm(model=name)
        return llms[name]
    source_note = ("아래 발췌는 이 프로젝트의 자료에서 주제로 찾은 것입니다."
                   if hits else "**이 주제로 찾은 자료가 없습니다.** 아는 것처럼 말하지 마세요.")

    # 언어 규칙은 **발언 프롬프트 안에** 둔다. `qa_rules()` 의 system 에도 있지만 거기서는
    # 여섯 번째 항목이라 묻힌다 — 실제로 참가자 하나가 영어로 말하기 시작했다(2026-10-07).
    language_rule = load_profile().language_rule()

    turns: list[dict] = []
    for round_no in range(1, max(1, rounds) + 1):
        for persona in personas:
            prompt = _TURN_PROMPT.format(
                topic=topic, context=context or "(없음)", source_note=source_note,
                history=_history(turns, history_budget), name=persona.name,
                title=f"({persona.title})" if persona.title else "",
                prompt=persona.prompt or "맡은 자리에서 보이는 것을 말합니다.",
                # 회의를 여는 한 사람에게만. 매번 붙이면 참가자마다 주제를 다시 적어
                # 회의록이 같은 문장으로 도배된다.
                opener=_OPENER if (round_no == 1 and not turns) else "",
                limit=MAX_TURN_CHARS, language_rule=language_rule,
            )
            # 화면이 **누가 어느 모델로 말했는지** 보여 줄 수 있어야 한다. 섞어 쓰면
            # 답의 성격이 달라지는데, 어느 모델이 말한 것인지 모르면 비교가 안 된다.
            speaker = _llm(persona.model if not model else "")
            try:
                # 프롬프트도 마지막으로 한 번 맞춘다. 발췌·이력을 나눠 담아도 역할 설명이
                # 길면 넘칠 수 있다. 자르면 로그가 남는다.
                text = speaker.chat(speaker.fit(prompt, label="meeting turn"),
                                    system=qa_rules()).strip()
            except Exception as exc:          # noqa: BLE001 - 한 사람이 죽어도 회의는 이어진다
                log_event(logger, "meeting turn failed", persona=persona.persona_id,
                          error=str(exc))
                text = ""
            # **서버에서 한 번 더 자른다.** 프롬프트의 부탁을 작은 모델이 지키지 않는다.
            text = _clip(text, MAX_TURN_CHARS)
            turn = {
                "persona_id": persona.persona_id, "name": persona.name,
                "title": persona.title, "round": round_no, "text": text,
                "model": speaker.model,
            }
            if text:
                turns.append(turn)
            yield "turn", turn

    if not turns:
        return
    try:
        # 정리는 **기본 모델**이 한다. 참가자 한 명의 모델로 하면 그 사람 말투로 정리된다.
        summary = base.chat(
            base.fit(_SUMMARY_PROMPT.format(
                topic=topic, history=_history(turns, history_budget * 2),
                language_rule=language_rule), label="meeting summary"),
            system=qa_rules()).strip()
    except Exception as exc:                  # noqa: BLE001
        log_event(logger, "meeting summary failed", error=str(exc))
        summary = ""
    yield "summary", {"text": summary, "model": base.model}
