"""팩을 색인한다 — 문서 청크와 검수 QA (개발계획서 §3.5).

    python scripts/pack_index.py packs/mcp-manager

문서를 넣거나 QA 를 검수한 뒤, 또는 팩을 갈아끼운 뒤에 돌린다. 이걸 안 돌리면
파일은 바뀌었는데 검색은 옛 벡터를 본다 — **화면상 아무 일도 안 일어난 것처럼 보이는**
종류의 문제라 눈치채기 어렵다.

`POST /api/admin/qa/reindex?include_docs=true` 와 같은 일을 한다. 서버를 띄우지 않고
반입 절차 안에서 돌릴 수 있도록 스크립트로도 둔다.

**색인 전에 검사한다.** 오류가 있는 팩을 색인하면 반쯤 들어간 인덱스가 남는다.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    if len(sys.argv) < 2:
        print("사용법: python scripts/pack_index.py <팩 경로> [var 경로]")
        return 2
    pack_dir = Path(sys.argv[1])
    if not pack_dir.is_dir():
        print(f"팩 경로가 없습니다: {pack_dir}")
        return 2

    # 벡터 저장소는 var 에 쌓인다. 안 주면 팩 이름으로 기본 자리를 잡는다 —
    # 팩과 같은 곳에 두면 형상관리에 50MB 짜리 파생물이 딸려 들어간다.
    var_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "var" / pack_dir.name

    # 설정을 읽기 **전에** 환경을 세운다. get_settings 는 lru_cache 라 한 번 읽으면 굳는다.
    os.environ["PACK_DIR"] = str(pack_dir)
    os.environ["VAR_DIR"] = str(var_dir)

    from scripts.pack_validate import Report, check_categories, check_docs, check_manifest, check_qa

    report = Report()
    check_manifest(pack_dir, report)
    ids = check_categories(pack_dir, report)
    check_qa(pack_dir, ids, report)
    check_docs(pack_dir, report)
    if report.errors:
        # 반쯤 들어간 인덱스를 남기지 않는다.
        report.print(pack_dir)
        print("  오류가 있어 색인하지 않았습니다.")
        return 1

    from app.ingestion.doc_index import DocIndex   # noqa: E402
    from app.qa.index import QaIndex               # noqa: E402

    print(f"색인 — 팩 {pack_dir} · var {var_dir}")

    # 모델 불일치 검사를 끄고 연다. 임베딩 모델을 바꾼 뒤 그 상태를 푸는 방법이 바로
    # 이 재색인인데, 검사를 그대로 두면 "재색인하세요" 라면서 재색인은 못 하게 된다.
    docs = DocIndex(check_model=False).rebuild()
    chunks = sum(docs.values()) if isinstance(docs, dict) else 0
    print(f"  문서 {len(docs) if isinstance(docs, dict) else 0}건 · 청크 {chunks}개")

    qa = QaIndex(check_model=False).rebuild()
    print(f"  QA  {qa}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
