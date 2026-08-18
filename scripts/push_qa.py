"""스튜디오에서 만든 QA를 서버로 올린다 (화면 없이 쓰는 길).

관리자 화면의 `QA 가져오기`(요청서 11)와 **같은 API**를 부른다. 화면이 준비되기 전에도
QA를 쌓을 수 있게 하려고 만든 것이고, 폐쇄망에서 화면을 못 여는 상황에서도 쓸 수 있다.

    # 무엇이 어떻게 될지만 본다 (아무것도 바꾸지 않는다)
    python scripts/push_qa.py --server http://192.168.0.100:18100 --file data/generated_qa.json

    # 실제로 올린다
    python scripts/push_qa.py --server ... --file ... --apply

    # 이미 있는 항목도 덮는다 (적중 횟수·검수 메모는 서버 것이 유지된다)
    python scripts/push_qa.py --server ... --file ... --apply --overwrite

**미리보기가 기본**이다. `--apply` 를 붙이지 않으면 서버가 계산만 하고 끝난다 — 되돌리기가
없는 작업이라 실수로 올리는 일이 없어야 한다.

비밀번호는 `--password` 로도 받지만, 주지 않으면 물어본다. 명령줄에 적으면 셸 기록에 남는다.
"""

import argparse
import getpass
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# 한 번에 다 보내지 않는다. 수백 건을 한 요청에 담으면 진행 상황을 보여줄 수 없고,
# 타임아웃이 나면 무엇이 들어갔는지 알 수 없다(화면도 같은 이유로 나눠 보낸다).
BATCH = 20

PREVIEW_LABEL = {"new": "+ 새로", "over": "~ 덮음", "skip": "  건너뜀"}
RESULT_LABEL = {"created": "추가", "updated": "덮음", "skipped": "건너뜀", "failed": "실패"}


def _check(response: httpx.Response) -> dict:
    if response.status_code == 401:
        raise SystemExit("인증에 실패했습니다. 아이디·비밀번호를 확인하세요.")
    if response.status_code == 400:
        raise SystemExit(f"파일을 읽지 못했습니다 — {response.json().get('detail', '')}")
    response.raise_for_status()
    return response.json()


def main() -> int:
    parser = argparse.ArgumentParser(description="QA를 서버로 올립니다")
    parser.add_argument("--server", required=True, help="예: http://192.168.0.100:18100")
    parser.add_argument("--file", required=True, help="generated_qa.json 또는 qa_index.json")
    parser.add_argument("--user", default="admin")
    parser.add_argument("--password", default=None, help="생략하면 물어봅니다(셸 기록에 안 남습니다)")
    parser.add_argument("--apply", action="store_true", help="실제로 올립니다. 없으면 미리보기만")
    parser.add_argument("--overwrite", action="store_true", help="이미 있는 항목도 덮습니다")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.is_file():
        raise SystemExit(f"파일이 없습니다: {path}")

    base = args.server.rstrip("/")
    auth = (args.user, args.password or getpass.getpass("관리자 비밀번호: "))

    with httpx.Client(auth=auth, timeout=120) as client:
        # 1) 미리보기 — 파일은 서버가 읽는다. 형식을 아는 곳이 한 군데여야 한다.
        items = _check(client.post(
            f"{base}/api/admin/qa/import/preview",
            files={"file": (path.name, path.read_bytes(), "application/json")},
        ))["items"]

        counts = {"new": 0, "over": 0, "skip": 0}
        print(f"\n파일: {path.name} · {len(items)}건")
        for item in items:
            counts[item["status"]] = counts.get(item["status"], 0) + 1
            note = f"  ({item['reason']})" if item.get("reason") else ""
            print(f"  {PREVIEW_LABEL.get(item['status'], '?')}  {item['question'][:56]}{note}")
        print(f"\n  새로 들어옴 {counts['new']} · 덮어씀 {counts['over']} · 건너뜀 {counts['skip']}")

        if not args.apply:
            print("\n미리보기만 했습니다. 실제로 올리려면 --apply 를 붙이세요.")
            return 0

        queue = [i for i in items
                 if i["status"] == "new" or (i["status"] == "over" and args.overwrite)]
        if not queue:
            print("\n올릴 항목이 없습니다." + ("" if args.overwrite else " 덮어쓰려면 --overwrite 를 붙이세요."))
            return 0

        # 되돌리기가 없다. 덮어쓸 것이 있으면 마지막으로 한 번 더 묻는다.
        if counts["over"] and args.overwrite:
            if input(f"\n{counts['over']}건을 덮어씁니다. 계속할까요? (y/N) ").strip().lower() != "y":
                print("취소했습니다.")
                return 1

        # 2) 반영 — 몇 건씩 나눠 보낸다
        totals: dict[str, int] = {}
        for start in range(0, len(queue), BATCH):
            chunk = queue[start: start + BATCH]
            result = _check(client.post(f"{base}/api/admin/qa/import",
                                        json={"items": chunk, "overwrite": args.overwrite}))
            for row in result["items"]:
                totals[row["status"]] = totals.get(row["status"], 0) + 1
                if row["status"] == "failed":
                    print(f"  실패: {row['question'][:56]} — {row.get('reason', '')}")
            print(f"  {min(start + BATCH, len(queue))} / {len(queue)}")

    summary = " · ".join(f"{RESULT_LABEL.get(k, k)} {v}" for k, v in totals.items())
    print(f"\n완료 — {summary}")
    print("올린 항목은 **검수 대기**입니다. 관리자 화면 `검수` 에서 승인해야 답변으로 나갑니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
