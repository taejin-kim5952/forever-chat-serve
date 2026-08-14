import json
import re
from dataclasses import dataclass

import ollama

from app.core.config import get_settings
from app.eval.golden_set import GoldenItem
from app.pipeline.rag import RagPipeline

_JUDGE_PROMPT = """당신은 RAG 챗봇의 답변 품질을 채점하는 평가자입니다.
아래 질문, 기대 답변 요약, 실제 생성된 답변을 비교해 1~5점으로 채점하세요.

- 5점: 기대 답변의 핵심 내용을 정확히 포함하고 근거 문서에 반영된 사실만 서술
- 3점: 핵심 내용 일부만 포함하거나 다소 모호함
- 1점: 기대 답변과 무관하거나 사실과 다른 내용(환각) 포함

질문: {question}
기대 답변 요약: {expected}
실제 생성된 답변: {actual}

반드시 아래 JSON 형식으로만 답하세요:
{{"score": <1-5 정수>, "reason": "<한 줄 이유>"}}
"""


@dataclass
class JudgeResult:
    question: str
    score: int
    reason: str


def _parse_score(raw: str) -> tuple[int, str]:
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        return 1, f"파싱 실패: {raw[:200]}"
    try:
        data = json.loads(match.group(0))
        return int(data.get("score", 1)), str(data.get("reason", ""))
    except (json.JSONDecodeError, ValueError):
        return 1, f"파싱 실패: {raw[:200]}"


def judge_answers(
    items: list[GoldenItem],
    rag_pipeline: RagPipeline | None = None,
    answer_model: str | None = None,
    judge_model: str | None = None,
    progress=None,
) -> list[JudgeResult]:
    """골든셋 문항을 실제로 물어보고 답변을 채점한다.

    `answer_model` 과 `judge_model` 을 다르게 주는 것을 권한다 — 같은 모델이 답하고 채점하면
    자기 답변에 후한 점수를 준다(자기 채점 편향).
    """
    settings = get_settings()
    rag_pipeline = rag_pipeline or RagPipeline()
    client = ollama.Client(host=settings.ollama_host)
    judge_model = judge_model or settings.ollama_llm_model

    results: list[JudgeResult] = []
    for index, item in enumerate(items, start=1):
        if progress:
            progress(index - 1, len(items), f"답변·채점 중… ({index}/{len(items)})")
        rag_result = rag_pipeline.answer(item.question, model=answer_model)
        answer = rag_result.answer or "(답변 없음)"

        # 답 없는 질문(오매칭)은 '답하지 않는 것'이 정답이므로 별도로 판정한다.
        if item.is_confusion_test:
            declined = not rag_result.answer
            results.append(JudgeResult(
                question=item.question,
                score=5 if declined else 1,
                reason="미해결로 올바르게 처리함" if declined else f"답하지 말아야 하는데 답함: {answer[:80]}",
            ))
            continue

        prompt = _JUDGE_PROMPT.format(
            question=item.question,
            expected=item.expected_answer_summary,
            actual=answer,
        )
        response = client.chat(
            model=judge_model,
            think=settings.ollama_think,
            messages=[{"role": "user", "content": prompt}],
            options={"num_ctx": 8192, "num_predict": 512},
        )
        score, reason = _parse_score(response["message"]["content"] or "")
        results.append(JudgeResult(question=item.question, score=score, reason=reason))

    if progress:
        progress(len(items), len(items), "완료")
    return results


def average_score(results: list[JudgeResult]) -> float:
    if not results:
        return 0.0
    return sum(r.score for r in results) / len(results)
