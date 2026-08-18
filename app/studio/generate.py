"""문서·질문에서 QA 초안을 만든다 — 이 프로젝트의 전제를 지탱하는 단계.

운영에서 답변을 만들지 않기로 했으므로, **답변은 여기서 미리 만들어져 있어야 한다.**
여기서 나온 것은 전부 `pending` 초안이고, 사람이 검수해 `approved` 로 바꿔야 사용자에게 나간다.

### 두 가지 생성 경로

```
문서 청크 ─→ [질문 모델] ─→ 질문 ─┬→ [답변 모델] ─→ 근거 있음? ─→ 답변
                                  │                  └─ 없음 ─→ 버린다
                                  └→ [질문 모델] ─→ 변형 질문 8~15개
질문 목록 ─→ 문서 검색 ─→ 발췌 ──→ [답변 모델] ─→ (같음)
```

### 질문과 답변을 한 번에 만들지 않는 이유 ★

전에는 청크 하나에 `Q:`/`A:` 를 한꺼번에 뽑게 했다. 호출이 절반이라 빠르지만 두 가지를 잃었다.

- **역할별로 좋은 모델이 다르다.** 2026-08-15 실측에서 큰 모델(12b)은 답변이 정확했지만
  변형 질문은 원문 어순만 바꿔 표현 폭이 좁았고, 작은 모델은 반대였다. 한 호출로 묶으면
  둘 다 같은 모델이 맡을 수밖에 없다.
- **근거 판정이 없었다.** `근거: 있음|없음` 선언은 질문 경로에만 있었다. 문서 경로는 청크를
  주고 만들게 하니 당연히 근거가 있다고 본 것인데, 모델이 청크 옆 문장이나 사전 지식으로
  답을 채우는 경우를 걸러내지 못했다. 지금은 두 경로가 같은 판정을 통과한다.

대신 호출이 청크당 `1 + 질문 수 × 2` 로 늘어난다. 스튜디오에서 도는 배치라 호출 수보다
결과 품질이 중요하다는 판단은 변형 질문을 따로 부르는 결정(아래)과 같다.

문서에서 시작하는 쪽이 기본이다. 질문에서 시작하는 쪽은 "사용자가 실제로 물었는데 답이
없었던 질문"(질문 분석 탭)을 QA로 만드는 용도라 **근거가 없을 수 있다.** 그때 답을 지어내면
검수자가 사실 여부를 문서와 대조하지 못한 채 승인하게 되고, 이 서비스의 유일한 품질 보증인
'검수'가 무력해진다. 그래서 모델이 `근거: 없음` 을 선언하면 그 질문은 버린다.
1차 프로젝트에서 유사도 숫자만으로 판단했다가 "점심 메뉴 추천"에 억지 답변이 나간 적이 있다.

### 변형 질문을 따로 한 번 더 부르는 이유

적중률은 사실상 변형 질문 목록이 결정한다(측정: "API 등록은 어떻게 하나요?" 1.000 vs
변형에서 걸린 "등록하는 방법 알려줘" 0.974). 질문·답변과 한 번에 만들게 하면 모델이 형식을
지키느라 변형을 2~3개로 줄인다. 호출을 나누면 항목당 10개 이상이 안정적으로 나온다.
어차피 스튜디오에서 도는 배치라 호출 수보다 결과 품질이 중요하다.
"""

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from app.core.categories import CategoryStore, load_categories
from app.core.config import get_settings
from app.core.logging import get_logger, log_event
from app.core.profile import Profile, load_profile
from app.ingestion.chunker import chunk_markdown_file
from app.ingestion.doc_index import DocIndex
from app.qa import store as qa_store
from app.studio.judge import judge_answer
from app.studio.korean import is_expected_language
from app.studio.llm import StudioLlm

logger = get_logger("studio.generate")

# 진행률 콜백: (완료 단계, 전체 단계, 화면에 띄울 문구)
ProgressFn = Callable[[int, int, str], None]
# 중지 요청 여부. 수십 분 걸리는 작업이라 사이사이에서 물어본다.
StopFn = Callable[[], bool]


