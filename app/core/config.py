from contextvars import ContextVar
from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _join(base: str, name: str) -> str:
    """경로를 잇는다. `Path` 를 쓰지 않는 이유는 Windows 에서 구분자가 `\\` 로 바뀌어
    기존 기본값(`./data/qa_index.json`)과 문자열이 달라지기 때문이다 — 동작은 같지만
    설정을 눈으로 대조할 때 헷갈린다."""
    return f"{base.rstrip('/')}/{name}"


# 팩(형상관리 대상)에 속하는 경로. 도메인이 바뀌면 통째로 갈아끼운다.
_PACK_FILES = {
    "qa_index_file": "qa_index.json",
    "categories_file": "categories.json",
    "profile_file": "profile.json",
    "generated_qa_file": "generated_qa.json",
    "raw_docs_dir": "raw_docs",
}

# 런타임 산출물. 팩과 함께 옮기면 안 된다 — git 에 들어가서도 안 되고,
# 팩을 되돌린다고 질문 이력까지 되돌아가면 곤란하다.
_VAR_FILES = {
    "chroma_persist_dir": "chroma",
    "runtime_config_file": "runtime_config.json",
    "question_log_file": "question_log.jsonl",
    "question_embedding_file": "question_embeddings.jsonl",
    "question_feedback_file": "question_feedback.jsonl",
    "analytics_file": "analytics.json",
    "eval_report_file": "eval_report.json",
    "job_history_file": "job_history.json",
    "log_file": "logs/app.jsonl",
}


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
    # **Ollama 자신이 쓰는 환경변수와 이름이 같다.** 윈도우에 Ollama 를 설치하면
    # `OLLAMA_HOST=0.0.0.0` 이 시스템 환경변수로 박히는 경우가 있는데(바깥에서 접속을
    # 받으려는 설정), 그 값이 `.env` 를 이기고 들어와 **클라이언트가 `0.0.0.0` 으로 접속을
    # 시도한다.** 서버에게 `0.0.0.0` 은 "전부 받는다"지만 클라이언트에게는 갈 곳이 없는
    # 주소라, `ConnectionError` 만 나고 원인은 안 보인다(2026-10-06, Ollama 0.35 로
    # 올라간 뒤 겪음). 아래 `_fix_ollama_host` 가 쓸 수 있는 주소로 고쳐 준다.
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
    # 사고 과정에 **따로** 주는 출력 예산. `num_predict` 는 생각과 본문을 합쳐 세므로,
    # 추론을 켜면 생각하다 예산이 끝나 **본문이 비어 돌아온다**(2026-10-06: 생각 3,953자 ·
    # 본문 0자). 그래서 추론을 켠 호출에만 이만큼을 얹는다. 0 이면 얹지 않는다 —
    # 느린 기계에서 추론을 사실상 끄는 손잡이로도 쓴다.
    ollama_think_num_predict: int = 3072
    # `추론 과정 보기` 를 화면에 내줄지. **기본은 꺼짐**이다.
    #
    # 2026-10-06 에 실제 모델(qwen3.5:4b)로 재 보니, 같은 질문에 생각이 11,131자 / 14,629자로
    # 흔들리고 답변 시간이 12초 → 49~59초가 됐다. 넘치면 본문이 비어 와서 추론을 끄고 다시
    # 부른다(`StudioLlm.chat`) — 그러면 더 느려진다. 게다가 생각은 **영어로** 나온다.
    # 답변 품질이 눈에 띄게 좋아지지도 않았다. 더 빠른 기계나 덜 수다스러운 모델에서 다시
    # 켤 수 있도록 코드는 그대로 두고 손잡이만 내려 둔다.
    ai_reasoning: bool = False
    # 화면을 열었을 때 `AI 답변` 스위치를 켜 둘지. **기본은 꺼짐**이다.
    #
    # 켜면 검수된 답변 경로를 **건너뛴다** — AI 답변은 QA 인덱스를 보지 않고 문서를 읽어
    # 그 자리에서 정리한다(`app/api/chat_stream.py` 의 `_composed`). 그래서 켜 두면
    # 사람이 검수해 둔 답이 있어도 기본으로는 안 나가고, 매번 수 초~수십 초가 걸린다.
    # 자료는 많은데 QA 가 아직 적은 설치에서는 그 편이 나을 수 있어 손잡이로 뒀다.
    #
    # 운영(serve)에는 LLM 이 없어 모델 목록이 비므로, 켜 두어도 화면이 잠근다.
    ai_answer_default: bool = False

    # ── 팩과 런타임 디렉터리 ─────────────────────────────────────────────────
    # 도메인 데이터(문서·카테고리·검수 QA)가 있는 곳과, 돌면서 쌓이는 것을 가른다.
    #
    # **기본값이 둘 다 `./data` 인 이유.** 지금 설치는 이 둘이 한 폴더에 섞여 있고,
    # 그대로 두어야 기존 동작이 한 글자도 달라지지 않는다 (계획서 §9.2).
    # 새 도메인은 `PACK_DIR=./packs/mcp-manager`, `VAR_DIR=./var/mcp-manager` 로 띄운다.
    pack_dir: str = "./data"
    var_dir: str = "./data"

    # ── 프로젝트(= 팩) 여러 벌을 한 서버에 담을 때 ───────────────────────────
    # 한 설치가 'API Link' · 'API Manager' · 'MCP' 처럼 여러 도메인을 함께 서비스한다.
    # `packs/<project_id>/` 와 `var/<project_id>/` 가 한 프로젝트의 몫이고, 요청마다
    # 어느 프로젝트인지 정해 그 경로를 보게 한다(`app/core/projects.py`).
    #
    # **`PACK_DIR` 를 직접 준 설치는 지금까지와 똑같이 동작한다.** 프로젝트를 고르지 않은
    # 요청은 아래 뿌리를 보지 않고 `pack_dir`/`var_dir` 를 그대로 쓴다 — 단일 팩으로 띄운
    # 기존 설치와 테스트가 그대로 살아 있어야 한다.
    projects_dir: str = "./packs"
    projects_var_dir: str = "./var"

    # ── 제품 이름 (설치 단위) ────────────────────────────────────────────────
    # 프로젝트 이름(`profile.service_name`)은 **프로젝트마다 다르다** — 'API Link 도우미' ·
    # 'API Manager 도우미' · 'MCP 서버 도우미'. 그것을 제목으로 쓰면 제품에 이름이 없고,
    # 화면은 지금 보고 있는 프로젝트 이름만 보여준다.
    #
    # 이 값은 설치 전체에 하나다. 비워 두면 **지금까지와 똑같이** 프로젝트 이름이 제목이
    # 된다 — 단일 도메인으로 쓰는 설치는 제품명이 따로 필요 없다.
    app_name: str = ""
    # 로고 네모 안의 글자. 비우면 프로젝트 프로필의 조직명을 쓴다(지금 동작).
    # 네 글자까지만 들어간다 — 그보다 길면 네모를 벗어난다.
    app_logo: str = ""
    # 로고 **이미지**를 두는 곳. 관리자 화면에서 올리면 여기에 저장되고, 있으면 글자 대신
    # 그림이 나간다. 설치 단위라 팩(`packs/`)이 아니라 따로 둔다 — 팩을 갈아끼워도 회사
    # 로고는 그대로여야 하고, 팩을 반입할 때 남의 로고가 함께 따라오면 안 된다.
    brand_dir: str = "./data/brand"

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
    # 챗봇 `AI 답변` 스위치가 근거로 넘길 발췌 개수 (studio 전용).
    #
    # 화면 카드용(`related_docs_count`, 3)과 **일부러 다르다.** AI 에게는 넓게 주고 고르게
    # 하는 편이 낫고(4번째로 걸린 문서에 답이 있는 경우가 있다), 화면에는 AI 가 실제로 쓴
    # 것만 남긴다. 늘릴수록 프롬프트가 길어져 느려지고, 발췌 하나에 돌아가는 예산이 줄어든다.
    ai_answer_source_count: int = 8
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

    # ── 라이브 조회 (개발계획서 §4) ──────────────────────────────────────────
    # 사이트 조회 API 의 뿌리. 팩의 lookup.yaml 이 켜져 있을 때만 쓴다.
    lookup_api_base: str = "http://localhost:9050"
    # 사용자가 답을 기다리는 중이다. 이 안에 안 오면 문서 검색으로 내려간다 — 재시도하지 않는다.
    lookup_timeout_ms: int = 1500

    log_level: str = "INFO"
    log_file: str = "./data/logs/app.jsonl"


    @model_validator(mode="after")
    def _fix_ollama_host(self) -> "Settings":
        """`0.0.0.0` · 스킴 없는 값 · 포트 없는 값을 접속 가능한 주소로 고친다.

        막지 않고 **고친다.** 설정이 잘못됐다고 기동을 멈추면, Ollama 를 쓰지 않는 운영까지
        못 뜬다. 바로잡을 수 있는 값이라 조용히 바로잡고 쓰는 편이 낫다.
        """
        host = (self.ollama_host or "").strip()
        if not host:
            host = "http://127.0.0.1:11434"
        if "://" not in host:
            host = f"http://{host}"
        # 서버가 '전부 받는다'로 쓰는 주소들. 클라이언트에서는 자기 자신을 가리키게 한다.
        for bind_all in ("//0.0.0.0", "//[::]", "//::"):
            if bind_all in host:
                host = host.replace(bind_all, "//127.0.0.1")
        if host.count(":") < 2:          # 스킴의 ':' 뿐이면 포트가 없다
            host = f"{host.rstrip('/')}:11434"
        object.__setattr__(self, "ollama_host", host)
        return self

    @model_validator(mode="after")
    def _derive_paths(self) -> "Settings":
        """팩/var 기준으로 경로를 채운다.

        **직접 준 값이 이긴다.** 환경변수·`.env`·생성자 인자로 넘긴 것은 그대로 두고,
        건드리지 않은 것만 계산한다 — 그래서 기존 설치와 테스트의 경로 지정이 모두 살아 있다.
        `pack_dir`·`var_dir` 를 안 바꾸면 결과 문자열도 지금과 같다.
        """
        for field, name in _PACK_FILES.items():
            if field not in self.model_fields_set:
                object.__setattr__(self, field, _join(self.pack_dir, name))
        for field, name in _VAR_FILES.items():
            if field not in self.model_fields_set:
                object.__setattr__(self, field, _join(self.var_dir, name))
        return self


