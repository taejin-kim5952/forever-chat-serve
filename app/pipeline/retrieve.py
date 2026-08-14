"""사용자 질문 → 응답. 운영에서 실제로 도는 유일한 경로다.

```
질문 ──임베딩(1회)──┬─→ QA 인덱스 검색 ── 유사도 ≥ 임계값 ─→ answer
                    │
                    └─→ 문서 인덱스 검색 ── 유사도 ≥ 하한 ──→ related_docs
                                          └─ 그 미만 ────────→ unresolved(접수)
```

**LLM을 부르지 않는다.** 답변은 이미 스튜디오에서 만들어 사람이 검수해 둔 것이고,
여기서는 가장 가까운 질문을 찾아 그 답변을 꺼내 줄 뿐이다. 그래서 GPU 없는 운영 서버에서도
1~3초에 끝난다(대부분 임베딩 1회 비용).

임베딩은 질문당 **한 번만** 계산해서 세 곳(QA 검색 / 문서 검색 / 질문 로그)에서 돌려 쓴다.
가장 비싼 단계라 여기서 두 번 돌리면 응답 시간이 그대로 두 배가 된다.
"""

import time
from dataclasses import dataclass

from app.core.categories import category_label
from app.core.logging import get_logger, log_event
from app.core.question_log import (
    QuestionLogEntry,
    append_question_embedding,
    append_question_log,
    new_log_id,
    new_ticket_id,
    now_iso,
)
from app.core.runtime_config import load_runtime_config
from app.ingestion.doc_index import DocIndex
from app.models.schemas import AskRequest, AskResponse, RelatedDoc, SourceDoc
from app.qa import store as qa_store
from app.qa.index import QaIndex

logger = get_logger("pipeline.retrieve")

UNRESOLVED_MESSAGE = (
    "문의가 담당자에게 접수되었습니다. 확인 후 등록된 이메일로 회신드립니다."
)


@dataclass
class _Retrieved:
    result_type: str
    similarity: float | None = None
    qa_item: qa_store.QaItem | None = None
    matched_question: str | None = None
    related: list[dict] | None = None


