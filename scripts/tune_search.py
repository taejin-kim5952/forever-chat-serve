"""검색 기준값을 **실측으로** 정한다 (studio 전용 도구).

### 왜 필요한가

기준값(`qa_match_threshold` 등)을 눈대중으로 올리고 내리면, 좋아졌는지 나빠졌는지 말할 수가
없다. 특히 **답하지 말아야 할 때 답하는** 경우는 사용자가 알려 주지 않으면 영영 안 보인다 —
틀린 답을 자신 있게 내놓는 쪽이 못 찾는 쪽보다 나쁜데도 그렇다.

이 도구는 질문 목록 하나로 세 가지를 동시에 센다.

    맞음    기대한 그 답변이 나갔다
    오매칭  **다른** 답변이 나갔다        ← 가장 나쁘다
    놓침    답변이 있는데 안 나갔다
    샘      답하지 말아야 할 질문에 뭔가 나갔다

### 쓰는 법

    python scripts/tune_search.py --project api-manager --init    # 질문 이력에서 초안 만들기
    (packs/<project>/eval_questions.json 을 손으로 고친다)
    python scripts/tune_search.py --project api-manager           # 지금 설정 채점
    python scripts/tune_search.py --project api-manager --sweep   # 기준값 조합 비교

### 기준값은 코퍼스마다 다르다

BM25 점수는 문서 수·길이에 따라 분포가 바뀐다. **자료를 크게 바꾸면 다시 재야 한다.**
남의 설치에서 쓰던 숫자를 그대로 가져오면 안 된다.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import config  # noqa: E402
from app.core.runtime_config import load_runtime_config  # noqa: E402
from app.ingestion.lexical import Bm25Index, rrf  # noqa: E402
from app.pipeline.retrieve import get_retriever  # noqa: E402
from app.qa import store as qa_store  # noqa: E402

EXPECTS = ("answer", "docs", "none")

# 이력에 섞인 시험·깨진 질문. 측정에 넣으면 숫자가 흐려진다.
_JUNK = ("로그 확인용", "워밍업", "테스트 접수", "???", "??")


def eval_path(project: str) -> Path:
    return Path(config.settings_for(project).pack_dir if project else config.get_settings().pack_dir) / "eval_questions.json"


def init_from_log(project: str) -> Path:
    """질문 이력에서 측정 세트 초안을 만든다.

    **지금 동작을 그대로 적어 둔다.** 그대로 두면 "아무것도 바꾸지 말라"는 뜻이 되므로,
    사람이 틀린 줄을 고치는 것이 이 파일의 핵심이다. 고친 줄은 `reviewed: true` 로 둔다.
    """
    log = Path(config.get_settings().question_log_file)
    # 이력의 `matched_qa_id` 는 **그때의** QA 를 가리킨다. 그 뒤 QA 를 다시 만들었으면
    # 그 id 는 사라지고, 비워 두지 않으면 멀쩡한 답변이 전부 '오매칭' 으로 집계된다
    # (2026-10-06 에 8건이 그렇게 잡혔다).
    alive = {i.qa_id for i in qa_store.load_qa() if i.status in qa_store.SERVING_STATUSES}
    rows, seen = [], set()
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            question = (entry.get("question") or "").strip()
            if not question or question in seen or any(j in question for j in _JUNK):
                continue
            seen.add(question)
            result = entry.get("result_type") or "unresolved"
            qa_id = entry.get("matched_qa_id") or ""
            stale = bool(qa_id) and qa_id not in alive
            rows.append({
                "question": question,
                "expect": {"answer": "answer", "live_answer": "answer",
                           "related_docs": "docs"}.get(result, "none"),
                "qa_id": "" if stale else qa_id,
                "reviewed": False,
                "note": "그때 걸린 QA 가 지금 없습니다 — 어느 답변이 맞는지 적어 주세요" if stale else "",
            })

    target = eval_path(project)
    target.write_text(
        json.dumps({"questions": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return target


def load_set(project: str) -> list[dict]:
    path = eval_path(project)
    if not path.exists():
        raise SystemExit(f"측정 세트가 없습니다: {path}\n  --init 으로 질문 이력에서 초안을 만드세요.")
    rows = json.loads(path.read_text(encoding="utf-8")).get("questions", [])
    bad = [r["question"] for r in rows if r.get("expect") not in EXPECTS]
    if bad:
        raise SystemExit("expect 값이 잘못된 질문: " + ", ".join(bad[:5]))
    return rows


def build_lexical() -> tuple[Bm25Index, dict[str, str]]:
    """승인된 QA 한 건을 **대표 질문 + 변형 질문을 합친 한 덩이**로 색인한다.

    벡터 인덱스는 변형마다 한 줄이지만 낱말 쪽은 합치는 편이 낫다. 변형 하나하나는 너무
    짧아 BM25 의 길이 보정이 과하게 걸리고, 어차피 어느 변형에 걸렸는지는 쓰지 않는다.
    """
    items = [i for i in qa_store.load_qa() if i.status in qa_store.SERVING_STATUSES]
    docs = {i.qa_id: " ".join([i.question, *i.variants]) for i in items}
    titles = {i.qa_id: i.question for i in items}
    return Bm25Index(docs), titles


def measure(rows: list[dict], top_k: int = 10) -> list[dict]:
    """질문마다 벡터·낱말 점수를 **한 번만** 계산해 둔다. 조합을 바꿔 가며 다시 쓴다."""
    retriever = get_retriever()
    lexical, _ = build_lexical()
    runtime = load_runtime_config()

    out = []
    for row in rows:
        question = row["question"]
        vector, qa_hits = retriever.qa_index.search(question, top_k)
        lex_hits = lexical.search(question, top_k)
        doc_hits = retriever.doc_index.search_by_vector(vector, runtime.doc_top_k)
        out.append({
            **row,
            "vec": [(h["qa_id"], h["similarity"]) for h in qa_hits],
            "lex": lex_hits,
            "doc_top": doc_hits[0]["similarity"] if doc_hits else 0.0,
        })
    return out


def decide(case: dict, qa_th: float, lex_min: float, soft: float, docs_floor: float) -> tuple[str, str]:
    """한 질문의 결과를 정한다. `(result_type, qa_id)`.

    통과 규칙은 **둘 다 어느 정도**다 — 낱말만으로 통과시키면 `연차 신청 어떻게 해` 가
    `서비스 권한은 어떻게 신청하나요?` 와 '신청' 으로 겹쳐 엉뚱한 검수 답변이 나간다
    (2026-10-06 측정). 벡터가 확실하면 낱말은 보지 않는다.
    """
    vec = dict(case["vec"])
    lex = dict(case["lex"])

    if lex_min > 0:
        order = rrf([[qa_id for qa_id, _ in case["vec"]], [qa_id for qa_id, _ in case["lex"]]])
    else:
        # 낱말을 끈 비교 기준(= 지금 동작)은 **벡터 순위 그대로** 봐야 한다. 순위만
        # 섞어 놓고 '지금' 이라고 부르면 비교가 성립하지 않는다.
        order = {qa_id: 1.0 / rank for rank, (qa_id, _) in enumerate(case["vec"], start=1)}
    if order:
        best = max(order, key=lambda qa_id: (order[qa_id], vec.get(qa_id, 0.0)))
        v, l = vec.get(best, 0.0), lex.get(best, 0.0)
        if v >= qa_th or (lex_min > 0 and v >= soft and l >= lex_min):
            return "answer", best

    return ("docs" if case["doc_top"] >= docs_floor else "none"), ""


def score(cases: list[dict], **thresholds) -> dict:
    tally = {"맞음": 0, "오매칭": 0, "놓침": 0, "자료맞음": 0, "자료놓침": 0, "막음": 0, "샘": 0}
    misses = []
    for case in cases:
        result, qa_id = decide(case, **thresholds)
        want = case["expect"]
        if want == "answer":
            if result != "answer":
                tally["놓침"] += 1
                misses.append(("놓침", case["question"], ""))
            elif case.get("qa_id") and qa_id != case["qa_id"]:
                tally["오매칭"] += 1
                misses.append(("오매칭", case["question"], qa_id))
            else:
                tally["맞음"] += 1
        elif want == "docs":
            if result == "answer":
                tally["오매칭"] += 1
                misses.append(("오매칭", case["question"], qa_id))
            elif result == "docs":
                tally["자료맞음"] += 1
            else:
                tally["자료놓침"] += 1
                misses.append(("자료놓침", case["question"], ""))
        else:
            if result == "none":
                tally["막음"] += 1
            else:
                tally["샘"] += 1
                misses.append(("샘", case["question"], qa_id or result))
    tally["_misses"] = misses
    return tally


def line(label: str, tally: dict) -> str:
    return (f"{label:30s} 맞음 {tally['맞음']:3d} · 오매칭 {tally['오매칭']:3d} · 놓침 {tally['놓침']:3d}"
            f" | 자료 {tally['자료맞음']:3d}/{tally['자료맞음'] + tally['자료놓침']:3d}"
            f" | 무관 막음 {tally['막음']:3d} · 샘 {tally['샘']:3d}")


def main() -> int:
    parser = argparse.ArgumentParser(description="검색 기준값을 실측으로 정한다")
    parser.add_argument("--project", default="", help="프로젝트 id (비우면 기본 팩)")
    parser.add_argument("--init", action="store_true", help="질문 이력에서 측정 세트 초안 만들기")
    parser.add_argument("--sweep", action="store_true", help="기준값 조합 비교")
    args = parser.parse_args()

    token = config.use_project(args.project) if args.project else None
    try:
        if args.init:
            print(f"측정 세트를 만들었습니다: {init_from_log(args.project)}")
            print("  expect 를 손으로 고치세요: answer(그 답변이 나가야 함) · docs(자료만) · none(답하면 안 됨)")
            return 0

        rows = load_set(args.project)
        unreviewed = sum(1 for r in rows if not r.get("reviewed"))
        cases = measure(rows)
        runtime = load_runtime_config()
        print(f"질문 {len(rows)}건 (손으로 확인 안 한 것 {unreviewed}건) · "
              f"QA {len(build_lexical()[0])}건\n")

        base = dict(qa_th=runtime.qa_match_threshold, lex_min=0.0, soft=0.0,
                    docs_floor=runtime.related_docs_floor)
        now = score(cases, **base)
        print(line(f"지금 (벡터만, {runtime.qa_match_threshold})", now))

        if not args.sweep:
            for kind, question, extra in now["_misses"][:20]:
                print(f"   {kind:6s} {question[:46]:48s} {extra}")
            return 0

        print()
        best = None
        for qa_th in (0.88, 0.90, 0.92):
            for soft in (0.80, 0.84, 0.86):
                for lex_min in (3.0, 5.0, 8.0, 12.0):
                    combo = dict(qa_th=qa_th, lex_min=lex_min, soft=soft,
                                 docs_floor=runtime.related_docs_floor)
                    tally = score(cases, **combo)
                    print(line(f"vec {qa_th} · soft {soft} · lex {lex_min}", tally))
                    # 오매칭과 샘이 먼저다. 틀린 답을 내놓는 쪽이 못 찾는 쪽보다 나쁘다.
                    key = (-(tally["오매칭"] + tally["샘"]), tally["맞음"] + tally["자료맞음"])
                    if best is None or key > best[0]:
                        best = (key, combo, tally)
        print("\n가장 나은 조합:")
        print(line(f"vec {best[1]['qa_th']} · soft {best[1]['soft']} · lex {best[1]['lex_min']}", best[2]))
        return 0
    finally:
        if token is not None:
            config.reset_project(token)


if __name__ == "__main__":
    raise SystemExit(main())