# 지금 요청이 어느 프로젝트의 것인가. 비어 있으면 '프로젝트를 고르지 않음' 이고, 그때는
# 기존처럼 `PACK_DIR`/`VAR_DIR` 설정을 그대로 쓴다.
#
# **왜 ContextVar 인가.** 경로를 읽는 곳이 11개 파일에 흩어져 있고 전부 `get_settings()` 를
# 거친다. 함수마다 project 인자를 받게 고치면 56개 엔드포인트와 그 아래 호출을 전부 손대야
# 하고, 한 군데라도 빠뜨리면 **다른 프로젝트의 파일을 조용히 읽는다.** 들어오는 자리에서
# 한 번 정하고 읽는 자리는 그대로 두는 편이 빠뜨릴 구멍이 없다.
_CURRENT_PROJECT: ContextVar[str] = ContextVar("current_project", default="")
# 그 프로젝트를 **누가** 정했는가. `request` 는 요청이 `?project=` 로 지목한 것,
# `default` 는 미들웨어가 기본값으로 채운 것이다.
#
# 둘을 가르는 이유: 공개 질문 경로는 프로젝트를 고르지 않은 '전체' 가 기본 상태이고, 그때는
# **가장 가까운 자료가 있는 프로젝트**를 찾아야 한다(`app/pipeline/scope.py`). 기본값으로
# 채워진 것을 '화면이 골랐다' 로 읽으면 빈 프로젝트에서 찾다 답을 못 찾는다 — 2026-10-06 에
# 실제로 그랬고, 오류가 아니라 "자료가 있는데 모른다" 로만 드러났다.
_PROJECT_SOURCE: ContextVar[str] = ContextVar("project_source", default="")


