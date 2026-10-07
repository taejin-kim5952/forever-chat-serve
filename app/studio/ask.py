"""챗봇 화면의 `AI 답변` 스위치 — **studio 전용**.

### 이것이 무엇이고, 무엇이 아닌가

평소 챗봇은 **미리 검수해 둔 QA만** 내보낸다. 이 모듈은 그 규칙의 예외가 아니라 **다른
길**이다. 스위치를 켜면 QA 인덱스를 보지 않고 문서에서 찾은 발췌만 근거로 답을 만든다.
그래서 결과에 `검수 완료` 표시가 붙지 않고, 화면은 `AI 정리 · 검수 전` 으로 그린다.

### 찾는 것은 임베딩, 고르는 것은 AI

    질문 ─임베딩─→ 후보 8건 ──→ AI ─→ 실제로 쓴 발췌만 인용 ─→ 답변 + 그 발췌들
                   (0.03초)        (질문과 관계없는 것은 뺀다)

둘은 잘하는 일이 다르다. **임베딩**은 10만 자에서 관련 있는 절을 0.03초에 찾아낸다.
**AI**는 그중 무엇이 실제로 답에 필요한지 판단한다. 2026-09-01 에 반대로도 해 봤다 —
문서 목차(제목 171개)를 통째로 주고 AI 에게 읽을 절을 고르게 했더니 3건 중 2건을 헛짚고
9.4초가 걸렸다. 제목만 보고 찍었기 때문이다. 임베딩은 본문을 이미 벡터로 읽어 둔다.

그래서 **후보는 넓게(8건) 주고 판단만 AI 에게 맡긴다.** 3건만 주면 4번째로 걸린 문서에
답이 있어도 AI 는 그것을 본 적이 없게 된다.

### 왜 생성 경로와 프롬프트를 나눴나

QA 생성(탭 ⑥)은 청크 **하나**에서 질문과 답을 만든다 — 무엇을 근거로 썼는지 물을 이유가
없다. 여기는 후보가 여럿이라 **어느 것을 썼는지**가 화면(참고 자료 카드)에 그대로 나가야
한다. 프롬프트가 다른 이유는 그것 하나이고, 지어내지 않게 하는 규칙(`qa_rules()`)과
근거 판정(`근거: 있음|없음`)은 **생성과 똑같은 것을 쓴다.**

### 왜 studio 에만 있나

운영 서버에는 GPU가 없다. 1차(`forever-chat`)에서 질문 1건에 1~3분이 걸렸고, 그것이 이
저장소가 갈라져 나온 이유다. 그래서 이 파일은 `app/studio/` 안에 있고 운영 경로
(`app/pipeline/retrieve.py`)는 이것을 import 하지 않는다.
"""

import re

from app.core.config import get_settings
from app.core.logging import get_logger, log_event
from app.studio.generate import _parse_grounded_answer, qa_rules
from app.studio.llm import StudioLlm

logger = get_logger("studio.ask")

# 발췌 하나에 줄 수 있는 최소 길이. 후보를 늘려도 이보다 짧게 자르지 않는다 —
# 200자만 남은 발췌는 문장이 끊겨 있어서 없느니만 못하다.
MIN_SOURCE_CHARS = 400
# 발췌 하나의 상한. 문서 한 절이 이보다 길면 앞부분만 쓴다.
MAX_SOURCE_CHARS = 1500

_USED_LINE = re.compile(r"^\s*사용\s*[:：]\s*(.*)$", re.M)

