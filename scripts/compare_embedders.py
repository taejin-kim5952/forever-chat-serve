"""임베딩 모델 비교 — 우리 문서로 직접 재고 고른다.

**벤치마크 순위를 믿지 마세요.** 이 프로젝트에서 두 번 뒤집혔습니다. 1차에서는 MTEB 상위인
`qwen3-embedding` 이 `embeddinggemma` 에 졌고, 2026-08-17 측정에서도 MTEB 1위(64.34)인
`qwen3-embedding` 이 우리 문서에서는 꼴찌였습니다(인수인계 문서 8-2).

### 무엇을 재는가

"질문을 던졌을 때 **그 질문이 나온 청크**가 상위에 오는가" 입니다. 청크에서 질문을 만들었으니
그 청크가 곧 정답이고, 사람이 라벨을 붙일 필요가 없습니다.

| 지표 | 뜻 |
| --- | --- |
| Recall@1 | 1등이 정답 청크인 비율 — 사용자가 실제로 보는 것 |
| Recall@3 | 상위 3등 안에 있는 비율 — 관련 문서 카드가 3개라 화면과 맞습니다 |
| MRR | 정답이 몇 등이었는지를 `1/등수` 로 평균 |

### 문항은 고정본을 씁니다 ★

`scripts/embed_bench_questions.json` 에 문항을 넣어 두고 모든 모델이 **같은 문항**으로 겨룹니다.
매번 새로 만들면 어제 숫자와 비교할 수 없습니다.

다만 고정본만 보고 고르면 그 문항에 맞춘 모델을 고르게 됩니다(과적합). 실제 결정은
**고정본(회귀 확인) + 새 문항(`--make`, 일반화 확인) + 실사용 로그**를 함께 보고 하세요.

### 실행

```bash
python scripts/compare_embedders.py                              # 지금 쓰는 모델로 재기
python scripts/compare_embedders.py --models models/bge-m3-onnx models/다른-모델
python scripts/compare_embedders.py --make 120                   # 문항 새로 만들기(studio 필요)
```

**후보는 모델 폴더 경로**입니다. 앱이 ONNX 로만 임베딩하므로(`app/ingestion/embedder.py`),
비교도 같은 방식으로 해야 그 숫자가 운영에 그대로 옮겨집니다. 다른 모델을 재보려면
그 모델의 ONNX 변환본을 폴더에 준비하세요(`model.onnx` + `tokenizer.json`).

**실제 `data/chroma/` 는 건드리지 않습니다.** 모델마다 임시 폴더에 따로 색인합니다
(차원이 다른 벡터가 한 컬렉션에 섞이면 안 됩니다).

로컬 GPU에 큰 모델이 올라와 있으면 임베딩 모델 로드가 실패할 수 있습니다. 모델을 하나씩
내리며 돌리므로 대개 괜찮지만, 실패하면 `ollama ps` 로 확인하고 `ollama stop <모델>` 하세요.
"""

import argparse
import json
import os
import random
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

QUESTION_FILE = Path(__file__).with_name("embed_bench_questions.json")
DEFAULT_MODELS = [str(ROOT / "models" / "bge-m3-onnx")]
# 문항을 만들 때 쓰는 모델. 임베딩 비교와는 무관하지만 고정해 두어야 다시 만들 때 결이 같다.
QUESTION_MODEL = "gemma4:latest"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="임베딩 모델을 우리 문서로 비교합니다.")
    parser.add_argument("--models", nargs="*", default=DEFAULT_MODELS,
                        help="비교할 임베딩 모델 폴더(model.onnx + tokenizer.json 이 든 곳)")
    parser.add_argument("--make", type=int, metavar="N",
                        help="문항을 N개 새로 만들어 고정본을 덮어씁니다(studio 필요)")
    parser.add_argument("--top-k", type=int, default=5, help="검색 상위 몇 건까지 볼지")
    return parser.parse_args()


# ─────────────────────────────────────────────────────────── 문항 만들기


