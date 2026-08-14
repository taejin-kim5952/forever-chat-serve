"""RAG 문서에서 평가용 질문을 자동 생성한다(합성 평가셋).

사람이 골든셋을 손으로 쓰는 대신, 문서 청크를 뽑아 "이 내용으로 답할 수 있는 질문"을
LLM에게 만들게 한다. **질문을 만든 청크가 곧 정답 출처**이므로 사람 라벨링 없이
검색 정확도(Recall@k, MRR)를 잴 수 있다.

품질을 좌우하는 세 가지를 프롬프트/구조로 처리한다.

1. **문장 베끼기 방지** — 문서 표현을 그대로 옮긴 질문은 검색이 너무 쉬워 점수가 부풀려진다.
   실제 사용자 말투로 바꿔 쓰도록 강제하고, 다듬어지지 않은 구어체도 섞게 한다.
2. **답이 없는 질문(negative)** — 전부 답할 수 있는 질문만 있으면 fallback 동작을 검증할 수 없다.
   문서에 근거가 없는 질문을 일정 비율로 생성해 `is_confusion_test` 로 표시한다.
3. **모델 분리** — 생성 모델을 답변 모델과 다르게 고를 수 있게 한다. 같은 모델이 문제를 내고
   풀면 점수가 후해진다(자기 채점 편향).
"""

import random
import re
from dataclasses import dataclass

import ollama

from app.core.config import get_settings
from app.core.logging import get_logger, log_event
from app.ingestion.loader import VectorStoreLoader

logger = get_logger("eval.question_gen")

_ANSWERABLE_PROMPT = """당신은 사내 포털 사용 가이드 문서를 읽고, 실제 사용자가 할 법한 질문을 만드는 사람입니다.

아래 문서 발췌를 읽고, **이 내용으로 답할 수 있는 질문**을 {count}개 만드세요.

[규칙]
1. 문서에 있는 문장을 그대로 옮기지 마세요. 실제 사용자가 검색창에 칠 법한 표현으로 바꿔 쓰세요.
2. 표현을 다양하게 섞으세요 — 정중한 문장, 짧은 구어체, 오타 섞인 것, 명사만 나열한 것 등.
   (예: "권한그룹은 무엇을 선택해야 하나요?", "권한그룹 뭐 골라요?", "권한그룹 선택 기준")
3. 문서를 보지 않은 사람이 던질 질문이어야 합니다. "위 문서에 따르면" 같은 표현은 쓰지 마세요.
4. 질문마다 한 줄 요약 정답을 함께 적으세요(문서 근거만 사용).
5. **질문과 정답 요약은 반드시 한국어로만 쓰세요.** 영어·중국어 등 다른 언어의 단어나 문장을
   섞지 마세요. 문서에 그대로 적힌 고유명사·화면명·필드명·코드(예: OAS 3.0, Swagger, Path)만 예외입니다.

[문서 발췌]
{context}

[출력 형식] 아래 형식을 정확히 지키고, 다른 말은 쓰지 마세요.
Q: (질문)
A: (한 줄 정답 요약)
Q: (질문)
A: (한 줄 정답 요약)"""

_UNANSWERABLE_PROMPT = """당신은 사내 포털 챗봇을 시험하는 사람입니다.

아래는 챗봇이 답할 수 있는 문서의 주제 목록입니다.
이 주제들과 **비슷해 보이지만 문서로는 답할 수 없는** 질문을 {count}개 만드세요.

[규칙]
1. 같은 업무 영역처럼 들려야 합니다(엉뚱한 잡담은 안 됩니다).
2. 문서에 없는 기능·수치·정책을 묻는 질문이어야 합니다.
   (예: "API 호출 요금은 얼마인가요?", "작년 API 등록 건수 통계 보여주세요")
3. 질문만 한 줄씩 쓰세요.
4. **반드시 한국어로만 쓰세요.** 다른 언어를 섞지 마세요.

[문서 주제]
{topics}

[출력 형식]
Q: (질문)
Q: (질문)"""


