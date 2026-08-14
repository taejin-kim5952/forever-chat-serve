"""ChromaDB 접근 공통 처리.

컬렉션이 둘이다.

- `qa_index`   — 검수된 QA의 질문과 변형 질문. 사용자 질문이 실제로 부딪치는 곳.
- `doc_chunks` — 원본 문서 청크. `answer` 를 못 찾았을 때 `related_docs` 를 뽑는 보조.

### 임베딩 모델을 바꾸면

차원이 달라진다(bge-m3 1024 ↔ embeddinggemma 768). 옛 벡터와 새 질문 벡터를 섞어 비교하면
Chroma가 예외를 내거나, 더 나쁘게는 조용히 엉뚱한 결과를 준다. 그래서 컬렉션 메타데이터에
**어떤 모델로 색인했는지** 적어두고, 다를 때 예외로 세운다. "재색인하세요"라는 문장 하나가
없어서 며칠을 헤매는 상황을 막기 위한 것이다.
"""

import threading
from pathlib import Path

import chromadb
from chromadb.api.models.Collection import Collection

from app.core.config import get_settings
from app.core.logging import get_logger, log_event

logger = get_logger("ingestion.vector_store")

_LOCK = threading.Lock()
_CLIENT: chromadb.ClientAPI | None = None

_EMBED_MODEL_KEY = "embed_model"


class EmbedModelMismatch(RuntimeError):
    pass


def get_client() -> chromadb.ClientAPI:
    """Chroma 클라이언트는 프로세스당 하나만 둔다 — 같은 디렉터리를 여러 번 열면
    파일 잠금이 부딪친다."""
    global _CLIENT
    with _LOCK:
        if _CLIENT is None:
            persist_dir = get_settings().chroma_persist_dir
            Path(persist_dir).mkdir(parents=True, exist_ok=True)
            _CLIENT = chromadb.PersistentClient(path=persist_dir)
        return _CLIENT


def reset_client() -> None:
    """테스트에서 설정을 바꿔 끼울 때 쓴다."""
    global _CLIENT
    with _LOCK:
        _CLIENT = None


def get_collection(name: str, check_model: bool = True) -> Collection:
    settings = get_settings()
    collection = get_client().get_or_create_collection(
        name,
        metadata={"hnsw:space": "cosine", _EMBED_MODEL_KEY: settings.ollama_embed_model},
    )

    if check_model:
        indexed_with = (collection.metadata or {}).get(_EMBED_MODEL_KEY)
        if indexed_with and indexed_with != settings.ollama_embed_model and collection.count():
            raise EmbedModelMismatch(
                f"'{name}' 컬렉션은 '{indexed_with}' 로 색인돼 있는데 현재 임베딩 모델은 "
                f"'{settings.ollama_embed_model}' 입니다. 모델을 되돌리거나 재색인하세요."
            )
    return collection


def qa_collection(check_model: bool = True) -> Collection:
    return get_collection(get_settings().chroma_qa_collection, check_model=check_model)


def doc_collection(check_model: bool = True) -> Collection:
    return get_collection(get_settings().chroma_doc_collection, check_model=check_model)


def rebuild_collection(name: str) -> Collection:
    """컬렉션을 비우고 현재 임베딩 모델로 다시 만든다. 재색인의 첫 단계."""
    client = get_client()
    try:
        client.delete_collection(name)
    except Exception:   # noqa: BLE001 - 없으면 지울 것도 없다
        pass
    log_event(logger, "collection rebuilt", collection=name, embed_model=get_settings().ollama_embed_model)
    return get_collection(name, check_model=False)


def to_similarity(distance: float) -> float:
    """Chroma 는 코사인 '거리'(1 - 유사도)를 준다. 화면과 임계값은 유사도로만 이야기하므로
    경계에서 뒤집히지 않게 여기 한 곳에서만 변환한다."""
    return 1.0 - float(distance)
