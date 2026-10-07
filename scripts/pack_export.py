"""운영 반입용으로 팩을 묶는다 (개발계획서 §3.5).

    python scripts/pack_export.py packs/mcp-manager

담는 것은 **배포 대상만**이다. 검수 전 초안(`generated_qa.json`)과 런타임 산출물은
빼고, 체크섬을 함께 넣는다 — 반입한 쪽이 "받은 것이 보낸 것과 같은가" 를 확인할 수 있어야
팩 배포가 절차로 성립한다.

**색인 결과(chroma)는 넣지 않는다.** 임베딩 모델이 다르면 그대로 쓸 수 없고, 반입 쪽에서
`pack_index.py` 를 한 번 돌리면 되는 파생물이다. 50MB 를 옮길 이유가 없다.
"""

import hashlib
import json
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# 배포에 담는 것. 계획서 부록 B 의 "배포 포함" 열과 같다.
INCLUDE_FILES = ["pack.json", "categories.json", "qa_index.json", "profile.json",
                 "glossary.json", "lookup.yaml", "README.md"]
INCLUDE_DIRS = ["raw_docs", "prompts"]

# 일부러 뺀다. 검수 전 초안이 운영에 섞이면 검수 체계가 무의미해진다.
EXCLUDE = {"generated_qa.json"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 16), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    if len(sys.argv) < 2:
        print("사용법: python scripts/pack_export.py <팩 경로> [출력 경로]")
        return 2
    pack_dir = Path(sys.argv[1])
    if not pack_dir.is_dir():
        print(f"팩 경로가 없습니다: {pack_dir}")
        return 2

    from scripts.pack_validate import Report, check_categories, check_docs, check_manifest, check_qa

    report = Report()
    check_manifest(pack_dir, report)
    ids = check_categories(pack_dir, report)
    check_qa(pack_dir, ids, report)
    check_docs(pack_dir, report)
    if report.errors:
        # 잘못된 팩을 묶어 보내면 반입 쪽에서 서버가 안 뜬다. 여기서 막는 편이 낫다.
        report.print(pack_dir)
        print("  오류가 있어 묶지 않았습니다.")
        return 1

    targets: list[Path] = []
    for name in INCLUDE_FILES:
        path = pack_dir / name
        if path.is_file() and name not in EXCLUDE:
            targets.append(path)
    for name in INCLUDE_DIRS:
        directory = pack_dir / name
        if not directory.is_dir():
            continue
        targets.extend(p for p in sorted(directory.rglob("*")) if p.is_file())

    if not targets:
        print("담을 것이 없습니다.")
        return 1

    checksums = {str(p.relative_to(pack_dir)).replace("\\", "/"): _sha256(p) for p in targets}
    manifest = {
        "pack_id": pack_dir.name,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "file_count": len(targets),
        "checksums": checksums,
    }

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "dist" / f"{pack_dir.name}-{stamp}.zip"
    out.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in targets:
            archive.write(path, str(path.relative_to(pack_dir)).replace("\\", "/"))
        archive.writestr("CHECKSUMS.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    print(f"묶었습니다: {out}")
    print(f"  파일 {len(targets)}건 · {out.stat().st_size / 1024:.0f}KB")
    if report.warnings:
        print(f"  경고 {len(report.warnings)}건 — pack_validate.py 로 확인하세요")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