class Retriever:
    """인덱스 핸들을 요청마다 새로 열지 않으려고 객체로 둔다 — Chroma 컬렉션을 매번
    여는 비용이 질문 1건 응답 시간에서 무시할 수 없다."""

    def __init__(self):
        self.qa_index = QaIndex()
        self.doc_index = DocIndex()

    def _search(self, question: str, category_id: str | None) -> tuple[list[float], _Retrieved]:
        config = load_runtime_config()

        query_vector, qa_hits = self.qa_index.search(question, config.qa_top_k)

        if qa_hits:
            # QA 파일은 한 번만 읽는다. 후보마다 읽으면 질문 1건에 파일을 열 번 넘게 연다.
            items = {i.qa_id: i for i in qa_store.load_qa()}

            # 주제를 고른 질문은 그 주제의 QA를 우선한다. 다만 **거르지는 않는다** —
            # 사용자가 주제를 잘못 골랐을 때 맞는 답을 통째로 못 찾게 되는 편이 더 나쁘다.
            if category_id:
                qa_hits.sort(
                    key=lambda h: (
                        getattr(items.get(h["qa_id"]), "category_id", None) == category_id,
                        h["similarity"],
                    ),
                    reverse=True,
                )

            top = qa_hits[0]
            if top["similarity"] >= config.qa_match_threshold:
                item = items.get(top["qa_id"])
                if item:
                    return query_vector, _Retrieved(
                        result_type="answer",
                        similarity=top["similarity"],
                        qa_item=item,
                        matched_question=top["matched_question"],
                    )
                # 파일에서는 지웠는데 벡터가 남은 경우. 조용히 넘기면 "가끔 답이 안 나온다"가 된다.
                log_event(logger, "qa vector without item, reindex needed", qa_id=top["qa_id"])

        doc_hits = self.doc_index.search_by_vector(query_vector, config.doc_top_k)
        related = [h for h in doc_hits if h["similarity"] >= config.related_docs_floor]
        if related:
            return query_vector, _Retrieved(
                result_type="related_docs",
                similarity=related[0]["similarity"],
                related=related[: config.related_docs_count],
            )

        # 최고 점수는 남긴다. 임계값을 어디까지 내려야 했는지 관리자 이력에서 보여야 한다.
        best = max(
            [h["similarity"] for h in qa_hits] + [h["similarity"] for h in doc_hits],
            default=None,
        )
        return query_vector, _Retrieved(result_type="unresolved", similarity=best)

    def ask(self, request: AskRequest) -> AskResponse:
        started = time.perf_counter()
        question = request.question.strip()

        query_vector, found = self._search(question, request.category_id)
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        response = self._to_response(found, elapsed_ms)
        self._record(request, question, query_vector, found, response)
        return response

    def record_support(self, request: AskRequest) -> AskResponse:
        """관련 문서만 받은 사용자가 '담당자에게 문의하기'를 누른 경우.

        검색은 이미 한 번 했으므로 다시 하지 않는다. 대신 이력에 `unresolved` 로 남긴다 —
        관리자 화면에서 "문서만 줬는데 사용자가 부족하다고 한 질문"이 바로 보여야
        다음에 만들 QA의 우선순위가 잡힌다.
        """
        question = request.question.strip()
        response = AskResponse(
            result_type="unresolved",
            message=UNRESOLVED_MESSAGE,
            ticket_id=new_ticket_id(),
        )
        log_id = new_log_id()
        response.log_id = log_id
        append_question_log(QuestionLogEntry(
            log_id=log_id,
            asked_at=now_iso(),
            question=question,
            lang=request.lang,
            category_id=request.category_id,
            category_label=category_label(request.category_id),
            result_type="unresolved",
            ticket_id=response.ticket_id,
            user_id=request.user_id,
            channel=request.channel,
        ))
        log_event(logger, "support requested", ticket_id=response.ticket_id)
        return response

    def _to_response(self, found: _Retrieved, elapsed_ms: int) -> AskResponse:
        if found.result_type == "answer" and found.qa_item:
            item = found.qa_item
            return AskResponse(
                result_type="answer",
                answer=item.answer,
                source_docs=[
                    SourceDoc(doc_id=doc_id, title=self._doc_title(doc_id))
                    for doc_id in item.source_doc_ids
                ],
                similarity=found.similarity,
                matched_qa_id=item.qa_id,
                response_time_ms=elapsed_ms,
            )

        if found.result_type == "related_docs":
            return AskResponse(
                result_type="related_docs",
                related_docs=[
                    RelatedDoc(
                        doc_id=hit["doc_id"],
                        chunk_id=hit.get("chunk_id", ""),
                        title=hit["title"],
                        section=hit["section"],
                        excerpt=hit["excerpt"],
                        url_or_ref=hit.get("url", ""),
                        similarity=hit["similarity"],
                    )
                    for hit in (found.related or [])
                ],
                similarity=found.similarity,
                response_time_ms=elapsed_ms,
            )

        return AskResponse(
            result_type="unresolved",
            message=UNRESOLVED_MESSAGE,
            ticket_id=new_ticket_id(),
            similarity=found.similarity,
            response_time_ms=elapsed_ms,
        )

    def _doc_title(self, doc_id: str) -> str:
        hits = self.doc_index.collection.get(
            where={"doc_id": doc_id}, limit=1, include=["metadatas"]
        ).get("metadatas") or []
        return (hits[0].get("title") if hits else None) or doc_id

    def _record(
        self,
        request: AskRequest,
        question: str,
        query_vector: list[float],
        found: _Retrieved,
        response: AskResponse,
    ) -> None:
        """질문 이력 적재. 운영에서 계속 살아 있어야 하는 기능이라 실패해도 응답은 나간다."""
        log_id = new_log_id()
        response.log_id = log_id

        append_question_log(QuestionLogEntry(
            log_id=log_id,
            asked_at=now_iso(),
            question=question,
            lang=request.lang,
            category_id=request.category_id,
            category_label=category_label(request.category_id),
            result_type=response.result_type,
            matched_qa_id=response.matched_qa_id,
            matched_question=found.matched_question,
            similarity=response.similarity,
            response_time_ms=response.response_time_ms,
            answer=response.answer,
            source_doc_titles=[d.title for d in response.source_docs]
            or [d.title for d in response.related_docs],
            ticket_id=response.ticket_id,
            user_id=request.user_id,
            channel=request.channel,
        ))
        # 클러스터링이 나중에 수천 건을 다시 임베딩하지 않도록 지금 계산한 벡터를 남긴다.
        append_question_embedding(log_id, query_vector)

        if response.matched_qa_id:
            qa_store.bump_hit_count(response.matched_qa_id)

        log_event(
            logger,
            "ask",
            result_type=response.result_type,
            similarity=response.similarity,
            elapsed_ms=response.response_time_ms,
            channel=request.channel,
        )


_retriever: Retriever | None = None


def get_retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever


def reset_retriever() -> None:
    """문서·QA를 재색인한 뒤와 테스트에서 인덱스 핸들을 새로 잡는다."""
    global _retriever
    _retriever = None
