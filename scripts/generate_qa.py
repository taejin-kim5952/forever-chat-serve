"""문서에서 QA 초안을 만든다 — 스튜디오 배치.

관리자 화면(탭 ⑥)이 아직 없으므로 **지금은 이 스크립트가 유일한 실행 수단**이다.
화면이 오면 같은 함수를 `POST /api/studio/generate` 가 부른다(로직은 한 벌만 둔다).

    python scripts/generate_qa.py                          # 전체 문서, 미리보기만
    python scripts/generate_qa.py --docs api-등록 spc-등록   # 문서 지정
    python scripts/generate_qa.py --category api_reg_flow  # 추천 질문에 답 붙이기
    python scripts/generate_qa.py --max 10 --variants 12
    python scripts/generate_qa.py --apply                  # 초안을 pending 으로 반영

`--apply` 를 줘도 **`pending` 까지만** 들어간다. 승인은 사람이 검수 화면에서 한다.
Ctrl+C 로 멈추면 그때까지 만든 초안은 `data/generated_qa.json` 에 남는다.

**시간이 오래 걸린다.** 문서 5건이면 청크 50여 개 × (본문 1회 + 변형 1회) = 100회가 넘는
LLM 호출이다. 로컬 GPU에서 수십 분을 잡는다. 처음에는 `--max 3` 으로 결과 품질을 먼저 보는
편이 낫다 — 프롬프트가 안 맞으면 30분을 버린다.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.categories import find_category, load_categories   # noqa: E402
from app.core.config import get_settings, is_studio              # noqa: E402
from app.studio import runner                                    # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="문서에서 QA 초안을 생성합니다.")
    parser.add_argument("--docs", nargs="*", default=[], help="문서 ID 목록(비우면 전체)")
    parser.add_argument("--category", default=None, help="카테고리 ID — 추천 질문에 답변을 붙입니다")
    parser.add_argument("--model", default=None, help="질문·답변 모두 이 모델로(역할 분리 없이)")
    parser.add_argument("--question-model", default=None, help="질문·변형 질문 모델(기본: .env 의 OLLAMA_QUESTION_MODEL)")
    parser.add_argument("--answer-model", default=None, help="답변 모델(기본: .env 의 OLLAMA_ANSWER_MODEL)")
    parser.add_argument("--judge-model", default=None,
                        help="채점 모델(기본: .env 의 OLLAMA_JUDGE_MODEL). 비우면 채점하지 않습니다")
    parser.add_argument("--per-chunk", type=int, default=2, help="청크당 QA 개수")
    parser.add_argument("--variants", type=int, default=10, help="항목당 변형 질문 수")
    parser.add_argument("--max", type=int, default=50, help="최대 생성 항목 수")
    parser.add_argument("--apply", action="store_true", help="생성 결과를 pending 으로 QA 인덱스에 넣습니다")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    settings = get_settings()

    if not is_studio():
        # 운영 서버(GPU 없음)에서 실수로 돌리면 몇 시간이 걸리거나 그냥 실패한다.
        print("APP_MODE 가 studio 가 아닙니다. 생성은 스튜디오 PC에서만 실행합니다.")
        print("  .env 에 APP_MODE=studio 를 설정하세요.")
        return 1

    questions: list[str] = []
    source = "docs"
    if args.category:
        category = find_category(load_categories(), args.category)
        if not category:
            print(f"카테고리를 찾을 수 없습니다: {args.category}")
            return 1
        if not category.questions:
            print(f"'{category.name}' 에 등록된 추천 질문이 없습니다.")
            return 1
        source, questions = "category", category.questions
        print(f"대상: 카테고리 '{category.name}' 추천 질문 {len(questions)}건")
    else:
        print(f"대상: 문서 {', '.join(args.docs) if args.docs else '전체'}")

    # `--model` 은 두 역할을 같은 모델로 묶는 지름길이다(역할별 옵션이 있으면 그쪽이 이긴다).
    question_model = args.question_model or args.model
    answer_model = args.answer_model or args.model

    job = runner.get_job()
    progress = job.start(
        source=source,
        doc_ids=args.docs,
        questions=questions,
        category_id=args.category,
        question_model=question_model,
        answer_model=answer_model,
        judge_model=args.judge_model,
        items_per_chunk=args.per_chunk,
        variant_count=args.variants,
        max_items=args.max,
    )
    print(f"모델: {progress.model} · 변형 질문 {args.variants}개/건")
    print("Ctrl+C 로 중지할 수 있습니다. 그때까지 만든 초안은 남습니다.\n")

    try:
        while not job.join(timeout=2):
            progress = job.progress()
            print(f"  [{progress.percent:3d}%] {progress.stage}")
    except KeyboardInterrupt:
        print("\n중지 요청… 진행 중인 항목까지 마칩니다.")
        job.request_stop()
        job.join(timeout=300)

    progress = job.progress()
    if progress.status == "failed":
        print(f"\n실패: {progress.error}")
        return 1

    drafts = job.drafts()
    print(f"\n초안 {len(drafts)}건 ({progress.status}) → {settings.generated_qa_file}\n")
    for draft in drafts:
        score = f"[{draft.score}점] " if draft.score else ""
        print(f"- {score}{draft.question}  (변형 {len(draft.variants)}개 · 출처 {', '.join(draft.source_doc_ids)})")
        print(f"    {' '.join(draft.answer.split())[:100]}…")
        if draft.judge_reason:
            print(f"    채점: {draft.judge_reason}")

    if args.apply:
        result = runner.apply_drafts()
        low = f" · 점수 {result.min_score}점 미만 {result.low_score}건 제외" if result.min_score else ""
        print(f"\nQA 인덱스에 pending 으로 {result.saved}건 추가 (중복 제외 {result.skipped}건{low}).")
        print("관리자 화면(탭 ④)에서 검수해 승인하면 사용자에게 나갑니다.")
    elif drafts:
        print("\n반영하려면 --apply 를 주고 다시 실행하거나, 관리자 화면에서 선택해 추가하세요.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
