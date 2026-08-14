from dataclasses import dataclass

from app.eval.golden_set import GoldenItem
from app.ingestion.loader import VectorStoreLoader


@dataclass
class RetrievalEvalResult:
    recall_at_5: float
    mrr: float
    per_question: list[dict]


def evaluate_retrieval(items: list[GoldenItem], vector_store: VectorStoreLoader, top_k: int = 5) -> RetrievalEvalResult:
    hits_at_5 = 0
    reciprocal_ranks: list[float] = []
    per_question: list[dict] = []

    for item in items:
        results = vector_store.query(item.question, top_k=top_k)
        doc_ids = [r["metadata"].get("doc_id") for r in results]

        rank = None
        for idx, doc_id in enumerate(doc_ids, start=1):
            if doc_id == item.expected_source:
                rank = idx
                break

        hit = rank is not None
        hits_at_5 += int(hit)
        reciprocal_ranks.append(1.0 / rank if rank else 0.0)
        per_question.append(
            {
                "question": item.question,
                "expected_source": item.expected_source,
                "retrieved": doc_ids,
                "hit": hit,
                "rank": rank,
            }
        )

    n = len(items) or 1
    return RetrievalEvalResult(
        recall_at_5=hits_at_5 / n,
        mrr=sum(reciprocal_ranks) / n,
        per_question=per_question,
    )