_ANSWER_PROMPT = """[사용자 질문]
{question}

[문서 발췌] 번호가 붙어 있습니다.
{context}

위 발췌만 근거로 이 질문에 답하세요. 질문과 관계없는 발췌는 쓰지 마세요.
{scope_note}
**'어느 문서에 있는지' 를 묻는 질문**(`~ 있는 문서`, `어디에 나와`, `어느 문서`, `어디 보면`)
에는 내용을 늘어놓지 말고 **문서 이름과 절 이름**으로 답하세요. 발췌 머리의 `[번호] 제목 > 절`
이 그 이름입니다.
  예) 「API 등록 · 배포 절차」의 '전체 흐름과 역할' 절에 있습니다.

[답변 쓰는 법] 화면이 마크다운을 그대로 그립니다. 읽기 좋게 꾸며 주세요.
- **첫 줄은 질문에 대한 한 문장 답**입니다. 제목으로 시작하지 마세요.
- 절차·순서는 번호 목록, 나열은 `-` 글머리 목록으로 씁니다.
- 항목마다 설명이 붙는 것(입력 항목·상태·역할)은 **표**로 씁니다.
- 화면명·버튼명·메뉴는 `**굵게**`, 경로·값·코드는 백틱으로 감쌉니다.
- 답이 길어 묶음이 나뉠 때만 `##` 소제목을 답니다. 서너 줄이면 제목 없이 그대로 씁니다.
- 굵게와 백틱을 **겹쳐 쓰지 마세요**. 둘 중 하나만 씁니다.
- **빈 칸을 만들지 마세요.** 표나 목록을 먼저 짜 놓고 `(내용 없음)` · `(없음)` · `-` 로
  채우면 안 됩니다. 발췌에 없는 항목은 **아예 쓰지 않습니다.** 꾸밀 거리가 모자라면
  표나 목록을 쓰지 말고 그냥 문장으로 쓰세요.
- 발췌에 없는 내용을 꾸밈으로 채우지 마세요. 꾸미는 것은 **있는 내용의 모양**일 뿐입니다.

[출력 형식] 아래 세 줄만 쓰세요. 다른 말을 붙이지 마세요.
근거: 있음
사용: 1,3
답변: (답변 본문. 여러 줄로 써도 됩니다)

`사용:` 에는 답에 실제로 근거로 쓴 발췌 번호만 적습니다.
발췌로 답할 수 없으면 `근거: 없음` 한 줄만 쓰세요."""


# 형식 칸을 **선택지로 적지 않는 이유** (2026-09-01, `qwen3.5:4b` 6회 중 1회 실패):
#
#     [출력 형식]
#     근거: 있음 | 없음        ← 이렇게 적었더니
#
#     근거: 있음 | 없음        ← 모델이 이 줄을 그대로 따라 썼다
#
# 그러면 판정이 '없음'을 읽고 멀쩡한 답을 버린다. 예시는 **고른 뒤의 모습 하나**만 보여주고,
# 거절하는 길은 문장으로 따로 알려 준다. 형식 설명을 칸 안에 길게 쓰는 것도 같은 이유로
# 피한다 — 모델이 설명문까지 답으로 옮겨 적는다.


# 백틱과 굵게를 겹쳐 쓴 것. `**저장**` 처럼 오면 화면이 코드로 그려 별표가 그대로 보인다.
_CODE_BOLD = re.compile(r"`[*]{2}(.+?)[*]{2}`|[*]{2}`(.+?)`[*]{2}")
# "채울 것이 없다"는 뜻으로 모델이 적어 넣는 말들.
_PLACEHOLDER = re.compile(
    r"^[(\[]?\s*(?:상세\s*)?(?:내용\s*)?(?:없음|해당\s*없음|미상|불명|N/?A|TBD|확인\s*필요)\s*[)\]]?$",
    re.IGNORECASE,
)


def _is_blank(cell: str) -> bool:
    cell = cell.strip().strip("*`").strip()
    return not cell or cell in {"-", "--", "—", "?", "·"} or bool(_PLACEHOLDER.match(cell))


