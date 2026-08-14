from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── 실행 모드 ────────────────────────────────────────────────────────────
    # serve  : 운영. GPU가 없어 LLM을 올리지 않는다. 임베딩 + 검색만 한다.
    # studio : 사내 작업용 PC. LLM이 있어 QA 사전 생성·평가까지 한다.
    # 화면(관리자)은 이 값을 <body data-mode> 로 받아 탭을 감춘다.
    app_mode: Literal["serve", "studio"] = "serve"

    # ── 관리자 인증 ──────────────────────────────────────────────────────────
    # 비밀번호를 코드/파일에 두지 않는다. 운영은 환경변수로만 주입한다.
    admin_username: str = "admin"
    admin_password: str = "change-me"

    # ── Ollama ──────────────────────────────────────────────────────────────
    ollama_host: str = "http://localhost:11434"
    # serve 모드에서도 필요하다 — 질문을 벡터로 만들어야 검색이 된다.
    ollama_embed_model: str = "bge-m3:latest"
    # studio 전용. serve 모드에서는 로드하지 않는다.
    ollama_llm_model: str = "gemma4:latest"
    ollama_think: bool = False
    ollama_num_ctx: int = 8192
    ollama_num_predict: int = 1024

    # ── 벡터 저장소 ──────────────────────────────────────────────────────────
    chroma_persist_dir: str = "./data/chroma"
    # 사용자 질문이 실제로 부딪치는 인덱스. 검수된 QA의 질문·변형 질문이 들어간다.
    chroma_qa_collection: str = "qa_index"
    # answer 를 못 찾았을 때 related_docs 를 뽑는 보조 인덱스.
    chroma_doc_collection: str = "doc_chunks"

    # ── 매칭 임계값 ──────────────────────────────────────────────────────────
    # 이 값 이상이면 미리 검수해 둔 답변을 그대로 보여준다(result_type=answer).
    qa_match_threshold: float = 0.90
    # answer 에 못 미쳐도 이 값 이상인 문서가 있으면 문서만 보여준다(related_docs).
    # 둘 다 못 넘기면 unresolved 로 접수한다.
    related_docs_floor: float = 0.55
    related_docs_count: int = 3
    # 상위 몇 건을 놓고 고를지. 같은 QA의 변형 질문이 여러 개 잡히므로 넉넉히 본다.
    qa_top_k: int = 10
    doc_top_k: int = 10

    # ── 파일 경로 ────────────────────────────────────────────────────────────
    qa_index_file: str = "./data/qa_index.json"
    categories_file: str = "./data/categories.json"
    runtime_config_file: str = "./data/runtime_config.json"
    question_log_file: str = "./data/question_log.jsonl"
    question_embedding_file: str = "./data/question_embeddings.jsonl"
    analytics_file: str = "./data/analytics.json"
    cluster_similarity_threshold: float = 0.85
    raw_docs_dir: str = "./data/raw_docs"

    log_level: str = "INFO"
    log_file: str = "./data/logs/app.jsonl"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def is_studio() -> bool:
    return get_settings().app_mode == "studio"