@lru_cache
def _base_settings() -> Settings:
    return Settings()


_PROJECT_SETTINGS: dict[tuple[str, str, str], Settings] = {}


def settings_for(project_id: str) -> Settings:
    """프로젝트 하나의 설정. **경로만** 그 프로젝트 것으로 바뀌고 나머지는 지금 설정 그대로다.

    `Settings()` 를 새로 만들지 않고 **지금 설정을 복사해 경로만 다시 계산한다.** 새로 만들면
    `.env` 를 다시 읽어서, 테스트가 격리해 둔 설정(임시 폴더·시험용 비밀번호)을 지나치고
    **실제 `packs/`·`var/` 를 건드린다.** 2026-08-17 에 테스트가 운영 데이터를 덮은 적이
    있어서, 이쪽은 처음부터 막아 둔다.

    캐시는 프로젝트마다 한 벌. 요청마다 만들면 경로 파생이 매번 돈다.
    """
    return _project_settings(get_settings(), project_id)


def _project_settings(base: Settings, project_id: str) -> Settings:
    key = (base.projects_dir, base.projects_var_dir, project_id)
    found = _PROJECT_SETTINGS.get(key)
    if found is None:
        data = base.model_dump()
        # 팩/var 에서 파생되는 경로는 지우고 다시 계산하게 둔다. 남겨 두면 '직접 준 값이
        # 이긴다' 규칙에 걸려 **앞 프로젝트의 경로가 그대로 따라온다.**
        for field in (*_PACK_FILES, *_VAR_FILES):
            data.pop(field, None)
        data["pack_dir"] = f"{base.projects_dir.rstrip('/')}/{project_id}"
        data["var_dir"] = f"{base.projects_var_dir.rstrip('/')}/{project_id}"
        found = Settings(_env_file=None, **data)
        _PROJECT_SETTINGS[key] = found
    return found


