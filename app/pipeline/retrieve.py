"""사용자 질문 → 응답. 운영에서 실제로 도는 유일한 경로다.

```
질문 ──엔티티 추출──→ 라이브 인텐트 적중 ─→ 사이트 API ─→ 템플릿 ─→ live_answer
   │                        └ 실패·타임아웃 ─→ 아래로 폴백
   └──임베딩(1회)──┬─→ QA 인덱스 검색 ── 유사도 ≥ 임계값 ─→ answer
                   │
                   └─→ 문서 인덱스 검색 ── 유사도 ≥ 하한 ──→ related_docs
                                         └─ 그 미만 ────────→ unresolved(접수)
```

**라이브 조회를 끄면 지금까지와 완전히 같은 경로**다. 팩의 `routes.lookup` 이 꺼져 있으면
(기본값) 프로바이더가 하나도 없고, 아래 `_live()` 는 곧바로 None 을 돌려준다.

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
from app.core.config import get_settings
from app.core.runtime_config import load_runtime_config
from app.ingestion.doc_index import DocIndex
from app.models.schemas import AskRequest, AskResponse, LiveAction, RelatedDoc, SourceDoc
from app.pipeline.lookup import entities as lookup_entities
from app.pipeline.lookup.base import LiveAnswer, Principal
from app.pipeline.lookup.providers.mcp_portal import Forbidden
from app.qa import store as qa_store
from app.qa.index import QaIndex

logger = get_logger("pipeline.retrieve")

UNRESOLVED_MESSAGE = (
    "문의가 담당자에게 접수되었습니다. 확인 후 등록된 이메일로 회신드립니다."
)


FORBIDDEN_MESSAGE = (
    "이 서버는 조회 권한이 없습니다. 담당자에게 열람 권한을 신청하신 뒤 다시 물어봐 주세요."
)


@dataclass
class _Retrieved:
    result_type: str
    similarity: float | None = None
    qa_item: qa_store.QaItem | None = None
    matched_question: str | None = None
    related: list[dict] | None = None
    live: LiveAnswer | None = None


class Retriever:
    """인덱스 핸들을 요청마다 새로 열지 않으려고 객체로 둔다 — Chroma 컬렉션을 매번
    여는 비용이 질문 1건 응답 시간에서 무시할 수 없다."""

    def __init__(self):
        self.qa_index = QaIndex()
        self.doc_index = DocIndex()
        # 기동 때 한 번 세운다. 팩이 라이브를 끄고 있으면 빈 목록이다.
        from app.pipeline.lookup.registry import load_providers

        self.lookup_providers = load_providers()

    def _search(self, question: str, category_id: str | None,
                query_vector: list[float] | None = None) -> tuple[list[float], _Retrieved]:
        """:param query_vector: 이미 계산해 둔 질문 임베딩. 프로젝트를 고르느라 한 번 계산한
        것을 그대로 쓴다(`app/pipeline/scope.py`) — 가장 비싼 단계라 두 번 돌리면 응답
        시간이 그대로 두 배다.
        """
        config = load_runtime_config()

        if query_vector is None:
            query_vector, qa_hits = self.qa_index.search(question, config.qa_top_k)
        else:
            qa_hits = self.qa_index.search_by_vector(query_vector, config.qa_top_k)

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

    def ask(self, request: AskRequest, principal: Principal | None = None,
            query_vector: list[float] | None = None) -> AskResponse:
        """:param principal: 질문한 사람의 자격. 없으면 익명이라 라이브 경로를 타지 않는다.
        :param query_vector: 미리 계산한 질문 임베딩(선택).
        """
        started = time.perf_counter()
        question = request.question.strip()

        # 라이브가 답할 수 있으면 그것이 먼저다 — 값이 수시로 바뀌는 질문은
        # 검수된 답변이 오히려 틀린 답이 된다.
        live = self._live(question, principal or Principal(), request.context)
        if live is not None:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            response = self._to_response(live, elapsed_ms)
            # 임베딩을 하지 않았으므로 벡터가 없다. 이력에는 질문·인텐트만 남는다 —
            # 라이브 응답 본문은 그 시점의 사용자 데이터라 저장하지 않는다 (계획서 §4.5).
            self._record(request, question, None, live, response)
            return response

        query_vector, found = self._search(question, request.category_id, query_vector)
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        response = self._to_response(found, elapsed_ms)
        self._record(request, question, query_vector, found, response)
        return response

    def _live(self, question: str, principal: Principal,
              context: dict | None = None) -> _Retrieved | None:
        """라이브 조회. 답할 것이 없으면 None 이고, 호출부는 지금까지의 경로로 간다.

        **실패는 조용히 폴백한다.** 사이트 API 가 죽어도 챗봇은 절차 안내를 계속해야 한다.
        예외는 403 뿐이다 — 권한 없음은 문서를 보여준다고 풀리지 않는다.
        """
        if not self.lookup_providers:
            return None

        if principal.anonymous():
            # 자격이 없으면 라이브 경로를 아예 타지 않는다 (계획서 §4.5).
            return None

        target, confidence = lookup_entities.extract(question)
        if not target or confidence < lookup_entities.MIN_CONFIDENCE:
            # 질문에 이름이 없으면 **지금 보고 있는 화면**을 본다 (계획서 §5.7).
            # 검증 화면에서 "왜 안 되나요" 만 쳐도 그 Version 을 짚는 것이 위젯의 값어치다.
            target, confidence = self._context_target(context)
            if not target:
                return None
        target = dict(target, confidence=confidence)

        for provider in self.lookup_providers:
            intent = provider.match(question, target)
            if intent is None:
                continue
            try:
                data = provider.fetch(intent, principal)
            except Forbidden:
                log_event(logger, "live lookup forbidden", intent=provider.id)
                return _Retrieved(result_type="unresolved", similarity=None)
            if not data:
                log_event(logger, "live lookup empty — falling back", intent=provider.id)
                return None
            answer = provider.render(intent, data)
            if answer is None:
                return None
            log_event(logger, "live answer", intent=provider.id,
                      confidence=confidence, target=target.get("name"))
            return _Retrieved(result_type="live_answer", live=answer)
        return None

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

    @staticmethod
    def _context_target(context: dict | None) -> tuple[dict, float]:
        """화면 맥락에서 대상을 뽑는다.

        **확신도는 1.0 이다.** 사용자가 그 화면을 보고 있다는 것은 추측이 아니라 사실이고,
        사전 대조처럼 틀릴 여지가 없다.
        """
        if not isinstance(context, dict):
            return {}, 0.0
        version_id = context.get("versionId")
        if version_id is None:
            return {}, 0.0
        return {
            "kind": "server",
            "version_id": version_id,
            "server_id": context.get("serverId"),
            "name": context.get("serverName"),
        }, 1.0

    def _to_response(self, found: _Retrieved, elapsed_ms: int) -> AskResponse:
        if found.result_type == "live_answer" and found.live:
            live = found.live
            return AskResponse(
                result_type="live_answer",
                answer=live.text,
                fetched_at=live.fetched_at.strftime("%Y-%m-%d %H:%M"),
                source_label=live.source_label,
                actions=[LiveAction(label=a.label, url=a.url) for a in live.actions],
                stale=live.stale,
                response_time_ms=elapsed_ms,
            )
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
        query_vector: list[float] | None,
        found: _Retrieved,
        response: AskResponse,
    ) -> None:
        """질문 이력 적재. 운영에서 계속 살아 있어야 하는 기능이라 실패해도 응답은 나간다.

        **라이브 답변의 본문은 남기지 않는다** (계획서 §4.5). 검수된 답변은 인덱스에서
        다시 찾을 수 있지만 라이브 값은 그 시점의 사용자 데이터다 — 질문 이력을 보는
        관리자가 남의 서버 상태를 읽게 되면 안 된다.
        """
        log_id = new_log_id()
        response.log_id = log_id
        live = response.result_type == "live_answer"

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
            answer=None if live else response.answer,
            source_doc_titles=[d.title for d in response.source_docs]
            or [d.title for d in response.related_docs],
            ticket_id=response.ticket_id,
            user_id=request.user_id,
            channel=request.channel,
        ))
        # 클러스터링이 나중에 수천 건을 다시 임베딩하지 않도록 지금 계산한 벡터를 남긴다.
        # 라이브 경로는 임베딩을 하지 않으므로 남길 벡터가 없다.
        if query_vector is not None:
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


# 프로젝트마다 한 벌. 한 서버가 'API Link' · 'API Manager' · 'MCP' 를 함께 담으므로
# 핸들도 그만큼 필요하다. 키는 그 프로젝트의 팩 경로다 — 프로젝트 id 로 잡으면 단일 팩
# 설치(프로젝트를 고르지 않는 요청)가 키를 공유해 **다른 팩의 인덱스를 쓴다.**
_retrievers: dict[str, Retriever] = {}


def get_retriever() -> Retriever:
    key = get_settings().pack_dir
    found = _retrievers.get(key)
    if found is None:
        found = _retrievers[key] = Retriever()
    return found


def reset_retriever() -> None:
    """문서·QA를 재색인한 뒤와 테스트에서 인덱스 핸들을 새로 잡는다.

    **전부 버린다.** 지금 프로젝트 것만 버리면, 재색인 뒤에 다른 프로젝트가 옛 핸들을 들고
    있다가 "어떤 프로젝트는 반영되고 어떤 프로젝트는 안 되는" 상태가 된다.
    """
    _retrievers.clear()
