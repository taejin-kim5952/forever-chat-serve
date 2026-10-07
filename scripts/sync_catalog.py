"""사이트 카탈로그를 받아 사전과 문서를 만든다 (개발계획서 §4.4 · §5.4).

    python scripts/sync_catalog.py --pack packs/mcp-manager --var var/mcp-manager \\
                                   --base http://localhost:9050 --cookie "session=..."

야간 배치로 돈다. 두 가지를 만든다.

  gazetteer   `var/<pack>/gazetteer.json` — 질문에서 서버 이름을 알아보게 하는 사전
  카탈로그 문서 `packs/<pack>/raw_docs/catalog/*.md` — 새 서버가 관련 문서로 잡히게

### 왜 문서까지 만드나

서버가 늘 때마다 사람이 문서를 쓰게 두면 **문서가 반드시 뒤처진다.** 자동 생성분은
`source: generated` 로 표시해 사람이 편집하지 않게 한다 — 다음 배치가 덮어쓴다.

### 자동 생성 문서로 만든 QA 는 자동 승인하지 않는다

초안은 `pending` 으로만 들어가고 검수를 거친다. 이 규칙에는 예외를 두지 않는다 —
검수되지 않은 답이 나가기 시작하면 검수 체계 전체가 무의미해진다.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CATALOG_DIR = "catalog"

DOC_TEMPLATE = """---
title: {name}
category: MCP 서버 > {name}
source: generated
updated: {updated}
---

## 개요

**{name}** ({registry_key}) 은 {status_label} 상태입니다.
{description}

## 제공 Tool

{tools}

## 연동

이 서버를 쓰려면 MCP 포털에서 서버 상세를 열어 Endpoint 를 확인하세요.
현재 상태와 가용률은 **챗봇에게 직접 물어보면** 지금 값을 알려 줍니다 — 이 문서는 야간에 만들어졌습니다.
"""


def fetch(base: str, path: str, headers: dict) -> dict | None:
    request = urllib.request.Request(f"{base.rstrip('/')}{path}", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        print(f"  [오류] {path} → HTTP {exc.code}")
        return None
    except Exception as exc:  # noqa: BLE001
        print(f"  [오류] {path} → {exc}")
        return None


def write_gazetteer(var_dir: Path, servers: list[dict]) -> Path:
    """엔진이 읽는 사전. 형태는 `app/pipeline/lookup/entities.py` 가 정한다."""
    path = var_dir / "gazetteer.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"servers": servers}, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_docs(pack_dir: Path, servers: list[dict], updated: str) -> int:
    """서버마다 문서 한 장. **기존 문서를 덮지 않는다** — 사람이 쓴 것과 섞이면 안 된다."""
    docs_dir = pack_dir / "raw_docs" / CATALOG_DIR
    docs_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    for server in servers:
        name = server.get("name")
        if not name:
            continue
        tools = server.get("toolNames") or []
        body = DOC_TEMPLATE.format(
            name=name,
            registry_key=server.get("registryKey") or name,
            status_label=server.get("statusLabel") or "등록",
            description=server.get("description") or "",
            updated=updated,
            tools="\n".join(f"- `{t}`" for t in tools) or "아직 수집된 Tool 이 없습니다.",
        )
        (docs_dir / f"{name}.md").write_text(body, encoding="utf-8")
        written += 1
    return written


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", required=True)
    parser.add_argument("--var", required=True)
    parser.add_argument("--base", default="http://localhost:9050")
    # 사이트는 사용자 자격으로 부른다 — 배치 계정이 볼 수 있는 것만 사전에 담긴다.
    parser.add_argument("--cookie", default="")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--no-docs", action="store_true", help="사전만 만들고 문서는 만들지 않는다")
    args = parser.parse_args()

    pack_dir = Path(args.pack)
    var_dir = Path(args.var)
    if not pack_dir.is_dir():
        print(f"팩 경로가 없습니다: {pack_dir}")
        return 2

    headers = {"Cookie": args.cookie} if args.cookie else {}
    payload = fetch(args.base, f"/api/user/assistant/catalog?limit={args.limit}", headers)
    if payload is None:
        # 사전을 비우지 않는다. 어제 것으로 계속 도는 편이, 이름을 하나도 못 알아보는 것보다 낫다.
        print("  카탈로그를 받지 못해 사전을 그대로 둡니다.")
        return 1

    servers = payload.get("servers") or []
    print(f"카탈로그 — 서버 {len(servers)}건 (조회 {payload.get('checkedAt')})")

    path = write_gazetteer(var_dir, servers)
    print(f"  사전  {path}")

    if not args.no_docs:
        # 설정 없이 부를 수 있게 환경을 세운다 (다른 도구와 같은 방식).
        os.environ.setdefault("PACK_DIR", str(pack_dir))
        os.environ.setdefault("VAR_DIR", str(var_dir))
        count = write_docs(pack_dir, servers, payload.get("checkedAt", "")[:10])
        print(f"  문서  {count}건 → {pack_dir / 'raw_docs' / CATALOG_DIR}")
        print()
        print("  다음: python scripts/pack_index.py " + str(pack_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
