"""테스트 격리.

이전 프로젝트에서 테스트가 실제 `data/` 를 건드려 질문 로그와 벡터 저장소를 오염시킨 적이
있다. 그래서 모든 테스트는 **자동으로** 임시 디렉터리를 쓴다(autouse). 개별 테스트가
격리를 잊어도 실제 데이터에 닿지 않는다.

임베딩은 Ollama 를 부르지 않고 가짜로 바꾼다. 테스트는 검색 로직을 검증하는 것이지
모델 성능을 재는 것이 아니고, 모델이 없는 CI 에서도 돌아야 한다.

**격리 장치가 두 겹이다.** 아래 `isolated_data` 가 앱 코드의 경로를 전부 임시 폴더로
돌리고, `real_data_untouched` 가 매 테스트 뒤에 실제 `data/` 가 그대로인지 확인한다.
두 번째가 필요한 이유는 2026-08-17 에 실제로 겪었다 — 테스트 **파일 자신**이
`from app.core.config import get_settings` 로 함수를 미리 가져가면, monkeypatch 는
`app.*` 모듈의 이름만 바꾸므로 테스트 모듈에 붙잡힌 원본은 그대로 살아 있다. 그 원본이
돌려준 기본 경로(`./data/...`)로 파일을 써서 **`data/qa_index.json` 이 `{}` 로 덮였다.**
앱은 멀쩡히 격리돼 있었고 테스트는 초록불이었다. 값 검사만으로는 못 잡는 종류라
결과물(파일)을 직접 본다.
"""

import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings, get_settings   # noqa: E402

REAL_DATA = Path(__file__).resolve().parents[1] / "data"


def _fingerprint() -> dict[str, str]:
    """실제 `data/` 의 파일 목록과 내용 해시. 크기·시각이 아니라 내용을 본다 —
    같은 길이로 덮이는 사고가 실제로 있었다(25KB 파일이 `{}` 2바이트가 된 건 눈에 띄지만,
    JSONL 한 줄이 바뀌는 경우는 안 띈다)."""
    if not REAL_DATA.is_dir():
        return {}
    out: dict[str, str] = {}
    for path in REAL_DATA.rglob("*"):
        if not path.is_file():
            continue
        rel = str(path.relative_to(REAL_DATA))
        # 벡터 저장소는 파생물이고 sqlite 라 열기만 해도 바뀐다. 원본만 지킨다.
        if rel.startswith(("chroma", "logs")):
            continue
        out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