def current_project() -> str:
    return _CURRENT_PROJECT.get()


def use_project(project_id: str, *, source: str = "request"):
    """이 요청이 볼 프로젝트를 정한다. 돌려주는 토큰을 `reset_project()` 에 넘겨 되돌린다.

    :param source: `request` = 요청이 지목했다 · `default` = 미들웨어가 기본값으로 채웠다.
        기본값이 `request` 인 것은 의도다 — 코드가 직접 프로젝트를 세울 때(목록을 돌 때 등)는
        언제나 그 프로젝트를 보려는 뜻이다.
    """
    return (_CURRENT_PROJECT.set(project_id or ""),
            _PROJECT_SOURCE.set(source if project_id else ""))


def reset_project(token) -> None:
    project_token, source_token = token
    _CURRENT_PROJECT.reset(project_token)
    _PROJECT_SOURCE.reset(source_token)


def project_was_requested() -> bool:
    """요청이 프로젝트를 **직접 지목했는가.** 기본값으로 채워진 것은 거짓이다."""
    return bool(_CURRENT_PROJECT.get()) and _PROJECT_SOURCE.get() == "request"


def get_settings() -> Settings:
    """지금 요청이 봐야 할 설정.

    `settings_for()` 를 부르지 않는다 — 그쪽이 다시 이 함수를 불러 **무한 재귀**가 된다.
    둘 다 `_project_settings()` 를 쓰고, 뿌리를 누가 주느냐만 다르다.
    """
    project = _CURRENT_PROJECT.get()
    base = _base_settings()
    return _project_settings(base, project) if project else base


def _clear_settings_cache() -> None:
    """두 캐시를 함께 비운다.

    `get_settings` 는 더 이상 `lru_cache` 가 아니지만 `get_settings.cache_clear()` 를 부르는
    자리가 이미 있다(테스트 격리·임베더 비교 스크립트). 이름을 그대로 살려 둔다 —
    그쪽을 고치게 하면 **캐시를 비운 줄 알았는데 안 비워진** 상태로 돌아간다.
    """
    _base_settings.cache_clear()
    _PROJECT_SETTINGS.clear()


get_settings.cache_clear = _clear_settings_cache   # type: ignore[attr-defined]


def is_studio() -> bool:
    return get_settings().app_mode == "studio"
