"""빈 팩 골격을 만든다 (개발계획서 §3.5).

    python scripts/pack_new.py mcp-manager

만드는 것은 **뼈대뿐**이다. 문서와 카테고리는 사람이 채운다 — 그게 팩 작업의 8할이고,
도구가 대신할 수 있는 부분이 아니다.

이미 있는 팩은 덮지 않는다. 며칠 걸려 모은 문서를 한 번의 오타로 날리는 일이 없어야 한다.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.pack import ENGINE_VERSION   # noqa: E402

MANIFEST = {
    "pack_id": "",
    "pack_version": "0.1.0",
    "engine_min_version": ENGINE_VERSION,
    "profile": {
        "organization": "조직명",
        "service_name": "서비스 도우미",
        "service_desc": "한 줄 소개",
        "domain_intro": "무엇에 대한 가이드인지 (명사구 — 뒤에 '를' 이 붙는다)",
        "language": "ko",
    },
    # 도메인마다 유사도 분포가 다르다. 평가 뒤에 정하고, 그 전에는 코드 기본값을 쓴다.
    "matching": {},
    "routes": {"related_docs": True, "unresolved_ticket": True},
    "copy": {},
}

CATEGORIES = {
    "groups": [
        {
            "group_id": "start",
            "group_name": "시작하기",
            "sort": 0,
            "enabled": True,
            "categories": [
                {
                    "category_id": "start_basic",
                    "group_id": "start",
                    "name": "기본 개념",
                    "sort": 0,
                    "enabled": True,
                    "questions": [],
                }
            ],
        }
    ],
    "quick_category_ids": [],
}

README = """# {pack_id}

이 팩이 무엇을 아는가 · 문서 출처 · 갱신 담당을 적습니다.

## 담기는 것

| 파일 | 누가 만드나 |
| --- | --- |
| `pack.json` | 사람 |
| `categories.json` | 사람 |
| `raw_docs/*.md` | 사람 (+ 자동 생성분) |
| `qa_index.json` | 생성 → **사람 검수** |

## 순서

```
1. pack.json 의 profile 채우기
2. raw_docs/ 에 마크다운 넣기          ← 여기가 전부입니다
3. categories.json 작성
4. python scripts/pack_validate.py packs/{pack_id}
5. python scripts/pack_index.py  packs/{pack_id}
6. APP_MODE=studio 로 QA 생성 → 검수 → approved
7. 평가로 임계값 결정 → pack.json 의 matching 에 적기
```
"""


def main() -> int:
    if len(sys.argv) < 2:
        print("사용법: python scripts/pack_new.py <pack_id>")
        return 2
    pack_id = sys.argv[1].strip()
    if not pack_id:
        print("pack_id 가 비었습니다.")
        return 2

    pack_dir = ROOT / "packs" / pack_id
    if pack_dir.exists():
        # 며칠 걸려 모은 문서를 오타 한 번으로 덮지 않는다.
        print(f"이미 있습니다: {pack_dir}")
        return 1

    (pack_dir / "raw_docs").mkdir(parents=True)

    manifest = dict(MANIFEST)
    manifest["pack_id"] = pack_id
    (pack_dir / "pack.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (pack_dir / "categories.json").write_text(
        json.dumps(CATEGORIES, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (pack_dir / "README.md").write_text(README.format(pack_id=pack_id), encoding="utf-8")

    print(f"만들었습니다: {pack_dir}")
    print()
    print("  다음:")
    print(f"    1. {pack_dir / 'pack.json'} 의 profile 을 채우세요")
    print(f"    2. {pack_dir / 'raw_docs'} 에 문서를 넣으세요")
    print(f"    3. python scripts/pack_validate.py packs/{pack_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