@dataclass
class ModelRoles:
    """역할별 모델 한 벌.

    `question` 이 질문과 **변형 질문**을 함께 맡는다. 둘 다 "같은 뜻을 여러 표현으로 쓰는" 일이라
    같은 성질의 모델이 유리하고, 답변은 "근거대로 빠짐없이 서술하는" 다른 성질이 필요하다.
    """

    question: StudioLlm
    answer: StudioLlm
    # 채점은 **따로 지정했을 때만** 한다. 같은 모델이 자기 답을 채점하면 점수가 후해지므로
    # (app/studio/judge.py) 비어 있으면 채점을 건너뛴다.
    judge: StudioLlm | None = None

    @classmethod
    def resolve(
        cls,
        question_model: str | None = None,
        answer_model: str | None = None,
        judge_model: str | None = None,
    ) -> "ModelRoles":
        """화면이 고른 값 → `.env` 의 역할별 값 → `OLLAMA_LLM_MODEL` 순서로 정한다."""
        settings = get_settings()
        judge_name = judge_model or settings.ollama_judge_model
        answer = StudioLlm(model=answer_model or settings.ollama_answer_model or None)
        if judge_name and judge_name == answer.model:
            # 막지는 않는다. 계열이 다른 모델을 아직 못 받은 상태에서도 한 번 돌려보고 싶을 수 있다.
            log_event(logger, "judge model equals answer model — self-grading bias", model=judge_name)
        return cls(
            question=StudioLlm(model=question_model or settings.ollama_question_model or None),
            answer=answer,
            judge=StudioLlm(model=judge_name) if judge_name else None,
        )

    @classmethod
    def single(cls, llm: StudioLlm, judge: StudioLlm | None = None) -> "ModelRoles":
        """한 모델이 전부 맡는다. 스크립트와 테스트가 쓴다."""
        return cls(question=llm, answer=llm, judge=judge)

    def label(self) -> str:
        parts = [self.question.model] if self.question.model == self.answer.model else [
            f"질문 {self.question.model}", f"답변 {self.answer.model}",
        ]
        if self.judge:
            parts.append(f"채점 {self.judge.model}")
        return " · ".join(parts)


class GenerationStats(BaseModel):
    """단계 사이에서 **걸러져 나간 것**. 진행 현황의 '흐름 요약'이 이 값을 보여준다.

    지금까지는 로그에만 남겼는데, 로그는 아무도 안 본다. `근거 없음` 이 많다는 것은
    "모델이 부실하다"가 아니라 **"그 주제를 다룬 문서가 없다"** 는 뜻이고, 그때 필요한 것은
    QA가 아니라 문서다. 파이프라인에서 가장 값진 신호라 화면까지 올린다.
    """

    source: str = ""            # docs | questions
    chunks: int = 0             # 문서에서 만든 청크 수 (질문 경로에서는 0)
    questions_made: int = 0     # 모델이 만든 질문 수 (필터 전)
    dropped_language: int = 0   # 기대 언어가 아니라서 버림
    dropped_ungrounded: int = 0 # 근거가 없어서 버림 ← 문서를 써야 한다는 신호
    failed_calls: int = 0
    drafts: int = 0
    # 아래 셋은 '반영'(apply) 단계에서 채워진다. 생성 시점에는 0이다.
    applied: int = 0
    skipped: int = 0
    low_score: int = 0


class QaDraft(BaseModel):
    """검수 전 초안. 아직 `qa_index.json` 에 들어가지 않은 상태다."""

    draft_id: str = Field(default_factory=lambda: f"dr_{uuid.uuid4().hex[:10]}")
    question: str
    answer: str
    variants: list[str] = Field(default_factory=list)
    category_id: Optional[str] = None
    source_doc_ids: list[str] = Field(default_factory=list)
    # 어느 절에서 나왔는지. 검수자가 원문을 찾아가는 시간을 줄인다.
    source_section: str = ""
    model_used: str = ""
    # 판정 모델의 채점(1~5). 0 = 판정하지 않았거나 판정을 읽지 못함 — 점수가 아니라 '모름'이다.
    score: int = 0
    judge_reason: str = ""
    judge_model: str = ""
    # 초안을 QA 인덱스에 넣었으면 그 qa_id. 같은 초안을 두 번 넣는 것을 막는다.
    applied_qa_id: Optional[str] = None


