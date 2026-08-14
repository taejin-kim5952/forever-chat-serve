"""질문 클러스터로부터 RAG 문서 초안을 생성한다.

여기서는 LLM을 쓴다 — 클러스터링과 달리 '없던 문장을 만드는 것'이 본질이기 때문이다.
생성한 초안은 저장하지 않고 화면에 돌려주며, 운영자가 다듬은 뒤 `POST /admin/docs` 로 저장한다.
"""

from dataclasses import dataclass

import ollama

from app.core.config import get_settings
from app.core.logging import get_logger, log_event
from app.core.runtime_config import load_runtime_config
from app.ingestion.loader import VectorStoreLoader

logger = get_logger("pipeline.draft")

_DRAFT_RULES = """당신은 KT OpenAPI Portal 'API Manager' 사용 가이드 문서를 작성하는 테크니컬 라이터입니다.
사용자들이 반복해서 물었지만 기존 문서로는 충분히 답하지 못한 질문 목록을 받았습니다.
이 질문들에 답하는 **새 가이드 문서 초안**을 마크다운으로 작성하세요.

[작성 규칙]
1. 아래 '자주 나온 질문'을 모두 다루는 하나의 문서를 만든다.
2. 기존 문서 발췌가 함께 주어지면 그 사실과 어긋나지 않게 쓰고, 화면명·경로·필드명은 그대로 유지한다.
3. 확실하지 않은 내용은 지어내지 말고 `(확인 필요)` 로 표시해 담당자가 채우게 한다.
4. 말투는 '~합니다' 체로 통일한다.
4-1. **문서 전체를 한국어로만 쓴다.** 영어·중국어 등 다른 언어의 단어나 문장을 섞지 않는다.
   문서에 그대로 적힌 고유명사·화면명·필드명·경로·코드만 예외다.
5. 아래 형식을 정확히 지킨다. frontmatter 를 반드시 포함한다.

---
title: (문서 제목)
category: (분류)
url: (관련 화면 경로, 모르면 비워둔다)
---

# (문서 제목)

## (소제목)
(내용 — 절차는 번호 목록, 개념 설명은 2~3문장)

[출력] 위 마크다운 본문만 출력한다. 설명이나 인사말을 덧붙이지 않는다."""


@dataclass
class DraftResult:
    content: str
    model_used: str


def _reference_context(questions: list[str], top_k: int) -> str:
    """질문들로 기존 문서를 검색해 초안의 사실 근거로 넣는다.

    이미 있는 내용을 다시 쓰지 않게 하고, 용어·경로 표기를 기존 문서와 맞추기 위함이다.
    """
    store = VectorStoreLoader()
    blocks: list[str] = []
    seen: set[str] = set()
    for question in questions[:3]:
        for hit in store.query(question, top_k=top_k):
            meta = hit["metadata"]
            key = f"{meta.get('doc_id')}#{meta.get('section_title')}"
            if key in seen:
                continue
            seen.add(key)
            blocks.append(f"[{meta.get('title')} - {meta.get('section_title')}]\n{hit['text']}")
    return "\n\n---\n\n".join(blocks)


def generate_draft(clusters: list[dict], category_label: str | None = None, model: str | None = None) -> DraftResult:
    settings = get_settings()
    runtime_config = load_runtime_config()
    model = model or settings.ollama_llm_model

    questions = [c["question"] for c in clusters]
    lines = [
        f"- {c['question']} (질문 {c['count']}건, 미해결률 {c['unresolved_rate']}%)"
        + (f"\n  의도: {c['summary']}" if c.get("summary") else "")
        for c in clusters
    ]

    context = _reference_context(questions, runtime_config.rag_top_k)
    user_prompt = "자주 나온 질문:\n" + "\n".join(lines)
    if category_label:
        user_prompt += f"\n\n문서 분류: {category_label}"
    if context:
        user_prompt += f"\n\n기존 문서 발췌(사실 근거):\n{context}"

    client = ollama.Client(host=settings.ollama_host)
    response = client.chat(
        model=model,
        think=settings.ollama_think,
        messages=[
            {"role": "system", "content": _DRAFT_RULES},
            {"role": "user", "content": user_prompt},
        ],
        options={
            "num_ctx": runtime_config.ollama_num_ctx,
            "num_predict": runtime_config.ollama_num_predict,
        },
    )
    content = (response["message"]["content"] or "").strip()
    log_event(logger, "draft generated", clusters=len(clusters), model=model, chars=len(content))
    return DraftResult(content=content, model_used=model)