@pytest.fixture(autouse=True)
def real_data_untouched():
    """테스트가 끝난 뒤 실제 `data/` 가 그대로인지 확인한다.

    격리가 뚫렸다는 것은 그 테스트의 실패가 아니라 **저장소의 사고**다. 그래서 조용히
    넘기지 않고 무엇이 바뀌었는지 이름까지 찍어서 멈춘다.
    """
    before = _fingerprint()
    yield
    after = _fingerprint()

    changed = sorted(
        name for name in set(before) | set(after)
        if before.get(name) != after.get(name)
    )
    assert not changed, (
        "테스트가 실제 data/ 를 건드렸습니다: " + ", ".join(changed)
        + "\n테스트 모듈이 `from app.core.config import get_settings` 로 함수를 미리 가져가"
          " 격리를 우회했을 가능성이 큽니다. `from app.core import config` 뒤"
          " `config.get_settings()` 로 부르세요."
    )


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    """설정의 모든 경로를 임시 디렉터리로 돌린다."""
    get_settings.cache_clear()

    overrides = {
        # 모드를 고정한다. studio 가 필요한 테스트는 `is_studio` 를 갈아 끼운다.
        "app_mode": "serve",
        "chroma_persist_dir": str(tmp_path / "chroma"),
        "qa_index_file": str(tmp_path / "qa_index.json"),
        "categories_file": str(tmp_path / "categories.json"),
        "profile_file": str(tmp_path / "profile.json"),
        "runtime_config_file": str(tmp_path / "runtime_config.json"),
        "question_log_file": str(tmp_path / "question_log.jsonl"),
        "question_embedding_file": str(tmp_path / "question_embeddings.jsonl"),
        "question_feedback_file": str(tmp_path / "question_feedback.jsonl"),
        "analytics_file": str(tmp_path / "analytics.json"),
        "generated_qa_file": str(tmp_path / "generated_qa.json"),
        "eval_report_file": str(tmp_path / "eval_report.json"),
        "job_history_file": str(tmp_path / "job_history.json"),
        "raw_docs_dir": str(tmp_path / "raw_docs"),
        # 임베딩은 `FakeEmbedder` 로 갈아 끼우므로 실제 모델 파일이 없어도 된다. 다만 경로가
        # 실제 `models/` 를 가리키면 아래 '격리 누락' 검사에 걸리므로 임시 폴더로 돌린다.
        "embed_onnx_dir": str(tmp_path / "models" / "bge-m3-onnx"),
        "log_file": str(tmp_path / "logs" / "app.jsonl"),
        "admin_username": "tester",
        "admin_password": "secret",
    }
    # `_env_file=None` 으로 **개발 PC의 `.env` 를 아예 안 읽는다.** 위 목록에 없는 설정은
    # 클래스 기본값이 된다.
    #
    # 예전에는 `.env` 를 그대로 읽었고, 그래서 목록에 넣는 것을 잊은 설정만 개발자 PC의 값을
    # 봤다. `APP_MODE=studio` 때문에 "운영에서 막히는가" 테스트가 전부 통과해 버린 적이 있고,
    # `OLLAMA_JUDGE_MODEL` 이 설정돼 있으면 "채점 모델을 안 정하면 채점하지 않는다" 테스트가
    # 실패한다 — 코드가 아니라 **그 PC의 .env 에 따라** 결과가 달라졌다. 목록을 늘리는 것으로는
    # 설정이 새로 생길 때마다 같은 일이 반복되므로, 읽는 것 자체를 끊는다.
    settings = Settings(_env_file=None, **overrides)

    # 경로 설정이 새로 생겼는데 위 목록에 넣는 것을 잊으면, 그 파일만 조용히 실제 data/ 를
    # 가리킨다. 실제로 `generated_qa_file` 을 빠뜨려 테스트가 생성 초안 파일을 덮어쓴 적이 있다.
    # 이름으로 훑어서 임시 폴더 밖을 가리키는 설정이 하나라도 있으면 여기서 멈춘다.
    leaked = sorted(
        name for name, value in settings.model_dump().items()
        if (name.endswith("_file") or name.endswith("_dir")) and not str(value).startswith(str(tmp_path))
    )
    assert not leaked, f"테스트 격리 누락 — 실제 경로를 가리키는 설정: {', '.join(leaked)}"
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)
    # 모듈마다 `from app.core.config import get_settings` 로 **자기 이름공간에 복사**해 두므로
    # 위 한 줄로는 부족하다. 예전에는 모듈 이름을 손으로 적어 뒀는데, 새 모듈을 만들고 목록에
    # 넣는 것을 잊으면 그 모듈만 조용히 실제 `.env`·실제 `data/` 를 본다. 실제로 `app.api.
    # admin_auth` 가 빠져 있어서, 개발 PC의 `.env`(APP_MODE=studio)를 읽고 모드 테스트가
    # 어긋났다. 그래서 목록 대신 **이미 불러온 app.* 모듈을 훑어서** 전부 갈아 끼운다.
    for name, module in list(sys.modules.items()):
        if name.startswith("app.") and hasattr(module, "get_settings"):
            monkeypatch.setattr(f"{name}.get_settings", lambda: settings, raising=False)

    Path(overrides["raw_docs_dir"]).mkdir(parents=True, exist_ok=True)

    _redirect_logging(settings)

    from app.ingestion import vector_store
    from app.pipeline import retrieve
    from app.studio import evaluate, runner
    vector_store.reset_client()
    retrieve.reset_retriever()
    # 생성·평가 잡은 모듈 전역이라 초기화하지 않으면 앞 테스트의 상태가 다음 테스트로 샌다.
    runner.reset_job()
    evaluate.reset_job()
    yield settings
    vector_store.reset_client()
    retrieve.reset_retriever()
    runner.reset_job()
    evaluate.reset_job()
    get_settings.cache_clear()


def _redirect_logging(settings) -> None:
    """로그 핸들러를 임시 디렉터리로 다시 건다.

    `setup_logging()` 은 `app.main` 을 import 하는 순간(= 테스트 수집 시점) **실제 설정으로**
    한 번 돈다. 그대로 두면 테스트가 남기는 로그가 운영·개발 로그 파일에 그대로 섞여 들어간다.
    실제 데이터를 건드리지 않는다는 규칙은 `data/` 뿐 아니라 로그 파일에도 적용된다.
    """
    import logging

    from app.core.logging import setup_logging

    root = logging.getLogger("faq_service")
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    setup_logging()


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
        monkeypatch.setattr(f"{module}.OnnxEmbedder", FakeEmbedder, raising=False)