class GenerationOutcome(BaseModel):
    """초안 + 통계. 통계를 로그로만 흘리면 화면이 쓸 수 없어서 함께 돌려준다."""

    drafts: list[QaDraft] = Field(default_factory=list)
    stats: GenerationStats = Field(default_factory=GenerationStats)


# ─────────────────────────────────────────────────────────────────── 프롬프트

# 조직 이름과 도메인 설명을 프롬프트에 박아 두면 설치할 때마다 소스를 고쳐야 한다.
# 달라지는 두 자리(도메인 소개 · 언어 규칙)만 `data/profile.json` 에서 채운다 —
# 기본 프로필에서는 이전과 **글자 하나까지 같은** 프롬프트가 나온다.
_QA_RULES_TEMPLATE = """당신은 {domain_intro}를 담당하는 사내 도우미입니다.
사용자가 실제로 물을 법한 질문과, 그 질문에 대한 답변을 만듭니다.

[규칙]
1. **발췌에 적혀 있는 내용으로만** 답한다. 발췌에 없는 기능·수치·정책을 지어내지 않는다.
2. 발췌로 답할 수 없는 질문은 아예 만들지 않는다. 개수를 채우려고 억지로 만들지 않는다.
3. 질문은 문서 문장을 그대로 옮기지 말고, 사용자가 검색창에 칠 법한 표현으로 쓴다.
4. 답변은 3~6문장 또는 번호 목록으로 쓴다. 화면명·경로·필드명·코드는 문서 표기를 그대로 유지한다.
5. 말투는 '~합니다' 체로 통일한다.
6. {language_rule}
   문서에 그대로 적힌 고유명사·화면명·필드명·경로·코드(예: OAS 3.0, Swagger, Path)만 예외다.
7. 확실하지 않은 부분은 지어내지 말고 `(확인 필요)` 로 표시해 검수자가 채우게 한다.
8. `[[문서ID]]` 는 문서끼리 참조하는 내부 표기다. 답변에 옮겨 쓰지 않는다.
9. "이 문서는 ~를 설명합니다" 처럼 **문서 자체를 설명하는 답변을 쓰지 않는다.** 사용자는 문서가
   아니라 업무 절차를 묻는다."""


def qa_rules(profile: Profile | None = None) -> str:
    """생성·답변에 공통으로 붙는 system 프롬프트.

    배치 시작 시점에 한 번 만들어 아래로 넘긴다. 항목마다 만들면 프로필 파일을 수백 번
    다시 읽게 되고, 배치 도중 파일이 바뀌면 앞뒤 항목이 서로 다른 규칙으로 만들어진다.
    """
    resolved = profile or load_profile()
    return _QA_RULES_TEMPLATE.format(
        domain_intro=resolved.domain_intro, language_rule=resolved.language_rule(),
    )

_QUESTION_PROMPT = """[문서 발췌]
{context}

위 발췌로 답할 수 있는 질문을 최대 {count}개 만드세요. 답변은 쓰지 마세요.

[추가 규칙]
1. 발췌에 답이 있는 질문만 만듭니다. 개수를 채우려고 억지로 만들지 않습니다.
2. 문서를 보지 않은 사람이 던질 질문이어야 합니다. "위 발췌에 따르면" 같은 표현을 쓰지 않습니다.
3. 서로 다른 것을 묻는 질문으로 만드세요. 같은 내용을 표현만 바꾼 것은 한 번만 씁니다.

[출력 형식] 질문만 한 줄에 하나씩 쓰세요. 번호·기호·설명을 붙이지 마세요."""

_ANSWER_PROMPT = """[사용자 질문]
{question}

[문서 발췌]
{context}

위 발췌만 근거로 이 질문에 답하세요.

[출력 형식] 아래 두 줄 형식을 정확히 지키세요.
근거: 있음 | 없음
답변: (근거가 있을 때만 답변 본문. 없으면 이 줄을 비웁니다)"""

