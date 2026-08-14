"""운영 중에 관리자 화면(탭 ⑧)에서 바꾸는 설정.

`Settings`(환경변수)와 나눈 이유: 임계값은 실제 질문을 보면서 몇 번씩 조정하게 되는데,
그때마다 서버를 재시작할 수 없다. 여기 값들은 파일에 저장되고 다음 요청부터 바로 반영된다.
"""

import threading
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from app.core.config import get_settings
from app.core.jsonstore import read_json, write_json_atomic

_LOCK = threading.Lock()


class RuntimeConfig(BaseModel):
    # 이 값 이상이면 검수된 답변을 그대로 보여준다.
    qa_match_threshold: float = Field(ge=0.0, le=1.0)
    # answer 에 못 미쳐도 이 값 이상인 문서가 있으면 문서만 보여준다.
    related_docs_floor: float = Field(ge=0.0, le=1.0)
    related_docs_count: int = Field(ge=1, le=10)
    qa_top_k: int = Field(ge=1, le=50)
    doc_top_k: int = Field(ge=1, le=50)

    @model_validator(mode="after")
    def _floor_below_match(self) -> "RuntimeConfig":
        # 하한이 답변 임계값보다 높으면 related_docs 구간이 사라진다 —
        # 답을 못 찾은 질문이 전부 곧장 unresolved 로 떨어져 화면이 조용히 나빠진다.
        if self.related_docs_floor >= self.qa_match_threshold:
            raise ValueError("관련 문서 하한은 답변 매칭 임계값보다 낮아야 합니다.")
        return self


def _path() -> Path:
    return Path(get_settings().runtime_config_file)


def _defaults() -> RuntimeConfig:
    s = get_settings()
    return RuntimeConfig(
        qa_match_threshold=s.qa_match_threshold,
        related_docs_floor=s.related_docs_floor,
        related_docs_count=s.related_docs_count,
        qa_top_k=s.qa_top_k,
        doc_top_k=s.doc_top_k,
    )


def load_runtime_config() -> RuntimeConfig:
    """매 호출마다 파일에서 읽는다 — 관리자 화면에서 저장하면 다음 요청부터 바로 반영되도록."""
    data = read_json(_path())
    if isinstance(data, dict):
        try:
            return RuntimeConfig(**data)
        except ValueError:
            # 손으로 편집하다 깨졌더라도 챗봇은 기본값으로 계속 동작해야 한다.
            pass
    return _defaults()


def save_runtime_config(config: RuntimeConfig) -> None:
    with _LOCK:
        write_json_atomic(_path(), config.model_dump_json(indent=2))


def reset_runtime_config() -> RuntimeConfig:
    defaults = _defaults()
    save_runtime_config(defaults)
    return defaults
