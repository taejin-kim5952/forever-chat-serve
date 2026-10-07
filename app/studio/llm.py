"""스튜디오 전용 LLM 호출 한 겹.

이 프로젝트에서 LLM을 부르는 **유일한 자리**다. 운영(serve)에는 GPU가 없어 이 모듈이 실행되면
안 되고, 부르는 쪽(`app/api/studio_generate.py`)이 `APP_MODE=studio` 를 먼저 확인한다.
여기 코드가 사용자 요청 경로로 새어 들어가면 응답이 1~3분이 되고 프로젝트 전제가 뒤집힌다.

1차 프로젝트에서 실제로 시간을 가장 많이 잡아먹은 두 가지를 여기서 막는다.

- **빈 응답**: 추론(thinking) 모델은 사고 과정만 내보내고 `content` 를 비운다. 답변이 통째로
  사라지는데 예외는 안 난다. `think=False` 로 두고, 그래도 비어 오면 **예외로 올린다** —
  조용히 건너뛰면 "왜 아무것도 안 만들어졌지"를 한참 헤맨다.
- **조용한 잘림**: 프롬프트가 `num_ctx` 를 넘으면 초과분이 말없이 잘린다. 그래서 발췌를
  **미리** 예산만큼 자르고, 자른 사실을 로그로 남긴다. 잘린 채로 생성된 답변은 문장 중간에서
  끝나거나 근거가 반쯤 사라진 상태가 된다.
"""

import ollama

from app.core.config import get_settings
from app.core.logging import get_logger, log_event

logger = get_logger("studio.llm")

# 토큰당 글자 수. 발췌를 얼마나 넣을 수 있는지가 이 값 하나로 정해진다.
#
# **2026-10-07 에 실제로 쟀다.** 우리 문서 68건을 토크나이저에 통과시키니 1토큰당
# 평균 2.01자, 가장 빡빡한 문서(코드·영문이 많은 것)도 1.70자였다. 같은 자료를
# `qwen3.5:4b` 에 넣었을 때는 15,710자 → 7,252 토큰(2.17자)이었다.
#
# 그 전에는 1.0 이었다. 안전한 쪽이지만 **창의 절반을 비워 두는** 값이라, AI 답변이
# 읽는 근거가 실제로 넣을 수 있는 양의 절반도 안 됐다. 1.6 은 가장 빡빡한 문서(1.70)
# 보다도 낮아 여유가 남는다 — 넘치면 Ollama 가 **조용히** 앞부분만 읽으므로 여기서
# 후하게 잡으면 안 된다.
#
# 자료 성격이 크게 바뀌면(영문·코드 비중이 늘면) 다시 재야 한다.
_CHARS_PER_TOKEN = 1.6
# 규칙·형식 안내와 모델이 쓸 여유. 발췌에 쓸 수 있는 예산에서 미리 빼둔다.
_PROMPT_OVERHEAD_CHARS = 1500


class EmptyLlmResponse(RuntimeError):
    """모델이 본문 없이 응답했다. 대개 추론 모델 + `think` 설정 문제다."""


# 추론 모델은 사고 과정을 **본문에 쏟아내** 출력 예산을 다 쓴다. `think=False` 와
# `format="json"` 으로도 막지 못한 경우가 있어(2026-08-17 `qwen3:4b` 채점에서 영어 사고 과정
# 4,071자 뒤 JSON 없이 잘림) 프롬프트 스위치를 함께 쓴다. Qwen3 계열이 이 방식을 쓴다.
_NO_THINK_PREFIX = "/no_think\n"
_NO_THINK_MODELS = ("qwen3",)


def _needs_no_think(model: str) -> bool:
    name = model.lower()
    return any(key in name for key in _NO_THINK_MODELS)


# 임베딩 전용 모델은 생성에 못 쓴다. 이름으로 거르는 어림짐작이지만, 목록에 남겨 두면
# 고를 수 있게 되고 고르는 순간 배치가 통째로 실패한다.
_EMBED_HINTS = ("embed", "bge", "gte", "e5")


def installed_models() -> list[str]:
    """Ollama 에 실제로 받아둔 생성 모델 목록.

    화면의 모델 선택은 원래 하드코딩이었다. 그러다 보니 이 PC에 없는 모델이 목록에 있고
    (`qwen3:14b`) 있는 모델은 없어서(`gemma4:12b`) 고를 수가 없었다. 목록을 서버가 물어본다.
    """
    settings = get_settings()
    try:
        raw = ollama.Client(host=settings.ollama_host).list()
    except Exception as exc:  # noqa: BLE001 — Ollama 가 꺼져 있어도 화면은 떠야 한다
        log_event(logger, "listing ollama models failed", error=str(exc))
        return []

    names = []
    for entry in raw.get("models", []):
        name = entry.get("model") or entry.get("name") or ""
        if name and not any(hint in name.lower() for hint in _EMBED_HINTS):
            names.append(name)
    return sorted(names)


