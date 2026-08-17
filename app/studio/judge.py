"""생성된 QA 초안을 근거 발췌와 대조해 채점한다 — 검수 전 자동 걸러내기.

1차 프로젝트(`forever-chat/app/eval/llm_judge.py`)의 판정자를 옮겨 왔다. **채점 대상이 다르다.**

```
1차 : 질문 → 파이프라인이 즉석에서 만든 답 → 골든셋의 기대 답변과 비교
후속: 미리 만들어 둔 초안(질문·답변) → 그 답을 만든 근거 발췌와 대조
```

후속에는 골든셋이 없다. 사람이 쓴 기대 답변이 없는 대신 **근거 발췌가 있다.** 그래서 묻는 것을
"기대 답변과 같은가"에서 **"발췌에 있는 사실만 말하는가"**로 바꿨다. 이 서비스가 실제로 막아야
하는 것이 그것이다 — 검수자가 원문과 대조하지 못한 채 그럴듯한 문장을 승인하는 일.

### 판정 모델은 답변 모델과 달라야 한다 ★

같은 모델이 답을 쓰고 자기 답을 채점하면 점수가 후해진다(자기 채점 편향). 문서를 잘못 읽고
답을 썼다면 채점할 때도 같은 오독을 반복하므로, 틀린 답에 만점이 나온다. 그래서 판정 모델은
**따로 지정했을 때만** 동작한다. 비워 두면 채점을 건너뛴다 — 같은 모델로 자기 채점을 하느니
채점이 없는 편이 낫다. 있으나 마나 한 점수가 붙으면 검수자가 그 숫자를 믿는다.

### 판정 실패는 0점이 아니라 '판정 없음'

1차는 JSON 파싱이 실패하면 1점(최악)을 줬다. 그러면 모델이 형식을 흘린 것만으로 멀쩡한 초안이
버려진다. 여기서는 `score=0` 으로 두고 **자동 반영에서만 뺀다.** 초안 목록에는 그대로 남아
사람이 판단할 수 있다.
"""

import json
import re

from app.core.logging import get_logger, log_event
from app.studio.llm import StudioLlm

logger = get_logger("studio.judge")

# 판정 안 됨. 점수가 아니라 '모름'이라는 표시다.
NOT_JUDGED = 0

_JUDGE_PROMPT = """당신은 사내 FAQ 답변을 사람이 검수하기 전에 걸러내는 평가자입니다.
[근거 발췌]에 비추어 [답변]을 1~5점으로 채점하세요.

- 5점: 발췌에 있는 사실만으로 질문에 정확히 답한다
- 4점: 대체로 정확하나 표현이 아쉽거나 사소한 내용이 빠졌다
- 3점: 답이 되기는 하나 모호하거나, 발췌에서 확인되지 않는 문장이 섞였다
- 2점: 질문에 절반만 답했거나 중요한 부분이 발췌와 어긋난다
- 1점: 질문과 무관하거나, 발췌에 없는 내용을 사실처럼 말한다(환각)

[질문]
{question}

[답변]
{answer}

[근거 발췌]
{context}

반드시 아래 JSON 한 줄로만 답하세요. 다른 말을 덧붙이지 마세요.
{{"score": <1-5 정수>, "reason": "<한 줄 이유>"}}"""

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def parse_verdict(raw: str) -> tuple[int, str]:
    """`{"score": n, "reason": "..."}` 를 읽는다. 못 읽으면 `(NOT_JUDGED, 사유)`."""
    match = _JSON_BLOCK.search(raw)
    if not match:
        return NOT_JUDGED, f"판정 형식을 읽지 못했습니다: {raw[:80]}"
    try:
        data = json.loads(match.group(0))
        score = int(data.get("score", NOT_JUDGED))
        reason = str(data.get("reason", "")).strip()
    except (json.JSONDecodeError, TypeError, ValueError):
        return NOT_JUDGED, f"판정 형식을 읽지 못했습니다: {raw[:80]}"

    if not 1 <= score <= 5:
        return NOT_JUDGED, f"점수 범위를 벗어났습니다: {score}"
    return score, reason


def judge_answer(llm: StudioLlm, question: str, answer: str, context: str) -> tuple[int, str]:
    """초안 한 건을 채점한다. 판정이 실패해도 예외를 올리지 않는다.

    채점은 부가 정보다. 판정 모델이 죽었다고 수십 분짜리 생성 배치를 통째로 실패시키면,
    그때까지 만든 초안까지 같이 버리게 된다.
    """
    prompt = _JUDGE_PROMPT.format(
        question=question, answer=answer, context=llm.fit(context, label="judge"),
    )
    try:
        # JSON 만 내보내게 한다 — 추론 모델이 사고 과정으로 예산을 다 써버리는 것을 막는다
        # (app/studio/llm.py 의 `json_format` 주석 참고).
        raw = llm.chat(prompt, json_format=True)
    except Exception as exc:  # noqa: BLE001 — 판정 실패가 생성을 멈추지 않는다
        log_event(logger, "judging failed", question=question[:40], error=str(exc))
        return NOT_JUDGED, f"판정을 실행하지 못했습니다: {exc}"

    score, reason = parse_verdict(raw)
    if score == NOT_JUDGED:
        log_event(logger, "judge verdict unreadable", question=question[:40], reason=reason)
    return score, reason
