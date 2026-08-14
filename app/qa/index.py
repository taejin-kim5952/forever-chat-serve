"""QA 벡터 색인 · 검색.

`qa_index` 컬렉션에는 **답변이 아니라 질문이 들어간다.** 사용자 질문과 비교할 대상은
질문이기 때문이다. 답변으로 색인하면 "API 등록 절차가 궁금해요" 같은 질문이
답변 본문의 서술문과 잘 맞지 않는다.

한 QA 항목의 대표 질문과 변형 질문이 **각각 하나의 벡터**로 들어가고, 모두 같은 `qa_id`
메타데이터를 갖는다. 그래서 상위 k 건에 같은 QA가 여러 번 나올 수 있고, 검색 결과는
`qa_id` 단위로 최고 점수만 남겨 접는다.

임베딩 태스크는 `similarity`(대칭)를 쓴다. 질문으로 질문을 찾는 일이라 한쪽만 query 로
취급하면 오히려 어긋난다 — `app/ingestion/embedder.py` 참고.
"""

from app.core.config import get_settings
from app.core.logging import get_logger, log_event
from app.ingestion.embedder import OllamaEmbedder
from app.ingestion.vector_store import qa_collection, rebuild_collection, to_similarity
from app.qa.store import QaItem, load_qa, serving_items

logger = get_logger("qa.index")

_QA_ID_KEY = "qa_id"


class QaIndex:
    def __init__(self):
        self.collection = qa_collection()
        self.embedder = OllamaEmbedder()

    # ------------------------------------------------------------------ 색인

    def _vector_ids(self, item: QaItem) -> list[str]:
        return [f"{item.qa_id}::{n}" for n in range(len(item.match_texts()))]

    def remove_item(self, qa_id: str) -> None:
        self.collection.delete(where={_QA_ID_KEY: qa_id})

    def upsert_item(self, item: QaItem) -> int:
        """항목 1건을 색인에 반영한다. 검수를 통과하지 않았으면 색인에서 지운다.

        변형 질문을 지우면 벡터 수가 줄어드는데, upsert 만으로는 남는 벡터가 그대로
        검색된다. 그래서 항상 **먼저 지우고 다시 넣는다.**
        """
        self.remove_item(item.qa_id)

        if item.status not in {"approved"} or not item.answer.strip():
            return 0

        texts = item.match_texts()
        if not texts:
            return 0

        embeddings = self.embedder.embed_batch(texts, task="similarity")
        self.collection.upsert(
            ids=self._vector_ids(item),
            embeddings=embeddings,
            documents=texts,
            metadatas=[
                {_QA_ID_KEY: item.qa_id, "is_variant": n > 0, "category_id": item.category_id or ""}
                for n in range(len(texts))
            ],
        )
        return len(texts)

    def rebuild(self) -> dict:
        """전체 재색인. 임베딩 모델을 바꿨거나, 파일을 직접 편집해 넣었을 때 쓴다."""
        self.collection = rebuild_collection(get_settings().chroma_qa_collection)
        items = serving_items(load_qa())
        vectors = 0
        for item in items:
            vectors += self.upsert_item(item)
        log_event(logger, "qa index rebuilt", items=len(items), vectors=vectors)
        return {"items": len(items), "vectors": vectors}

    def count(self) -> int:
        return self.collection.count()

    # ------------------------------------------------------------------ 검색

    def search(self, question: str, top_k: int) -> tuple[list[float], list[dict]]:
        """`(질문 임베딩, 검색 결과)`.

        임베딩을 함께 돌려주는 이유: `related_docs` 로 넘어갈 때와 질문 로그에 남길 때
        같은 벡터를 재사용한다. 한 질문에 임베딩을 두 번 돌리면 응답 시간이 두 배가 된다.
        """
        query_vector = self.embedder.embed(question, task="similarity")
        return query_vector, self.search_by_vector(query_vector, top_k)

    def search_by_vector(self, query_vector: list[float], top_k: int) -> list[dict]:
        total = self.collection.count()
        if total == 0:
            return []

        results = self.collection.query(
            query_embeddings=[query_vector],
            n_results=min(top_k, total),
            include=["documents", "metadatas", "distances"],
        )
        documents = (results.get("documents") or [[]])[0]
        metadatas = (results.get("metadatas") or [[]])[0]
        distances = (results.get("distances") or [[]])[0]

        # 같은 QA의 변형 질문이 여러 개 잡히므로 qa_id 단위로 최고 점수만 남긴다.
        best: dict[str, dict] = {}
        for text, meta, dist in zip(documents, metadatas, distances):
            qa_id = meta.get(_QA_ID_KEY)
            if not qa_id:
                continue
            similarity = to_similarity(dist)
            current = best.get(qa_id)
            if current is None or similarity > current["similarity"]:
                best[qa_id] = {
                    "qa_id": qa_id,
                    "matched_question": text,
                    "is_variant": bool(meta.get("is_variant")),
                    "similarity": similarity,
                }
        return sorted(best.values(), key=lambda h: h["similarity"], reverse=True)