_VARIANT_PROMPT = """아래 질문과 **뜻이 같은** 다른 표현을 {count}개 만드세요.

[질문]
{question}

[규칙]
1. 뜻이 달라지면 안 됩니다. 범위를 넓히거나 좁히지 마세요.
2. 표현을 다양하게 섞으세요 — 정중한 문장, 짧은 구어체, 명사만 나열한 것, 줄임말.
   (예: "권한그룹은 무엇을 선택해야 하나요?", "권한그룹 뭐 골라요?", "권한그룹 선택 기준")
3. **한국어로만** 쓰세요. 화면명·필드명·코드는 원문 표기를 유지합니다.
4. 한 줄에 하나씩, 번호나 기호 없이 질문만 쓰세요."""


# ─────────────────────────────────────────────────────────────────── 파싱

_GROUND_LINE = re.compile(r"^\s*근거\s*[:：]\s*(.+)$")
_ANSWER_LINE = re.compile(r"^\s*답변\s*[:：]\s*(.*)$")
_LIST_MARKER = re.compile(r"^(?:[-*•]|\d+[.)]|Q\s*[:.)])\s*")


def _parse_grounded_answer(raw: str) -> str | None:
    """`근거: 있음/없음` + `답변:` 을 읽는다. 근거가 없다고 하면 None(= 만들지 않는다).

    근거 여부를 **모델이 스스로 선언**하게 하는 것이 핵심이다. 검색 유사도만 보고 답을 만들게
    하면 문서에 없는 내용이 그럴듯한 문장으로 채워진다.
    """
    grounded: bool | None = None
    answer_lines: list[str] = []
    collecting = False

    for line in raw.splitlines():
        ground = _GROUND_LINE.match(line)
        if ground:
            grounded = "있음" in ground.group(1)
            continue
        answer = _ANSWER_LINE.match(line)
        if answer:
            collecting = True
            answer_lines = [answer.group(1)]
            continue
        if collecting:
            answer_lines.append(line)

    body = "\n".join(answer_lines).strip()
    # 형식을 무시하고 본문만 뱉는 모델이 있다. 근거 줄이 아예 없으면 본문 유무로 판단한다.
    if grounded is None:
        grounded = bool(body)
    if not grounded or not body:
        return None
    return body


def _parse_line_items(raw: str) -> list[str]:
    """'한 줄에 하나' 형식의 응답을 읽는다. 질문 목록과 변형 질문이 같은 형식을 쓴다."""
    items: list[str] = []
    for line in raw.splitlines():
        text = _LIST_MARKER.sub("", line.strip()).strip()
        # 대괄호 머리말('[규칙]')이나 너무 짧은 줄은 형식 안내를 따라 쓴 것이다.
        if len(text) >= 4 and not text.startswith("["):
            items.append(text)
    return items


# ─────────────────────────────────────────────────────────────────── 보조


_WIKI_LINK = re.compile(r"\[\[[^\]]+\]\]")
# `([[api-등록]] 참고)` 처럼 링크를 지우면 껍데기만 남는 괄호. 같이 걷어낸다.
_EMPTY_PAREN = re.compile(r"\(\s*(?:참고|참조)?\s*\)")


def clean_answer(text: str) -> str:
    """답변에서 문서 내부 표기를 걷어낸다.

    `raw_docs/*.md` 는 문서끼리 `[[문서ID]]` 로 참조한다. 사람이 읽는 원본에서는 유용하지만
    챗봇 말풍선에는 `[[api-등록]]` 이 그대로 찍힌다(화면은 마크다운 일부만 렌더한다).
    프롬프트로도 막지만 모델이 규칙 하나를 흘리는 일은 흔하므로 코드에서 한 번 더 지운다.
    """
    cleaned = _WIKI_LINK.sub("", text)
    cleaned = _EMPTY_PAREN.sub("", cleaned)
    # 지우고 남은 이중 공백과 구두점 앞 공백. 줄바꿈은 답변 서식이므로 건드리지 않는다.
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"[ \t]+([,.)])", r"\1", cleaned)
    return cleaned.strip()


# 중복 판정 규칙은 저장소(app/qa/store.py)에 있다. 운영의 'QA 가져오기'와 **같은 규칙**을
# 써야 해서 studio 밖으로 옮겼다. 여기서 다시 내보내는 것은 기존 호출부를 그대로 두기 위함이다.
normalize_question = qa_store.normalize_question