def make_questions(count: int) -> list[dict]:
    """청크에서 질문을 만들고 '그 청크'를 정답으로 기록한다.

    문서 문장을 그대로 쓰면 검색이 너무 쉬워져 모델 차이가 안 보인다. 그래서 실제 생성에 쓰는
    프롬프트를 그대로 써서 **사용자 말투로 바꾼 질문**을 만든다.
    """
    from app.core.config import is_studio
    from app.studio.generate import _QUESTION_PROMPT, _load_chunks, _parse_line_items, qa_rules
    from app.studio.korean import is_korean
    from app.studio.llm import StudioLlm

    if not is_studio():
        print("APP_MODE 가 studio 가 아닙니다. 문항 생성은 스튜디오 PC에서만 합니다.")
        raise SystemExit(1)

    llm, rules = StudioLlm(model=QUESTION_MODEL), qa_rules()
    chunks = _load_chunks([])
    if not chunks:
        print("문서가 없습니다. data/raw_docs/ 를 확인하세요.")
        raise SystemExit(1)

    # 씨앗을 고정한다 — 문항을 다시 만들 때 같은 청크에서 뽑아야 결과를 견줄 수 있다.
    random.seed(20260817)
    picked = random.sample(chunks, min(count, len(chunks)))
    print(f"청크 {len(chunks)}개 중 {len(picked)}개로 문항을 만듭니다 (모델 {QUESTION_MODEL}).")

    items: list[dict] = []
    for n, chunk in enumerate(picked, 1):
        meta = chunk["meta"]
        context = llm.fit(f"[{meta.get('title')} - {meta.get('section_title')}]\n{chunk['text']}")
        try:
            raw = llm.chat(_QUESTION_PROMPT.format(context=context, count=1), system=rules)
        except Exception as exc:  # noqa: BLE001 — 한 건 실패해도 나머지는 계속
            print(f"  [{n}/{len(picked)}] 실패: {exc}")
            continue
        questions = [q for q in _parse_line_items(raw)[:1] if is_korean(q)]
        if not questions:
            continue
        items.append({
            "question": questions[0],
            "chunk_id": f"{meta['doc_id']}::{meta['chunk_index']}",
            "doc_id": meta["doc_id"],
            "section": meta.get("section_title", ""),
        })
        print(f"  [{n}/{len(picked)}] {questions[0][:56]}", flush=True)

    QUESTION_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n문항 {len(items)}개 → {QUESTION_FILE.name}")
    return items


# ─────────────────────────────────────────────────────────── 측정


def measure(model: str, questions: list[dict], top_k: int) -> dict:
    store = Path(tempfile.mkdtemp(prefix="embed_bench_"))
    try:
        # 설정은 기동할 때 고정되므로(@lru_cache) 캐시를 비우고 다시 읽게 한다.
        os.environ["CHROMA_PERSIST_DIR"] = str(store)
        os.environ["EMBED_ONNX_DIR"] = model

        from app.core.config import get_settings
        get_settings.cache_clear()
        from app.ingestion import embedder as embedder_module
        from app.ingestion import vector_store
        vector_store.reset_client()
        embedder_module.reset_session()      # 모델이 바뀌므로 세션을 새로 만든다
        from app.ingestion.doc_index import DocIndex

        index = DocIndex(check_model=False)
        started = time.time()
        chunks = sum(index.ingest_dir(force=True).values())
        index_seconds = time.time() - started

        hit1 = hit3 = 0
        reciprocal = 0.0
        started = time.time()
        for item in questions:
            hits = index.search(item["question"], top_k=top_k)
            ids = [h["chunk_id"] for h in hits]
            rank = ids.index(item["chunk_id"]) + 1 if item["chunk_id"] in ids else 0
            hit1 += 1 if rank == 1 else 0
            hit3 += 1 if 1 <= rank <= 3 else 0
            reciprocal += (1 / rank) if rank else 0
        search_seconds = time.time() - started

        total = len(questions)
        return {
            "model": Path(model).name,
            "dim": len(index.embedder.embed("차원 확인", task="query")),
            "chunks": chunks,
            "recall1": round(hit1 / total * 100, 1),
            "recall3": round(hit3 / total * 100, 1),
            "mrr": round(reciprocal / total, 3),
            "index_sec": round(index_seconds, 1),
            "search_ms": round(search_seconds / total * 1000),
        }
    finally:
        shutil.rmtree(store, ignore_errors=True)


def main() -> int:
    args = _parse_args()

    if args.make:
        questions = make_questions(args.make)
    elif QUESTION_FILE.exists():
        questions = json.loads(QUESTION_FILE.read_text(encoding="utf-8"))
    else:
        print(f"문항 파일이 없습니다: {QUESTION_FILE}")
        print("  python scripts/compare_embedders.py --make 40  으로 먼저 만드세요.")
        return 1

    if not questions:
        print("문항이 비어 있습니다.")
        return 1

    print(f"\n문항 {len(questions)}개 · 모델 {len(args.models)}개\n")
    rows = []
    for model in args.models:
        try:
            row = measure(model, questions, args.top_k)
        except Exception as exc:  # noqa: BLE001 — 한 모델이 실패해도 나머지는 잰다
            print(f"{model:26} 실패: {exc}")
            continue
        rows.append(row)
        print(f"{model:26} 차원 {row['dim']:5} · Recall@1 {row['recall1']:5}% · "
              f"Recall@3 {row['recall3']:5}% · MRR {row['mrr']:5} · "
              f"색인 {row['index_sec']:6}초 · 검색 {row['search_ms']:4}ms/건", flush=True)

    print("\n| 모델 | 차원 | Recall@1 | Recall@3 | MRR | 색인 | 검색 |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for row in rows:
        print(f"| `{row['model']}` | {row['dim']} | {row['recall1']}% | {row['recall3']}% | "
              f"{row['mrr']} | {row['index_sec']}초 | {row['search_ms']}ms |")
    print("\n결과를 인수인계 문서 8-2 에 남기세요. 남기지 않으면 다음 사람이 처음부터 다시 잽니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
