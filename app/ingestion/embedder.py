"""임베딩 생성.

serve 모드에서 **유일하게 남는 AI 모델**이다. LLM(수 GB, 답변 1건에 1~3분)은 운영에서
걷어냈지만, 사용자 질문을 벡터로 바꾸는 일은 여기서 해야 검색이 성립한다.
인코더라 CPU에서도 질문 1건에 0.5~1초 수준으로 끝난다.

### 태스크 접두어

모델에 따라 입력 앞에 용도를 알려주는 접두어를 붙여야 제 성능이 난다.
`bge-m3` 는 접두어 없이 학습돼 붙이면 오히려 손해고, `embeddinggemma` 는 붙여야 한다.
그래서 모델별 표를 두고, 모르는 모델은 접두어 없이 쓴다(가장 안전한 쪽).

태스크가 세 가지인 이유:

- `document` / `query` — **비대칭** 검색. 짧은 질문으로 긴 문서를 찾는 경우(문서 인덱스).
- `similarity` — **대칭** 비교. 질문으로 질문을 찾는 경우(QA 인덱스). 양쪽 길이와 성격이
  같으므로 한쪽만 query 로 취급하면 오히려 어긋난다.

인덱싱할 때와 검색할 때 **같은 태스크 규칙**을 써야 한다. 한쪽만 바꾸면 유사도가 통째로
어긋나는데, 예외는 안 나고 검색 품질만 조용히 무너져서 알아채기 가장 어려운 종류의 버그다.
"""

from typing import Literal

import ollama

from app.core.config import get_settings

EmbedTask = Literal["query", "document", "similarity"]

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


def _prefix_table(model: str) -> dict[str, str]:
    name = model.split(":")[0].lower()
    for key, table in _PREFIX.items():
        if name.startswith(key):
            return table
    return _NO_PREFIX


class OllamaEmbedder:
    def __init__(self, model: str | None = None, host: str | None = None):
        settings = get_settings()
        self.model = model or settings.ollama_embed_model
        self.client = ollama.Client(host=host or settings.ollama_host)
        self._prefix = _prefix_table(self.model)

    def _apply(self, text: str, task: EmbedTask) -> str:
        return self._prefix[task].format(t=text)

    def embed(self, text: str, task: EmbedTask = "similarity") -> list[float]:
        response = self.client.embed(model=self.model, input=self._apply(text, task))
        return response["embeddings"][0]

    def embed_batch(self, texts: list[str], task: EmbedTask = "similarity") -> list[list[float]]:
        if not texts:
            return []
        response = self.client.embed(model=self.model, input=[self._apply(t, task) for t in texts])
        return response["embeddings"]