def tidy_markdown(answer: str) -> str:
    """꾸미기가 **내용 없는 틀**을 만드는 것을 걷어낸다.

    마크다운으로 쓰라고 하면 모델이 표나 목록을 **먼저 짜 놓고** 채우지 못한 칸에
    `(내용 없음)` 을 적는다(2026-10-07 `gemma4:latest` 에서 반복 확인). 프롬프트로
    금지해도 지키지 않아서, 글자 수준에서 지운다.

    - 데이터 칸이 전부 비어 있는 표 줄은 지운다. 남는 줄이 없으면 표 자체를 지운다
    - `- **항목**: (내용 없음)` 같은 목록 줄도 지운다
    - 백틱과 굵게를 겹쳐 쓴 것은 굵게로 편다

    **내용을 고치지 않는다.** 모양만 손본다 — 모델이 쓴 말을 다시 쓰기 시작하면 그 순간
    "발췌만 근거로" 라는 규칙이 흐려진다.
    """
    text = _CODE_BOLD.sub(lambda m: "**" + (m.group(1) or m.group(2)) + "**", answer or "")

    lines = text.split("\n")
    kept: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and not re.match(r"^[|\s:-]+$", stripped):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) > 1 and all(_is_blank(c) for c in cells[1:]):
                continue
        elif re.match(r"^\s*[-*]\s", line) and ":" in line:
            if _is_blank(line.split(":", 1)[1]):
                continue
        kept.append(line)

    # 머리줄과 구분줄만 남은 표는 통째로 지운다.
    out: list[str] = []
    i = 0
    while i < len(kept):
        if kept[i].strip().startswith("|"):
            j = i
            while j < len(kept) and kept[j].strip().startswith("|"):
                j += 1
            block = kept[i:j]
            data = [b for b in block if not re.match(r"^[|\s:-]+$", b.strip())]
            if len(data) > 1:
                out.extend(block)
            i = j
            continue
        out.append(kept[i])
        i += 1

    # 표를 지우면서 생긴 빈 줄 세 개 이상은 둘로 줄인다.
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def build_context(hits: list[dict], budget: int = 0) -> str:
    """검색 결과를 프롬프트에 넣을 발췌 묶음으로 만든다.

    제목과 절 이름을 함께 넣는다. 본문만 넣으면 모델이 서로 다른 문서의 문장을 한 문단으로
    엮어 놓는데, 그러면 사람이 어느 문서에서 온 말인지 확인할 수 없다. 번호를 붙이는 것은
    **모델이 무엇을 썼는지 되돌려 말하게** 하기 위한 것이다(`사용:` 줄).

    `budget` 은 발췌 전체에 쓸 수 있는 글자 수다. **후보 수로 나눠 고르게 준다** — 통째로
    넘겨 `llm.fit()` 이 뒤를 자르게 두면 뒤쪽 후보가 **통째로 사라진다.** 그러면 AI 는
    보지도 못한 것을 안 골랐을 뿐인데 화면에서는 "판단해서 뺐다"로 보인다.

    **`excerpt` 가 아니라 `text`(청크 전문)를 넣는다.** `excerpt` 는 화면 카드에 두 줄로
    보여주려고 200자쯤에서 자른 것이다. 그것을 모델에 주면 문장이 중간에 끊긴 채로 답을
    만들게 된다 — 근거가 있는데도 `근거: 없음` 이 나오는 흔한 원인이다(2026-09-01 확인).
    """
    if not hits:
        return ""
    per_source = MAX_SOURCE_CHARS
    if budget:
        per_source = max(MIN_SOURCE_CHARS, min(MAX_SOURCE_CHARS, budget // len(hits)))

    blocks = []
    for order, hit in enumerate(hits, start=1):
        title = hit.get("title") or hit.get("doc_id") or ""
        section = hit.get("section") or ""
        head = f"[{order}] {title}" + (f" > {section}" if section else "")
        body = hit.get("text") or hit.get("excerpt") or ""
        blocks.append(f"{head}\n{body[:per_source]}")
    return "\n\n".join(blocks)


def parse_used(raw: str, count: int) -> tuple[str, list[int]]:
    """`(사용 줄을 걷어낸 응답, 0부터 시작하는 발췌 번호)`.

    번호를 먼저 떼어내는 이유: `답변:` 라벨을 빼먹는 모델이 있어서(2026-09-01 `qwen3.5:4b`)
    라벨 없는 본문을 답변으로 받아 주는데, 그때 `사용: 1,3` 줄이 답변 첫 줄로 섞여 들어간다.
    """
    used: list[int] = []
    for match in _USED_LINE.finditer(raw):
        for number in re.findall(r"\d+", match.group(1)):
            index = int(number) - 1
            if 0 <= index < count and index not in used:
                used.append(index)
    return _USED_LINE.sub("", raw), used


# 전체(여러 자료를 가로질러) 검색일 때만 덧붙이는 한 줄.
#
# 그때 사용자는 **어느 자료의 이야기인지 모른 채** 답을 받는다. 프로젝트 안에서 물었을
# 때는 이미 알고 있으므로 같은 말을 또 하면 군더더기다. 프롬프트를 둘로 나누는 대신
# 이 한 줄만 끼운다.
_ACROSS_NOTE = """
이 질문은 **여러 자료를 가로질러** 찾은 것입니다. 사용자는 어느 자료에서 나온 답인지
모릅니다. 첫 문장이나 끝에 **어느 문서의 이야기인지** 한 번 밝혀 주세요.
"""


def compose(question: str, hits: list[dict], model: str | None = None,
            on_think=None, across: bool = False) -> tuple[str | None, str, list[dict]]:
    """`(답변, 쓴 모델, AI 가 실제로 근거로 쓴 발췌)`. 근거가 없으면 답변은 `None` 이다.

    돌려주는 발췌가 곧 화면의 참고 자료 카드다. **AI 가 안 쓴 문서는 카드로도 내보내지
    않는다** — 답에 반영되지 않은 문서가 '참고 자료'로 붙어 있으면 사람이 그것까지 근거로
    읽는다.

    번호를 못 읽었으면(형식 이탈) 유사도 상위 몇 건으로 떨어진다. 후보 8건을 전부 카드로
    내보내면 무관한 카드가 여덟 장 뜨는데, 그것이 지금보다 나쁘기 때문이다.

    LLM이 없거나(Ollama 미실행) 응답이 깨져도 **예외를 밖으로 내지 않는다** — 화면은
    "답을 못 만들었다"로 떨어져 참고 자료라도 보여주면 되고, 그것이 오류 화면보다 낫다.
    """
    if not hits:
        return None, "", []

    settings = get_settings()
    # 역할별 모델을 쓰는 설치에서는 **답변 모델**이 이 자리에 맞는다(변형 질문용 작은
    # 모델이 아니라). 생성 경로가 답을 만들 때 쓰는 것과 같은 모델이어야, 여기서 잘 나온
    # 답이 생성에서도 잘 나온다.
    llm = StudioLlm(model=model or settings.ollama_answer_model or None)
    context = build_context(hits, budget=llm.source_budget_chars())

    try:
        prompt = _ANSWER_PROMPT.format(question=question, context=context,
                                       scope_note=_ACROSS_NOTE if across else "")
        raw = llm.chat(prompt, system=qa_rules(), think=on_think is not None, on_think=on_think)
    except Exception as exc:                      # noqa: BLE001 - 원인이 무엇이든 화면은 계속 돈다
        log_event(logger, "ai answer failed", model=llm.model, error=str(exc))
        return None, llm.model, []

    rest, used = parse_used(raw, len(hits))
    answer = _parse_grounded_answer(rest)
    if not answer:
        return None, llm.model, []
    # 꾸미기가 만들어 낸 빈 틀을 걷어낸다(tidy_markdown 참고). 다듬고 나서 남는 것이
    # 없으면 답이 없었던 것이다.
    answer = tidy_markdown(answer)
    if not answer:
        return None, llm.model, []

    sources = [hits[i] for i in used] or hits[: settings.related_docs_count]
    log_event(
        logger, "ai answer composed",
        model=llm.model, candidates=len(hits), used=len(sources),
        cited=bool(used), chars=len(answer),
    )
    return answer, llm.model, sources
