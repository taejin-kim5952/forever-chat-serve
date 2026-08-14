"""테스트 격리.

이전 프로젝트에서 테스트가 실제 `data/` 를 건드려 질문 로그와 벡터 저장소를 오염시킨 적이
있다. 그래서 모든 테스트는 **자동으로** 임시 디렉터리를 쓴다(autouse). 개별 테스트가
격리를 잊어도 실제 데이터에 닿지 않는다.

임베딩은 Ollama 를 부르지 않고 가짜로 바꾼다. 테스트는 검색 로직을 검증하는 것이지
모델 성능을 재는 것이 아니고, 모델이 없는 CI 에서도 돌아야 한다.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings, get_settings   # noqa: E402


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    """설정의 모든 경로를 임시 디렉터리로 돌린다."""
    get_settings.cache_clear()

    overrides = {
        "chroma_persist_dir": str(tmp_path / "chroma"),
        "qa_index_file": str(tmp_path / "qa_index.json"),
        "categories_file": str(tmp_path / "categories.json"),
        "runtime_config_file": str(tmp_path / "runtime_config.json"),
        "question_log_file": str(tmp_path / "question_log.jsonl"),
        "question_embedding_file": str(tmp_path / "question_embeddings.jsonl"),
        "analytics_file": str(tmp_path / "analytics.json"),
        "raw_docs_dir": str(tmp_path / "raw_docs"),
        "log_file": str(tmp_path / "logs" / "app.jsonl"),
        "admin_username": "tester",
        "admin_password": "secret",
    }
    settings = Settings(**overrides)
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)
    for module in [
        "app.core.categories", "app.core.question_log", "app.core.runtime_config",
        "app.qa.store", "app.ingestion.vector_store", "app.ingestion.embedder",
        "app.ingestion.doc_index", "app.api.admin_docs", "app.api.admin_settings",
        "app.api.health", "app.main", "app.core.auth",
    ]:
        try:
            monkeypatch.setattr(f"{module}.get_settings", lambda: settings, raising=False)
        except AttributeError:
            pass

    Path(overrides["raw_docs_dir"]).mkdir(parents=True, exist_ok=True)

    from app.ingestion import vector_store
    from app.pipeline import retrieve
    vector_store.reset_client()
    retrieve.reset_retriever()
    yield settings
    vector_store.reset_client()
    retrieve.reset_retriever()
    get_settings.cache_clear()


class FakeEmbedder:
    """문자열을 결정적인 벡터로 바꾼다.

    같은 문장은 같은 벡터, 겹치는 글자가 많을수록 가까운 벡터가 나오도록
    글자 단위 해시 버킷을 센다. 실제 임베딩과 값은 다르지만 "비슷한 문장이 더 가깝다"는
    성질은 유지되므로 임계값 분기를 검증할 수 있다.
    """

    DIM = 64

    def __init__(self, *args, **kwargs):
        self.model = "fake-embed"

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self.DIM
        for char in text:
            vector[ord(char) % self.DIM] += 1.0
        norm = sum(v * v for v in vector) ** 0.5 or 1.0
        return [v / norm for v in vector]

    def embed(self, text: str, task: str = "similarity") -> list[float]:
        return self._vector(text)

    def embed_batch(self, texts: list[str], task: str = "similarity") -> list[list[float]]:
        return [self._vector(t) for t in texts]


@pytest.fixture(autouse=True)
def fake_embedder(monkeypatch):
    for module in ["app.ingestion.doc_index", "app.qa.index", "app.ingestion.embedder"]:
        monkeypatch.setattr(f"{module}.OllamaEmbedder", FakeEmbedder, raising=False)
