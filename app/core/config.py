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

    # ── 관리자 세션 ──────────────────────────────────────────────────────────
    # 화면의 로그인 모달이 쓰는 쿠키. Basic 인증도 그대로 살아 있다(스크립트·curl 용).
    session_cookie_name: str = "admin_session"
    session_ttl_minutes: int = 480
    # 쿠키 서명 키. 비워두면 기동할 때마다 새로 만든다 — 서버를 재시작하면 로그인이 풀리지만,
    # 키를 파일이나 코드에 남기지 않는 쪽이 안전하다. 여러 파드로 늘릴 때만 값을 준다.
    session_secret: str = ""

    # ── 임베딩 (ONNX, 앱 안에서 돈다) ─────────────────────────────────────────
    # serve 모드에서도 필요하다 — 질문을 벡터로 만들어야 검색이 된다.
    # **Ollama 로는 임베딩하지 않는다.** 같은 모델이라도 실행 방식이 다르면 벡터가 달라져
    # (실측 코사인 0.984) 색인과 검색이 조용히 어긋난다. 선택지를 두지 않는 이유다.
    embed_onnx_dir: str = "./models/bge-m3-onnx"
    # 토크나이저가 자르는 기준. bge-m3 는 8192까지 받지만 문장 하나에 그만큼 쓸 일이 없고,
    # 길이를 줄이면 CPU 색인이 빨라진다. 청크가 이보다 길면 뒷부분이 잘린다.
    embed_max_tokens: int = 512
    # 이 길이를 넘는 청크는 위 상한에 걸려 **예외 없이 뒷부분이 버려진다.**
    # 자르지는 않고 로그로만 알린다(app/ingestion/chunker.py). 0이면 확인하지 않는다.
    embed_warn_chars: int = 1800

    # ── Ollama (LLM 전용 · studio) ───────────────────────────────────────────
    # 질문·답변·채점에만 쓴다. 운영에는 이 설정이 필요 없다.
    ollama_host: str = "http://localhost:11434"
    # studio 전용. serve 모드에서는 로드하지 않는다.
    ollama_llm_model: str = "gemma4:latest"
    # 역할별 모델. 비우면 위 값을 쓴다.
    #
    # 2026-08-15 같은 문서·같은 설정으로 재본 결과(gemma4:latest vs gemma4:12b):
    #  - 답변: 12b 가 사용자 역할 셋을 모두 서술(284자), latest 는 하나만 설명하고 끝(54자)
    #  - 변형 질문: 반대로 12b 가 원문 어순만 바꿔 표현 폭이 좁았다. latest 는 구어체·명사
    #    나열까지 섞어 냈다. 적중률은 변형 질문의 표현 폭이 사실상 결정한다
    #  - 속도: 항목당 latest 17초 / 12b 76초
    # 그래서 질문·변형에는 작고 빠른 모델, 답변에는 큰 모델을 두는 배치가 유리하다.
    ollama_question_model: str = ""
    ollama_answer_model: str = ""
    # 채점 모델. **비우면 채점하지 않는다.** 답변 모델과 같은 모델로 채점하면 자기 답에 후한
    # 점수를 주므로(app/studio/judge.py), 계열이 다른 모델을 받아 여기 적기 전까지는 채점을
    # 켜지 않는 편이 낫다 — 있으나 마나 한 점수가 붙으면 검수자가 그 숫자를 믿는다.
    ollama_judge_model: str = ""
    # 이 점수 미만은 '반영'에서 자동으로 뺀다. 0점(판정 못 함)도 함께 빠진다.
    # 초안 목록에는 남으므로 사람이 보고 직접 고를 수 있다.
    qa_apply_min_score: int = 4
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
    # 납품처마다 달라지는 문자열(조직명·서비스명·도메인 소개·언어). 없으면 기본값을 쓴다.
    profile_file: str = "./data/profile.json"
    runtime_config_file: str = "./data/runtime_config.json"
    question_log_file: str = "./data/question_log.jsonl"
    question_embedding_file: str = "./data/question_embeddings.jsonl"
    # 답변에 대한 사용자 신고(👍/👎). 질문 로그와 파일을 나눈 이유는 feedback.py 상단에 있다.
    question_feedback_file: str = "./data/question_feedback.jsonl"
    analytics_file: str = "./data/analytics.json"
    # 스튜디오에서 만든 **검수 전** 초안. qa_index.json 과 일부러 파일을 나눴다 —
    # "사람 손을 안 탄 것"과 "검수 대상"이 파일 단위로 구분돼야 실수로 배포되지 않는다.
    generated_qa_file: str = "./data/generated_qa.json"
    # 마지막 품질 평가 결과. 메모리에만 두면 재시작 한 번에 사라져 진행 현황에 띄울 값이 없다.
    eval_report_file: str = "./data/eval_report.json"
    # 끝난 작업 이력(진행 현황의 '최근 작업'). 같은 이유로 파일에 남긴다.
    job_history_file: str = "./data/job_history.json"
    cluster_similarity_threshold: float = 0.85
    raw_docs_dir: str = "./data/raw_docs"

    log_level: str = "INFO"
    log_file: str = "./data/logs/app.jsonl"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def is_studio() -> bool:
    return get_settings().app_mode == "studio"