@dataclass
class GeneratedItem:
    question: str
    expected_answer_summary: str
    expected_source: str
    category: str
    is_confusion_test: bool = False

    def to_row(self) -> dict:
        return {
            "question": self.question,
            "lang": "ko",
            "expected_answer_summary": self.expected_answer_summary,
            "expected_source": self.expected_source,
            "category": self.category,
            "is_confusion_test": self.is_confusion_test,
            # 사람이 쓴 문항과 구분해 나중에 걷어낼 수 있게 표시한다.
            "generated": True,
        }


def _chat(client: ollama.Client, model: str, prompt: str) -> str:
    settings = get_settings()
    response = client.chat(
        model=model,
        think=settings.ollama_think,
        messages=[{"role": "user", "content": prompt}],
        options={"num_ctx": 8192, "num_predict": 1024},
    )
    return response["message"]["content"] or ""


def _parse_qa(raw: str) -> list[tuple[str, str]]:
    """`Q:` / `A:` 쌍을 뽑는다. A 가 없으면 빈 문자열로 둔다."""
    pairs: list[tuple[str, str]] = []
    question: str | None = None
    for line in raw.splitlines():
        line = line.strip()
        q = re.match(r"^Q\s*[:.)]\s*(.+)$", line)
        a = re.match(r"^A\s*[:.)]\s*(.+)$", line)
        if q:
            if question:
                pairs.append((question, ""))
            question = q.group(1).strip()
        elif a and question:
            pairs.append((question, a.group(1).strip()))
            question = None
    if question:
        pairs.append((question, ""))
    return [(q, a) for q, a in pairs if len(q) >= 5]


_LIST_MARKER = re.compile(r"^(?:[-*•]|\d+[.)]|Q\s*[:.)])\s*")

_HANGUL = re.compile(r"[가-힣]")
# 한글이 아닌 CJK(중국어/일본어 가나) — 소형 다국어 모델이 가장 흔하게 흘리는 문자들
_OTHER_CJK = re.compile(r"[぀-ヿ一-鿿]")
# 영어 문장임을 드러내는 기능어. 고유명사(OAS, Swagger)와 달리 문장 구조에만 나타난다.
_ENGLISH_FUNCTION_WORDS = re.compile(
    r"\b(?:the|is|are|was|were|how|what|which|do|does|did|can|could|should|"
    r"you|your|i|we|they|of|and|for|with|from|to|in|on|at|it|this|that)\b",
    re.IGNORECASE,
)
_ENGLISH_SENTENCE_HITS = 3


def is_korean(text: str) -> bool:
    """한국어 문장인지 판정한다.

    프롬프트로 "한국어로만 쓰라"고 해도 4B~8B 다국어 모델은 영어 문장이나 중국어 조각을
    섞어 내보내는 경우가 있다. 평가셋에 그런 문항이 섞이면 점수가 왜곡되므로 걸러낸다.

    한글 '비율'로 재면 `OAS 3.0 Swagger YAML 등록` 같은 명사 나열형 질문이 억울하게 걸린다.
    그래서 (1) 한글이 하나도 없거나 (2) 다른 CJK 문자가 섞였거나 (3) 영어 기능어가 여러 개
    나오는(= 영어 문장인) 경우만 걸러낸다.
    """
    stripped = text.strip()
    if not stripped:
        return False
    if _OTHER_CJK.search(stripped):
        return False
    if not _HANGUL.search(stripped):
        return False
    return len(_ENGLISH_FUNCTION_WORDS.findall(stripped)) < _ENGLISH_SENTENCE_HITS


def _parse_questions(raw: str) -> list[str]:
    """질문만 뽑는다. 형식 지시를 무시하고 그냥 한 줄씩 나열하는 모델이 흔해서 관대하게 읽는다."""
    pairs = _parse_qa(raw)
    if pairs:
        return [q for q, _ in pairs]

    questions = []
    for line in raw.splitlines():
        line = _LIST_MARKER.sub("", line.strip()).strip()
        # 대괄호 머리말('[출력 형식]')이나 너무 짧은 줄은 버린다.
        if len(line) >= 8 and not line.startswith("["):
            questions.append(line)
    return questions