def _category_id_for(store: CategoryStore, doc_category: str) -> str | None:
    """문서 frontmatter 의 `category`("API 관리 > API 등록")를 카테고리 id 로 맞춘다.

    표기가 정확히 겹치는 경우에만 붙인다. 억지로 비슷한 것을 고르면 검수자가 틀린 주제를
    믿고 넘어가므로, 애매하면 **비워 두고 검수 화면에서 고르게** 한다.
    """
    if not doc_category:
        return None
    leaf = doc_category.split(">")[-1].strip()
    for group in store.groups:
        for category in group.categories:
            if category.name.strip() == leaf:
                return category.category_id
    return None


def _fail_if_every_call_failed(attempted: int, failures: list[str]) -> None:
    """호출이 **전부** 실패했으면 배치를 실패로 올린다.

    하나씩 실패하는 것은 흔한 일(형식 이탈·타임아웃)이라 건너뛰고 계속한다. 그러나 전부 실패했다면
    모델이 없거나 설정이 틀린 것이다. 그때 "완료, 0건"으로 끝내면 검수자는 문서 탓을 하며
    프롬프트를 고치기 시작한다 — 1차 프로젝트에서 빈 응답 문제를 찾는 데 가장 오래 걸린 이유다.
    """
    if attempted and len(failures) == attempted:
        raise RuntimeError(f"LLM 호출이 모두 실패했습니다({attempted}건). 마지막 오류: {failures[-1]}")


def _judged(roles: ModelRoles, draft: QaDraft, context: str) -> QaDraft:
    """초안에 채점 결과를 붙인다. 판정 모델이 없으면 그대로 돌려준다."""
    if roles.judge is None:
        return draft
    score, reason = judge_answer(roles.judge, draft.question, draft.answer, context)
    draft.score, draft.judge_reason, draft.judge_model = score, reason, roles.judge.model
    return draft


def grounded_answer(
    llm: StudioLlm, question: str, context: str, rules: str | None = None,
) -> str | None:
    """발췌만 근거로 답을 만든다. 모델이 `근거: 없음` 을 선언하면 None.

    두 생성 경로가 이 한 곳을 함께 쓴다 — 문서에서 만든 질문이든 사용자가 실제로 물은
    질문이든, 답을 만드는 규칙이 달라야 할 이유가 없다.
    """
    raw = llm.chat(
        _ANSWER_PROMPT.format(question=question, context=context), system=rules or qa_rules(),
    )
    return _parse_grounded_answer(raw)


def make_variants(llm: StudioLlm, question: str, count: int, language: str = "ko") -> list[str]:
    """변형 질문 생성. 실패해도 항목 자체는 살린다 — 대표 질문만으로도 검수는 가능하다."""
    if count <= 0:
        return []
    try:
        raw = llm.chat(_VARIANT_PROMPT.format(question=question, count=count))
    except Exception as exc:  # noqa: BLE001 — 변형 실패로 배치 전체를 멈추지 않는다
        log_event(logger, "variant generation failed", question=question[:40], error=str(exc))
        return []

    accepted: list[str] = []
    seen = {normalize_question(question)}
    for variant in _parse_line_items(raw):
        if len(accepted) >= count:
            break
        key = normalize_question(variant)
        # 대표 질문과 같은 문구는 벡터를 낭비하고 중복 적중을 만든다(admin_qa 저장 규칙과 같다).
        if key in seen or not is_expected_language(variant, language):
            continue
        seen.add(key)
        accepted.append(variant)
    return accepted


# ─────────────────────────────────────────────────────────── 문서에서 생성


def _load_chunks(doc_ids: list[str]) -> list[dict]:
    """원본 마크다운에서 직접 청크를 만든다.

    벡터 저장소에서 꺼내지 않는 이유: 벡터는 파생물이라 색인 전이면 비어 있다. 문서를 막 넣고
    바로 생성하는 흐름이 스튜디오에서는 가장 흔하므로, 색인 여부와 무관하게 동작해야 한다.
    """
    raw_dir = Path(get_settings().raw_docs_dir)
    paths = sorted(raw_dir.glob("*.md"))
    if doc_ids:
        wanted = set(doc_ids)
        paths = [p for p in paths if p.stem in wanted]

    chunks: list[dict] = []
    for path in paths:
        _, parsed = chunk_markdown_file(path)
        for chunk in parsed:
            # 표제만 있는 짧은 절에서는 만들 답이 없다. 호출만 버린다.
            if len(chunk.text.strip()) < 120:
                continue
            if _is_document_lead(chunk, len(parsed)):
                continue
            chunks.append({"text": chunk.text, "meta": chunk.metadata})
    return chunks


