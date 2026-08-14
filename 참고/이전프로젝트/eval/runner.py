"""평가 실행 서비스 — 질문 생성 · 골든셋 관리 · 평가 배치.

`scripts/run_eval.py` 가 하던 일을 API에서도 쓸 수 있게 옮겨 담았다.
오래 걸리는 작업이라 진행 상태를 따로 들고 있고, 화면이 폴링해서 읽는다.
"""

import io
import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger, log_event
from app.eval.golden_set import GoldenItem, load_golden_set
from app.eval.llm_judge import average_score, judge_answers
from app.eval.question_gen import GeneratedItem, generate_questions
from app.eval.retrieval_metrics import evaluate_retrieval
from app.ingestion.loader import VectorStoreLoader
from app.pipeline.rag import RagPipeline

logger = get_logger("eval.runner")

_LOCK = threading.Lock()


@dataclass
class EvalProgress:
    running: bool = False
    stage: str = ""
    percent: int = 0
    error: str = ""

    def snapshot(self) -> dict:
        return {"running": self.running, "stage": self.stage, "percent": self.percent, "error": self.error}


_progress = EvalProgress()

# 백그라운드 생성이 끝난 뒤 화면이 결과(질문 목록)를 가져갈 수 있도록 마지막 실행 결과를 들고 있다.
# 파일로 남기지 않는 이유: 골든셋에 이미 저장되며, 이 값은 "방금 만든 것"만 쓰는 일회성 데이터다.
_last_generation: dict = {"questions": [], "added_to_golden_set": 0, "generated_at": ""}


def get_progress() -> dict:
    return _progress.snapshot()


def get_last_generation() -> dict:
    return _last_generation


def _report_path() -> Path:
    return Path("data/eval_report.json")


def load_report() -> dict:
    path = _report_path()
    if not path.exists():
        return {"run_at": None, "num_questions": 0, "recall_at_5": None, "mrr": None,
                "llm_judge_avg": None, "details": []}
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"run_at": None, "num_questions": 0, "details": []}


# ───────────────────────────────────────────────────────────── 골든셋 쓰기


def append_to_golden_set(items: list[GeneratedItem]) -> int:
    """생성한 문항을 골든셋에 추가한다. 이미 있는 질문은 건너뛴다."""
    if not items:
        return 0
    path = Path(get_settings().golden_set_file)
    existing = {item.question for item in load_golden_set()} if path.exists() else set()

    added = 0
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with io.open(path, "a", encoding="utf-8") as f:
            for item in items:
                if item.question in existing:
                    continue
                f.write(json.dumps(item.to_row(), ensure_ascii=False) + "\n")
                existing.add(item.question)
                added += 1
    log_event(logger, "golden set extended", added=added, requested=len(items))
    return added


def remove_generated_from_golden_set() -> int:
    """자동 생성 문항만 걷어낸다(사람이 쓴 문항은 남긴다)."""
    path = Path(get_settings().golden_set_file)
    if not path.exists():
        return 0
    with _LOCK, io.open(path, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    kept = [r for r in rows if not r.get("generated")]
    with _LOCK, io.open(path, "w", encoding="utf-8") as f:
        for row in kept:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    removed = len(rows) - len(kept)
    log_event(logger, "generated golden items removed", removed=removed)
    return removed


def golden_set_summary() -> dict:
    path = Path(get_settings().golden_set_file)
    if not path.exists():
        return {"total": 0, "generated": 0, "handwritten": 0, "confusion": 0}
    with io.open(path, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    generated = sum(1 for r in rows if r.get("generated"))
    return {
        "total": len(rows),
        "generated": generated,
        "handwritten": len(rows) - generated,
        "confusion": sum(1 for r in rows if r.get("is_confusion_test")),
    }


# ─────────────────────────────────────────────────────────────── 배치 실행


def run_generation(count: int, model: str | None, unanswerable_ratio: float, append: bool) -> dict:
    _progress.running = True
    _progress.error = ""
    try:
        def on_progress(done: int, total: int, stage: str) -> None:
            _progress.stage = stage
            _progress.percent = int(done / max(1, total) * 100)

        items = generate_questions(
            count=count, model=model, unanswerable_ratio=unanswerable_ratio, progress=on_progress,
        )
        added = append_to_golden_set(items) if append else 0
        rows = [item.to_row() for item in items]
        _last_generation.update({
            "questions": rows,
            "added_to_golden_set": added,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })
        return {
            "generated": rows,
            "added_to_golden_set": added,
            "golden_set": golden_set_summary(),
        }
    except Exception as exc:  # noqa: BLE001 — 배치 실패가 서버를 죽이면 안 된다
        _progress.error = str(exc)
        log_event(logger, "question generation failed", error=str(exc))
        raise
    finally:
        _progress.running = False


def run_evaluation(answer_model: str | None, judge_model: str | None, limit: int | None = None) -> dict:
    """골든셋으로 검색 정확도와 답변 품질을 측정하고 리포트를 저장한다."""
    settings = get_settings()
    _progress.running = True
    _progress.error = ""
    try:
        items: list[GoldenItem] = load_golden_set()
        if limit:
            items = items[:limit]
        if not items:
            raise ValueError("골든셋이 비어 있습니다. 먼저 질문을 생성하거나 문항을 추가하세요.")

        _progress.stage = "검색 정확도 측정 중…"
        _progress.percent = 5
        vector_store = VectorStoreLoader()
        retrieval = evaluate_retrieval(items, vector_store, top_k=settings.rag_top_k)

        def on_progress(done: int, total: int, stage: str) -> None:
            _progress.stage = stage
            # 검색 측정이 앞의 10%, 답변·채점이 나머지 90%를 차지한다.
            _progress.percent = 10 + int(done / max(1, total) * 90)

        rag_pipeline = RagPipeline(vector_store=vector_store)
        judged = judge_answers(
            items, rag_pipeline=rag_pipeline,
            answer_model=answer_model, judge_model=judge_model, progress=on_progress,
        )

        report = {
            "run_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "num_questions": len(items),
            "recall_at_5": retrieval.recall_at_5,
            "mrr": retrieval.mrr,
            "llm_judge_avg": average_score(judged),
            "answer_model": answer_model or settings.ollama_llm_model,
            "judge_model": judge_model or settings.ollama_llm_model,
            "details": [
                {**rq, "judge_score": jr.score, "judge_reason": jr.reason}
                for rq, jr in zip(retrieval.per_question, judged)
            ],
        }
        path = _report_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with io.open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        _progress.stage = "완료"
        _progress.percent = 100
        log_event(
            logger, "evaluation finished",
            questions=len(items), recall=retrieval.recall_at_5, judge=report["llm_judge_avg"],
        )
        return report
    except Exception as exc:  # noqa: BLE001
        _progress.error = str(exc)
        log_event(logger, "evaluation failed", error=str(exc))
        raise
    finally:
        _progress.running = False