class StudioLlm:
    def __init__(self, model: str | None = None, host: str | None = None):
        settings = get_settings()
        self.model = model or settings.ollama_llm_model
        self.client = ollama.Client(host=host or settings.ollama_host)
        self.num_ctx = settings.ollama_num_ctx
        self.num_predict = settings.ollama_num_predict
        self.think = settings.ollama_think
        self.think_num_predict = settings.ollama_think_num_predict

    def source_budget_chars(self) -> int:
        """프롬프트에 넣을 수 있는 발췌 길이. 컨텍스트 창에서 출력 몫과 규칙 몫을 뺀 값."""
        usable = (self.num_ctx - self.num_predict) * _CHARS_PER_TOKEN
        return max(500, int(usable) - _PROMPT_OVERHEAD_CHARS)

    def fit(self, text: str, label: str = "") -> str:
        """발췌를 예산에 맞춘다. 잘랐으면 반드시 로그를 남긴다 — 조용히 자르면 원인 추적이 안 된다."""
        budget = self.source_budget_chars()
        if len(text) <= budget:
            return text
        log_event(
            logger, "source truncated to fit context window",
            label=label, original_chars=len(text), budget_chars=budget, num_ctx=self.num_ctx,
        )
        return text[:budget]

    def chat(self, prompt: str, system: str | None = None, json_format: bool = False,
             think: bool = False, on_think=None) -> str:
        """`json_format=True` 면 Ollama 에게 **JSON 만** 내보내게 한다.

        채점처럼 기계가 읽을 응답에 쓴다. 형식을 모델의 선의에 맡기지 않는다 — 형식이 깨지면
        멀쩡한 답변이 '판정 실패'로 걸러진다.

        추론 모델에는 이것만으로 부족해서 `/no_think` 도 함께 붙인다(위 주석).

        ### `think=True` — 사고 과정을 **받는** 경우

        사용자가 `추론 과정 보기` 를 켠 답변 한 건에만 쓴다. 그때는 `/no_think` 를 붙이지
        않고 Ollama 에게 생각을 내보내게 한다. **본문과 따로 온다**(`message.thinking`) —
        2026-08-17 에 본문을 잡아먹었던 것과 다른 점이 이것이고, 그래서 답변이 짧아지지
        않는다. 대신 **느려진다**(측정: 12초 → 21초).

        생성·채점 같은 배치 경로에서는 켜지 않는다. 항목마다 수 초씩 늘고, 거기서는 사람이
        그 글을 읽지 않는다.

        :param on_think: 생각 조각이 올 때마다 부르는 함수. 주면 **흘려보내며** 받는다 —
            수십 초를 기다리는 동안 화면에 아무것도 없으면 멈춘 것과 구분되지 않는다.
        """
        if _needs_no_think(self.model) and not think:
            prompt = _NO_THINK_PREFIX + prompt

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        options = {"num_ctx": self.num_ctx, "num_predict": self.num_predict}
        if think:
            # 생각이 본문의 몫을 먹지 않게 **얹어서** 준다. 합쳐서 세기 때문이다.
            options["num_predict"] = self.num_predict + self.think_num_predict
        if think and on_think is not None:
            content = self._stream(messages, options, on_think)
        else:
            response = self.client.chat(
                model=self.model,
                think=think or self.think,
                messages=messages,
                format="json" if json_format else None,
                options=options,
            )
            content = (response["message"]["content"] or "").strip()

        if not content and think:
            # 생각만 하다 예산이 끝났다. **추론을 끄고 한 번 더 부른다** — 사용자에게는
            # 답이 나오는 것이 생각을 보는 것보다 먼저다. 예산을 올려도 같은 입력에 같은
            # 길이가 안 나와서(위 모듈 주석의 측정) '가끔 답이 없는' 상태가 남는다.
            log_event(logger, "thinking overran the budget, retrying without it",
                      model=self.model, budget=self.num_predict + self.think_num_predict)
            return self.chat(prompt, system=system, json_format=json_format, think=False)

        if not content:
            raise EmptyLlmResponse(
                f"{self.model} 이 빈 응답을 돌려줬습니다. 추론 모델이면 OLLAMA_THINK=false 를 확인하세요."
            )
        return content

    def _stream(self, messages: list[dict], options: dict, on_think) -> str:
        """생각은 조각마다 넘기고 본문은 모아서 돌려준다.

        본문까지 흘려보내지 않는 이유: 답변 끝에 `사용: 1,3` 같은 **기계가 읽을 줄**이
        붙어 있어(`app/studio/ask.py`), 다 받은 뒤에 떼어내야 한다. 조각마다 내보내면
        그 줄이 사용자 화면에 잠깐 보였다 사라진다.
        """
        parts = []
        for chunk in self.client.chat(
            model=self.model, think=True, messages=messages, stream=True, options=options,
        ):
            message = chunk.get("message") or {}
            piece = message.get("thinking")
            if piece:
                on_think(piece)
            body = message.get("content")
            if body:
                parts.append(body)
        return "".join(parts).strip()