def _is_document_lead(chunk, chunk_count: int) -> bool:
    """첫 헤딩 앞의 도입부인가.

    도입부는 "이 문서는 ~를 설명합니다"라서, 여기서 QA를 만들게 하면 업무가 아니라 **문서 자체를
    설명하는 답변**이 나온다. 실제로 `gemma4` 첫 시험 생성에서 그런 항목이 1번으로 나왔다.
    검색(`related_docs`)에는 도입부도 쓸모가 있으므로 청킹 단계가 아니라 여기서만 뺀다.

    헤딩이 하나도 없는 문서는 전부 도입부처럼 보이므로 그때는 빼지 않는다 — 그 문서에서
    아무것도 못 만들게 된다.
    """
    meta = chunk.metadata
    return (
        chunk_count > 1
        and meta.get("chunk_index") == 0
        and meta.get("section_title") == meta.get("title")
    )


def generate_from_docs(
    doc_ids: list[str],
    *,
    roles: ModelRoles,
    items_per_chunk: int = 2,
    variant_count: int = 10,
    max_items: int = 50,
    existing_questions: set[str] | None = None,
    progress: ProgressFn | None = None,
    should_stop: StopFn | None = None,
) -> GenerationOutcome:
    chunks = _load_chunks(doc_ids)
    if not chunks:
        log_event(logger, "generation skipped: no chunks", doc_ids=doc_ids)
        return GenerationOutcome(stats=GenerationStats(source="docs"))

    categories = load_categories()
    # 프로필은 배치 시작에 한 번만 읽는다(qa_rules 독스트링 참고).
    profile = load_profile()
    rules, language = qa_rules(profile), profile.language
    seen = set(existing_questions or set())
    drafts: list[QaDraft] = []
    dropped_lang = 0
    ungrounded = 0
    attempted = 0
    questions_made = 0
    failures: list[str] = []

    for index, chunk in enumerate(chunks):
        if should_stop and should_stop():
            break
        if len(drafts) >= max_items:
            break
        meta = chunk["meta"]
        if progress:
            # 청크를 다 도는 것과 max_items 를 채우는 것 중 **먼저 끝나는 쪽**이 진행률이다.
            # 청크 기준으로만 재면 max_items 가 먼저 차는 흔한 경우에 0%에서 갑자기 끝나 보인다.
            step = max(index, int(len(drafts) / max_items * len(chunks)))
            progress(step, len(chunks), f"문서에서 QA 생성 중… ({len(drafts)}건) {meta.get('title', '')}")

        # 발췌 예산은 답변 모델 기준으로 자른다. 두 모델의 컨텍스트 창이 다를 때 넉넉한 쪽에
        # 맞추면, 답변 단계에서 근거 뒷부분이 조용히 잘린 채로 답이 만들어진다.
        context = roles.answer.fit(
            f"[{meta.get('title')} - {meta.get('section_title')}]\n{chunk['text']}",
            label=str(meta.get("doc_id", "")),
        )
        attempted += 1
        try:
            raw = roles.question.chat(
                _QUESTION_PROMPT.format(context=context, count=items_per_chunk), system=rules
            )
        except Exception as exc:  # noqa: BLE001 — 청크 하나가 실패해도 나머지는 계속한다
            log_event(logger, "chunk question generation failed", doc_id=meta.get("doc_id"), error=str(exc))
            failures.append(str(exc))
            continue

        made = _parse_line_items(raw)[:items_per_chunk]
        questions_made += len(made)
        for question in made:
            if len(drafts) >= max_items:
                break
            if not is_expected_language(question, language):
                dropped_lang += 1
                continue
            key = normalize_question(question)
            if key in seen:
                continue

            attempted += 1
            try:
                answer = grounded_answer(roles.answer, question, context, rules=rules)
            except Exception as exc:  # noqa: BLE001 — 답변 하나가 실패해도 나머지는 계속한다
                log_event(logger, "answer generation failed", question=question[:40], error=str(exc))
                failures.append(str(exc))
                continue
            # 질문을 만든 그 청크로도 답을 못 하겠다면, 질문 모델이 발췌 밖의 것을 물은 것이다.
            if answer is None or not is_expected_language(answer, language):
                ungrounded += 1
                continue

            seen.add(key)
            drafts.append(_judged(roles, QaDraft(
                question=question,
                answer=clean_answer(answer),
                variants=make_variants(roles.question, question, variant_count, language=language),
                category_id=_category_id_for(categories, str(meta.get("category", ""))),
                source_doc_ids=[str(meta.get("doc_id", ""))],
                source_section=str(meta.get("section_title", "")),
                model_used=roles.answer.model,
            ), context))

    log_event(
        logger, "qa drafts generated from docs",
        model=roles.label(), chunks=len(chunks), drafts=len(drafts), language=language,
        dropped_language=dropped_lang, dropped_ungrounded=ungrounded, failed_calls=len(failures),
    )
    _fail_if_every_call_failed(attempted, failures)
    return GenerationOutcome(drafts=drafts, stats=GenerationStats(
        source="docs", chunks=len(chunks), questions_made=questions_made,
        dropped_language=dropped_lang, dropped_ungrounded=ungrounded,
        failed_calls=len(failures), drafts=len(drafts),
    ))