def _sample_chunks(store: VectorStoreLoader, sample_size: int, seed: int | None) -> list[dict]:
    got = store.collection.get(include=["documents", "metadatas"])
    documents = got.get("documents") or []
    metadatas = got.get("metadatas") or []
    chunks = [{"text": d, "meta": m} for d, m in zip(documents, metadatas) if d]
    if not chunks:
        return []
    rng = random.Random(seed)
    rng.shuffle(chunks)
    return chunks[:sample_size]


def generate_questions(
    count: int = 20,
    model: str | None = None,
    unanswerable_ratio: float = 0.2,
    per_chunk: int = 2,
    seed: int | None = None,
    store: VectorStoreLoader | None = None,
    progress=None,
) -> list[GeneratedItem]:
    """문서에서 평가용 질문을 생성한다.

    `progress(done, total, stage)` 를 주면 진행 상황을 알려준다(오래 걸리는 작업이라 화면이 폴링한다).
    """
    settings = get_settings()
    model = model or settings.ollama_llm_model
    store = store or VectorStoreLoader()
    client = ollama.Client(host=settings.ollama_host)

    negative_target = int(round(count * max(0.0, min(1.0, unanswerable_ratio))))
    positive_target = max(0, count - negative_target)

    chunk_need = max(1, -(-positive_target // max(1, per_chunk)))   # 올림 나눗셈
    chunks = _sample_chunks(store, chunk_need, seed)
    if not chunks:
        log_event(logger, "question generation skipped: no chunks")
        return []

    items: list[GeneratedItem] = []
    dropped_lang = 0
    total_steps = len(chunks) + (1 if negative_target else 0)

    for index, chunk in enumerate(chunks, start=1):
        if progress:
            progress(index - 1, total_steps, f"질문 생성 중… ({len(items)}/{count})")
        meta = chunk["meta"]
        raw = _chat(client, model, _ANSWERABLE_PROMPT.format(
            count=per_chunk,
            context=f"[{meta.get('title')} - {meta.get('section_title')}]\n{chunk['text']}",
        ))
        for question, answer in _parse_qa(raw)[:per_chunk]:
            if len(items) >= positive_target:
                break
            # 다른 언어가 섞인 문항은 평가 점수를 왜곡하므로 버린다.
            if not is_korean(question) or (answer and not is_korean(answer)):
                dropped_lang += 1
                continue
            items.append(GeneratedItem(
                question=question,
                expected_answer_summary=answer,
                expected_source=meta.get("doc_id", ""),
                category=meta.get("category", "") or meta.get("title", ""),
            ))

    positives_made = len(items)
    if negative_target:
        if progress:
            progress(len(chunks), total_steps, "답 없는 질문 생성 중…")
        topics = sorted({f"{c['meta'].get('title')} - {c['meta'].get('section_title')}" for c in chunks})
        raw = _chat(client, model, _UNANSWERABLE_PROMPT.format(
            count=negative_target, topics="\n".join(f"- {t}" for t in topics[:12]),
        ))
        for question in _parse_questions(raw):
            if len(items) - positives_made >= negative_target:
                break
            if not is_korean(question):
                dropped_lang += 1
                continue
            items.append(GeneratedItem(
                question=question,
                expected_answer_summary="문서에 근거가 없어 답변할 수 없어야 한다(미해결 처리 기대).",
                expected_source="",
                category="오매칭",
                is_confusion_test=True,
            ))

    if progress:
        progress(total_steps, total_steps, "완료")
    log_event(
        logger, "questions generated",
        model=model, requested=count, produced=len(items),
        negatives=sum(1 for i in items if i.is_confusion_test),
        dropped_non_korean=dropped_lang,
    )
    return items
