"""임베딩 생성 — ONNX Runtime 으로 **앱 안에서** 돈다.

serve 모드에서 **유일하게 남는 AI 모델**이다. LLM(수 GB, 답변 1건에 1~3분)은 운영에서
걷어냈지만, 사용자 질문을 벡터로 바꾸는 일은 여기서 해야 검색이 성립한다.

### 왜 Ollama 를 안 쓰는가 ★

임베딩 하나 때문에 **컨테이너를 하나 더 띄워야 했다.** 파드 안에 챗봇 + Ollama 두 개가
있었고, 폐쇄망에는 Ollama 바이너리와 모델을 따로 반입해야 했다. 앱 안에서 돌리면 그 전부가
사라진다. 2026-08-17 실측(인수인계 8-1):

| | Ollama GGUF F16 (GPU) | ONNX int8 (CPU) |
| 검색 | 254ms/건 | **35ms/건** |
| 반입 | Ollama + 모델 pull | 파일 3개 565MB |

GPU 쪽이 오히려 느린 이유는, 짧은 질문 한 건에서는 모델 연산보다 **HTTP 호출·서빙
오버헤드가 지배적**이기 때문이다. 같은 프로세스에서 부르면 그 비용이 통째로 없어진다.
운영에는 GPU가 없으므로 이 35ms 가 운영 실제 값이다.

### 구현을 하나만 두는 이유 ★

Ollama 로도 임베딩할 수 있게 남겨 두면 언젠가 누가 그것을 켠다. 같은 `bge-m3` 라도
**실행 방식이 다르면 벡터가 다르다** — 실측 코사인 0.984 다. 색인과 검색이 어긋나면
예외는 안 나고 검색 품질만 조용히 무너진다. 그래서 선택지를 **없앴다.**

LLM(질문·답변·채점)은 여전히 Ollama 를 쓴다. 그쪽은 스튜디오 전용이라 운영에 없다.

### 태스크 접두어

모델에 따라 입력 앞에 용도를 알려주는 접두어를 붙여야 제 성능이 난다. `bge-m3` 는 접두어
없이 학습돼 붙이면 오히려 손해다. 모델을 바꿀 때 이 표를 함께 확인해야 하고, 색인할 때와
검색할 때 **같은 규칙**을 써야 한다. 한쪽만 바꾸면 예외는 안 나고 품질만 무너진다.

태스크가 세 가지인 이유:

- `document` / `query` — **비대칭** 검색. 짧은 질문으로 긴 문서를 찾는 경우(문서 인덱스).
- `similarity` — **대칭** 비교. 질문으로 질문을 찾는 경우(QA 인덱스).
"""

import threading
from pathlib import Path
from typing import Literal

import numpy as np

from app.core.config import get_settings
from app.core.logging import get_logger, log_event

logger = get_logger("ingestion.embedder")

EmbedTask = Literal["query", "document", "similarity"]

MODEL_FILE = "model.onnx"
TOKENIZER_FILE = "tokenizer.json"

# {모델 이름 접두사: {태스크: 포맷}}. `{t}` 자리에 원문이 들어간다.
_PREFIX: dict[str, dict[str, str]] = {
    "embeddinggemma": {
        "query": "task: search result | query: {t}",
        "document": "title: none | text: {t}",
        "similarity": "task: sentence similarity | query: {t}",
    },
    "qwen3-embedding": {
        "query": "Instruct: Given a search query, retrieve relevant passages that answer it\nQuery: {t}",
        "document": "{t}",
        "similarity": "Instruct: Retrieve semantically similar text\nQuery: {t}",
    },
}

_NO_PREFIX = {"query": "{t}", "document": "{t}", "similarity": "{t}"}


class ModelFilesMissing(RuntimeError):
    """모델 파일이 없다. 받는 방법까지 문구에 담는다 — 여기서 막히면 아무것도 안 된다."""


def _prefix_table(name: str) -> dict[str, str]:
    lowered = name.lower()
    for key, table in _PREFIX.items():
        if key in lowered:
            return table
    return _NO_PREFIX


# 세션은 무겁다(수백 MB 로드). 프로세스당 하나만 만들어 돌려 쓴다.
_LOCK = threading.Lock()
_SESSION = None
_TOKENIZER = None
_LOADED_DIR: str | None = None