# ─────────────────────────────────────────────────────────── 질문에서 생성


def generate_from_questions(
    questions: list[str],
    *,
    roles: ModelRoles,
    doc_index: DocIndex | None = None,
    category_id: str | None = None,
    variant_count: int = 10,
    top_k: int = 3,
    max_items: int = 50,
    existing_questions: set[str] | None = None,
    progress: ProgressFn | None = None,
    should_stop: StopFn | None = None,
) -> GenerationOutcome:
    """질문 목록에 답을 붙인다. 근거를 못 찾은 질문은 **답을 만들지 않고 버린다.**

    버려진 질문은 "문서가 없다"는 신호다. 그때 필요한 것은 QA가 아니라 문서이며,
    지어낸 답변으로 그 신호를 덮으면 문서 공백이 영영 드러나지 않는다.
    """
    index = doc_index or DocIndex()
    profile = load_profile()
    rules, language = qa_rules(profile), profile.language
    seen = set(existing_questions or set())
    drafts: list[QaDraft] = []
    ungrounded = 0
    attempted = 0
    failures: list[str] = []

    for position, question in enumerate(questions):
        if should_stop and should_stop():
            break
        if len(drafts) >= max_items:
            break
        question = question.strip()
        if not question:
            continue
        key = normalize_question(question)
        if key in seen:
            continue
        if progress:
            progress(position, len(questions), f"질문에 답변 생성 중… ({len(drafts)}건)")

        hits = index.search(question, top_k)
        if not hits:
            ungrounded += 1
            continue

        context = roles.answer.fit(
            "\n\n---\n\n".join(f"[{h['title']} - {h['section']}]\n{h['text']}" for h in hits),
            label=question[:40],
        )
        attempted += 1
        try:
            answer = grounded_answer(roles.answer, question, context, rules=rules)
        except Exception as exc:  # noqa: BLE001
            log_event(logger, "answer generation failed", question=question[:40], error=str(exc))
            failures.append(str(exc))
            continue

        if not answer or not is_expected_language(answer, language):
            ungrounded += 1
            continue

        seen.add(key)
        drafts.append(_judged(roles, QaDraft(
            question=question,
            answer=clean_answer(answer),
            variants=make_variants(roles.question, question, variant_count, language=language),
            category_id=category_id,
            source_doc_ids=list({h["doc_id"] for h in hits if h["doc_id"]}),
            source_section=hits[0].get("section", ""),
            model_used=roles.answer.model,
        ), context))

    log_event(
        logger, "qa drafts generated from questions",
        model=roles.label(), asked=len(questions), drafts=len(drafts), language=language,
        ungrounded=ungrounded, failed=len(failures),
    )
    _fail_if_every_call_failed(attempted, failures)
    return GenerationOutcome(drafts=drafts, stats=GenerationStats(
        source="questions", questions_made=len(questions),
        dropped_ungrounded=ungrounded, failed_calls=len(failures), drafts=len(drafts),
    ))
