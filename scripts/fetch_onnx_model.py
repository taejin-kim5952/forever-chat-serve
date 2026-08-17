"""임베딩 모델(ONNX) 받기 — 처음 한 번, 그리고 폐쇄망 반입 묶음 만들기.

`data/chroma/` 를 저장소에 두지 않고 재색인으로 만드는 것과 같은 원칙이다. 모델 파일은
565MB 라 저장소에 넣지 않고, **받는 방법만** 저장소에 둔다.

    python scripts/fetch_onnx_model.py              # 기본 위치(models/bge-m3-onnx)에 받기
    python scripts/fetch_onnx_model.py --dest D:/x  # 다른 곳에 받기

### 폐쇄망에는 이렇게 넣습니다

외부망 PC 에서 위 명령으로 받은 뒤 **폴더를 통째로 복사**하면 끝입니다. 인증도, 별도 도구도
필요 없습니다. 그 폴더를 `.env` 의 `EMBED_ONNX_DIR` 로 가리키거나 이미지에 `COPY` 하세요.

### 왜 int8 인가

원본(FP32)은 2,163MB 인데 int8 은 544MB 다. 같은 40문항으로 재보니 Recall@3 은 같고
Recall@1 만 1건 차이였다(인수인계 8-1). 이미지 크기가 4분의 1이 되는 값어치가 있다.

**모델을 바꾸면 전체 재색인이 필요하다.** 양자화가 다르면 벡터가 달라진다(코사인 0.984).
"""

import argparse
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEST = ROOT / "models" / "bge-m3-onnx"

REPO = "gpahal/bge-m3-onnx-int8"
# (내려받을 이름, 저장할 이름). 앱은 model.onnx · tokenizer.json 두 이름만 본다.
FILES = [
    ("model_quantized.onnx", "model.onnx"),
    ("tokenizer.json", "tokenizer.json"),
    ("sentencepiece.bpe.model", "sentencepiece.bpe.model"),
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="임베딩 모델(ONNX)을 받습니다.")
    parser.add_argument("--dest", default=str(DEFAULT_DEST), help="받을 폴더")
    parser.add_argument("--force", action="store_true", help="이미 있어도 다시 받기")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    print(f"받는 곳: {dest}\n출처: https://huggingface.co/{REPO} (MIT)\n")

    for remote, local in FILES:
        out = dest / local
        if out.exists() and not args.force:
            print(f"  건너뜀 {local:28} 이미 있음 ({out.stat().st_size / 1024 / 1024:.1f} MB)")
            continue

        url = f"https://huggingface.co/{REPO}/resolve/main/{remote}"
        print(f"  받는 중 {local:28} …", end="", flush=True)
        try:
            with httpx.stream("GET", url, timeout=600, follow_redirects=True) as response:
                if response.status_code != 200:
                    print(f" 실패 (HTTP {response.status_code})")
                    return 1
                # 통째로 메모리에 올리지 않는다 — 544MB 짜리가 있다.
                with out.open("wb") as f:
                    for chunk in response.iter_bytes(1 << 20):
                        f.write(chunk)
        except Exception as exc:  # noqa: BLE001 — 네트워크 문제는 원인을 그대로 보여준다
            print(f" 실패: {exc}")
            print("\n폐쇄망이라면 외부망 PC에서 받아 폴더를 복사해 넣으세요.")
            return 1
        print(f" {out.stat().st_size / 1024 / 1024:.1f} MB")

    total = sum(p.stat().st_size for p in dest.iterdir() if p.is_file()) / 1024 / 1024
    print(f"\n완료 — 합계 {total:.1f} MB")
    print("이 폴더를 통째로 복사하면 폐쇄망에서도 그대로 씁니다.")
    print("\n모델을 새로 받았거나 바꿨다면 **재색인**하세요:")
    print("  curl -u admin:비밀번호 -X POST \"http://localhost:18100/api/admin/qa/reindex?include_docs=true\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
