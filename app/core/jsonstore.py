"""JSON 파일 저장 공통 처리.

카테고리·QA 인덱스·런타임 설정이 모두 JSON 파일 하나로 유지된다. DB를 두지 않는 이유는
항목이 수백~수천 건이고 쓰기가 관리자 저장 시점에만 일어나기 때문이다.

쓰기는 **임시 파일 → os.replace** 로 한다. 관리자가 저장하는 도중 프로세스가 죽어도
파일이 반쯤 쓰인 상태로 남지 않는다 — QA 인덱스가 깨지면 챗봇이 통째로 멈춘다.
"""

import io
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json_atomic(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # 같은 디렉터리에 임시 파일을 만들어야 os.replace 가 원자적으로 동작한다.
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
