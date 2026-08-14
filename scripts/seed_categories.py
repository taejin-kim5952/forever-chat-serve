"""퍼블 산출물의 카테고리 더미를 `data/categories.json` 으로 옮긴다.

퍼블이 대분류 5 / 카테고리 48 을 실제 업무 용어로 채워줬다. 이걸 다시 손으로 옮겨 적으면
오타가 나고 화면과 서버가 어긋난다. 한 번 변환해 두고, 이후 수정은 관리자 화면에서 한다.

한 번만 쓰는 스크립트다. `data/categories.json` 이 이미 있으면 덮어쓰지 않는다.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "퍼블" / "chat.js"
TARGET = ROOT / "data" / "categories.json"


def js_object_to_json(js: str):
    """JS 객체 리터럴 → JSON. 따옴표 없는 키와 홑따옴표, 후행 쉼표만 처리하면 된다."""
    js = re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', js)
    js = js.replace("'", '"')
    js = re.sub(r",(\s*[}\]])", r"\1", js)
    return json.loads(js)


def main() -> int:
    if not SOURCE.exists():
        print(f"퍼블 산출물을 찾을 수 없습니다: {SOURCE}")
        return 1
    if TARGET.exists() and "--force" not in sys.argv:
        print(f"{TARGET} 가 이미 있습니다. 덮어쓰려면 --force 를 주세요.")
        return 0

    src = SOURCE.read_text(encoding="utf-8")
    block = src[src.index("var CATEGORY_GROUPS"): src.index("var QUICK_CATEGORY_IDS")]
    groups = js_object_to_json(block[block.index("["): block.rindex("]") + 1])

    quick_src = src[src.index("var QUICK_CATEGORY_IDS"):]
    quick_ids = js_object_to_json(quick_src[quick_src.index("["): quick_src.index("]") + 1])

    # 퍼블 산출물이 두 벌 있고 필드 이름이 다르다(`group_label`/`id`/`label` ↔
    # `group_name`/`category_id`/`name`). 어느 쪽이 오든 서버 모델 이름으로 맞춘다.
    for group_sort, group in enumerate(groups):
        group["group_name"] = group.get("group_name") or group.pop("group_label", "")
        group.pop("group_label", None)
        group["sort"] = group_sort
        group["enabled"] = True
        for cat_sort, category in enumerate(group["categories"]):
            category["category_id"] = category.get("category_id") or category.pop("id", "")
            category["name"] = category.get("name") or category.pop("label", "")
            category.pop("id", None)
            category.pop("label", None)
            category["group_id"] = group["group_id"]
            category["sort"] = cat_sort
            category["enabled"] = True
            category.setdefault("questions", [])

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(
        json.dumps({"groups": groups, "quick_category_ids": quick_ids}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    total = sum(len(g["categories"]) for g in groups)
    print(f"저장했습니다: 대분류 {len(groups)} / 카테고리 {total} / 자주 찾는 주제 {len(quick_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