def _load(model_dir: Path):
    """ONNX 세션과 토크나이저를 한 번만 만든다."""
    global _SESSION, _TOKENIZER, _LOADED_DIR
    with _LOCK:
        if _SESSION is not None and _LOADED_DIR == str(model_dir):
            return _SESSION, _TOKENIZER

        model_path, tokenizer_path = model_dir / MODEL_FILE, model_dir / TOKENIZER_FILE
        if not model_path.exists() or not tokenizer_path.exists():
            raise ModelFilesMissing(
                f"임베딩 모델 파일이 없습니다: {model_dir}\n"
                f"  python scripts/fetch_onnx_model.py   로 받으세요(약 565MB).\n"
                f"  폐쇄망이면 이 폴더를 통째로 복사해 넣으면 됩니다."
            )

        import onnxruntime as ort
        from tokenizers import Tokenizer

        options = ort.SessionOptions()
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        # CPU 로 고정한다. 실행 제공자가 다르면 벡터가 미세하게 달라질 수 있고, 그러면
        # 스튜디오에서 색인한 것과 운영에서 검색하는 것이 어긋난다. 운영에는 GPU도 없다.
        session = ort.InferenceSession(str(model_path), options, providers=["CPUExecutionProvider"])

        tokenizer = Tokenizer.from_file(str(tokenizer_path))
        tokenizer.enable_truncation(max_length=get_settings().embed_max_tokens)
        # **패딩을 켜지 않는다.** 아래 embed_batch 주석 참고 — 켜면 느려지고 틀린다.

        _SESSION, _TOKENIZER, _LOADED_DIR = session, tokenizer, str(model_dir)
        log_event(logger, "embedding model loaded", model_dir=str(model_dir),
                  inputs=[i.name for i in session.get_inputs()])
        return _SESSION, _TOKENIZER


def reset_session() -> None:
    """테스트에서 설정을 바꿔 끼울 때 쓴다."""
    global _SESSION, _TOKENIZER, _LOADED_DIR
    with _LOCK:
        _SESSION = _TOKENIZER = _LOADED_DIR = None


class OnnxEmbedder:
    def __init__(self, model_dir: str | None = None):
        settings = get_settings()
        self.model_dir = Path(model_dir or settings.embed_onnx_dir)
        # 컬렉션 메타데이터에 적히는 이름. 폴더 이름이 곧 "무엇으로 색인했는가"다 —
        # 같은 bge-m3 라도 양자화가 다르면 벡터가 다르므로 이름으로 구분해야 한다.
        self.model = self.model_dir.name
        self._prefix = _prefix_table(self.model)

    def _apply(self, text: str, task: EmbedTask) -> str:
        return self._prefix[task].format(t=text)

    def embed_batch(self, texts: list[str], task: EmbedTask = "similarity") -> list[list[float]]:
        """여러 건을 임베딩한다. **한 건씩 돌린다** — 묶어서 돌리지 않는다.

        묶으면 짧은 문장도 배치에서 가장 긴 문장 길이만큼 패딩되는데, 이 모델에서는 그것이
        두 가지를 망가뜨린다(2026-08-17 실측).

        - **틀린다**: 같은 문장인데 배치로 넣으면 벡터가 달라진다(코사인 0.988). 색인은
          여러 청크를 묶어서, 검색은 한 건만 넣으므로 **정확히 같은 질문도 1.000이 안 나온다.**
          유사도 임계값 0.90 의 여유가 그만큼 줄어든다
        - **느리다**: 청크 67개에 배치 57.8초 / 한 건씩 10.4초. 짧은 문장에 긴 문장만큼의
          계산을 시키기 때문이다. **5.6배 차이**다

        묶는 것이 항상 빠르다는 통념이 여기서는 반대다.
        """
        if not texts:
            return []
        session, tokenizer = _load(self.model_dir)
        names = {i.name for i in session.get_inputs()}

        vectors = []
        for text in texts:
            encoded = tokenizer.encode(self._apply(text, task))
            feed = {
                "input_ids": np.array([encoded.ids], dtype=np.int64),
                "attention_mask": np.array([encoded.attention_mask], dtype=np.int64),
            }
            output = session.run(None, {k: v for k, v in feed.items() if k in names})[0]

            # bge-m3 는 dense/sparse/colbert 를 함께 내보낸다. 첫 출력(dense)만 쓴다.
            vector = np.asarray(output, dtype=np.float32)[0]
            if vector.ndim == 2:                   # (seq, hidden) 이면 CLS 토큰
                vector = vector[0]
            norm = float(np.linalg.norm(vector))
            vectors.append((vector / max(norm, 1e-12)).astype(float).tolist())
        return vectors

    def embed(self, text: str, task: EmbedTask = "similarity") -> list[float]:
        return self.embed_batch([text], task)[0]
