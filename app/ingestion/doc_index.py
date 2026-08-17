"""원본 문서 색인 · 검색.

이 인덱스는 **답변을 만들지 않는다.** 검수된 QA에서 답을 못 찾았을 때
"직접 답은 없지만 이 문서를 보시면 됩니다"를 내주는 차선책(`related_docs`)용이다.

운영(serve)에도 이 인덱스는 올라간다. 문서 본문 자체가 사용자에게 도움이 되고,
LLM 없이 임베딩만으로 동작하기 때문이다.
"""

from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger, log_event
from app.ingestion.chunker import (
    Chunk,
    chunk_markdown_file,
    excerpt,
    oversize_chunks,
    strip_media,
)
from app.ingestion.embedder import OnnxEmbedder
from app.ingestion.vector_store import doc_collection, rebuild_collection, to_similarity

logger = get_logger("ingestion.doc_index")

_DOC_HASH_KEY = "doc_hash"


class DocIndex:
    def __init__(self, check_model: bool = True):
        # `check_model=False` 는 **재색인 경로 전용**이다(app/qa/index.py 의 같은 주석 참고).
        self.collection = doc_collection(check_model=check_model)
        self.embedder = OnnxEmbedder()

    # ------------------------------------------------------------------ 색인

    def _existing_hash(self, doc_id: str) -> str | None:
        results = self.collection.get(where={"doc_id": doc_id}, limit=1, include=["metadatas"])
        metadatas = results.get("metadatas") or []
        if metadatas and _DOC_HASH_KEY in metadatas[0]:
            return metadatas[0][_DOC_HASH_KEY]
        return None

    def delete_doc(self, doc_id: str) -> None:
        self.collection.delete(where={"doc_id": doc_id})

    def count_chunks(self, doc_id: str) -> int:
        return len(self.collection.get(where={"doc_id": doc_id}, include=[]).get("ids") or [])

    def _upsert(self, doc_hash: str, chunks: list[Chunk]) -> int:
        if not chunks:
            return 0
        oversize_chunks(chunks, log_to=logger)
        texts = [c.text for c in chunks]
        # **저장은 원문, 임베딩은 그림 표기를 걷어낸 것.** 화면은 그림을 그려야 하고,
        # 벡터에는 파일 경로가 섞이면 안 된다(chunker.strip_media 참고).
        # 긴 본문 쪽이므로 document 태스크. 질문은 query 태스크로 넣는다(비대칭 검색).
        embeddings = self.embedder.embed_batch([strip_media(t) for t in texts], task="document")
        self.collection.upsert(
            ids=[c.chunk_id for c in chunks],
            embeddings=embeddings,
            documents=texts,
            metadatas=[{**c.metadata, _DOC_HASH_KEY: doc_hash} for c in chunks],
        )
        return len(chunks)

    def ingest_file(self, path: Path, force: bool = False) -> int:
        doc_hash, chunks = chunk_markdown_file(path)
        doc_id = path.stem

        if not force and self._existing_hash(doc_id) == doc_hash:
            log_event(logger, "doc unchanged, skipping", doc_id=doc_id)
            return 0

        # 문서를 고치면 절이 줄어들 수 있다. 남은 옛 청크가 계속 검색되지 않도록 먼저 지운다.
        self.delete_doc(doc_id)
        count = self._upsert(doc_hash, chunks)
        log_event(logger, "doc ingested", doc_id=doc_id, chunks=count)
        return count

    def ingest_dir(self, force: bool = False) -> dict[str, int]:
        raw_dir = Path(get_settings().raw_docs_dir)
        return {p.stem: self.ingest_file(p, force=force) for p in sorted(raw_dir.glob("*.md"))}

    def rebuild(self) -> dict[str, int]:
        """임베딩 모델을 바꾼 뒤 전체를 다시 색인한다."""
        self.collection = rebuild_collection(get_settings().chroma_doc_collection)
        return self.ingest_dir(force=True)

    # ------------------------------------------------------------------ 검색

    def search(self, question: str, top_k: int) -> list[dict]:
        query_vector = self.embedder.embed(question, task="query")
        return self.search_by_vector(query_vector, top_k)

    def search_by_vector(self, query_vector: list[float], top_k: int) -> list[dict]:
        if self.collection.count() == 0:
            return []
        results = self.collection.query(
            query_embeddings=[query_vector],
            n_results=min(top_k, self.collection.count()),
            include=["documents", "metadatas", "distances"],
        )
        # ids 는 include 에 넣지 않아도 항상 온다. 화면이 출처 상세 모달을 열 때 쓴다.
        ids = (results.get("ids") or [[]])[0]
        documents = (results.get("documents") or [[]])[0]
        metadatas = (results.get("metadatas") or [[]])[0]
        distances = (results.get("distances") or [[]])[0]

        hits = []
        for chunk_id, text, meta, dist in zip(ids, documents, metadatas, distances):
            hits.append({
                "chunk_id": chunk_id,
                "doc_id": meta.get("doc_id", ""),
                "title": meta.get("title") or meta.get("doc_id", ""),
                "section": meta.get("section_title", ""),
                "excerpt": excerpt(text),
                "text": text,
                "url": meta.get("url", ""),
                "similarity": to_similarity(dist),
            })
        return hits

    def get_chunk(self, chunk_id: str) -> dict | None:
        """출처 문서 상세 모달이 쓰는 조회."""
        result = self.collection.get(ids=[chunk_id], include=["documents", "metadatas"])
        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []
        if not documents:
            return None
        meta = metadatas[0]
        return {
            "doc_id": meta.get("doc_id", ""),
            "title": meta.get("title") or meta.get("doc_id", ""),
            "section": meta.get("section_title", ""),
            "text": documents[0],
            "url": meta.get("url", ""),
        }
