from typing import Literal, Optional

from pydantic import BaseModel, Field

# 화면의 응답 상태와 1:1이다 — 퍼블 요청서 4번의 result_type.
ResultType = Literal["answer", "related_docs", "unresolved"]


# ─────────────────────────────────────────────────────────── 챗봇


class AskRequest(BaseModel):
    question: str
    lang: str = "ko"
    user_id: Optional[str] = None
    # 'web' = 실제 사용자, 'auto' = 내부 테스트. 테스트가 실사용 통계를 흐리지 않게 나눈다.
    channel: str = "web"
    # 화면에서 고른 주제. 라벨은 서버가 id 로 다시 찾으므로 받지 않는다.
    category_id: Optional[str] = None


class SourceDoc(BaseModel):
    doc_id: str = ""
    title: str
    section: str = ""
    url_or_ref: str = ""


class RelatedDoc(BaseModel):
    doc_id: str = ""
    chunk_id: str = ""
    title: str
    section: str = ""
    excerpt: str = ""
    url_or_ref: str = ""
    similarity: float = 0.0


class AskResponse(BaseModel):
    result_type: ResultType
    # result_type == 'answer' 일 때만 채워진다.
    answer: Optional[str] = None
    source_docs: list[SourceDoc] = Field(default_factory=list)
    # result_type == 'related_docs' 일 때만 채워진다.
    related_docs: list[RelatedDoc] = Field(default_factory=list)
    # result_type == 'unresolved' 일 때만 채워진다.
    message: Optional[str] = None
    ticket_id: Optional[str] = None

    similarity: Optional[float] = None
    matched_qa_id: Optional[str] = None
    response_time_ms: int = 0
    log_id: Optional[str] = None


class FeedbackRequest(BaseModel):
    """답변 말풍선의 👍/👎.

    `log_id` 로 어느 응답인지 잇는다. 질문 글자를 다시 받으면 같은 질문을 두 번 한 경우를
    구분할 수 없다. `vote=""` 는 취소이고, `reason` 은 👎 일 때만 의미가 있다.
    """

    log_id: str
    vote: Literal["up", "down", ""] = ""
    reason: Optional[str] = None


class DocChunkDetail(BaseModel):
    doc_id: str
    title: str
    section: str = ""
    text: str
    url_or_ref: str = ""


# ─────────────────────────────────────────────────────────── 카테고리


class CategoryOut(BaseModel):
    category_id: str
    name: str
    questions: list[str] = Field(default_factory=list)


class CategoryGroupOut(BaseModel):
    group_id: str
    group_name: str
    categories: list[CategoryOut] = Field(default_factory=list)


class CategoriesResponse(BaseModel):
    groups: list[CategoryGroupOut] = Field(default_factory=list)
    quick_category_ids: list[str] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────── 관리자 · 인증


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    username: str
    # 화면이 남은 시간을 계산해 만료 전에 안내할 수 있게 함께 준다.
    expires_at: int


class SessionResponse(BaseModel):
    authenticated: bool = False
    username: Optional[str] = None
    # 로그인 전에도 모드를 알아야 화면이 studio 전용 탭을 미리 정리할 수 있다.
    mode: Literal["serve", "studio"] = "serve"


# ─────────────────────────────────────────────────────────── 관리자 · QA


class QaSaveRequest(BaseModel):
    qa_id: Optional[str] = None
    question: str
    answer: str = ""
    variants: list[str] = Field(default_factory=list)
    category_id: Optional[str] = None
    source_doc_ids: list[str] = Field(default_factory=list)
    status: Literal["pending", "approved", "hold", "disabled"] = "pending"
    note: str = ""
    created_by: str = "human"


class QaBulkRequest(BaseModel):
    qa_ids: list[str]
    action: Literal["approve", "hold", "pending", "disable", "delete", "set_category"]
    category_id: Optional[str] = None


class QaBulkResponse(BaseModel):
    changed: int
    reindexed: int = 0


class QaPage(BaseModel):
    items: list[dict] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0
    summary: dict = Field(default_factory=dict)


class ReindexResponse(BaseModel):
    items: int = 0
    vectors: int = 0
    docs: dict = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────── 관리자 · 문서


class DocSummary(BaseModel):
    doc_id: str
    title: str
    category: str = ""
    updated: str = ""
    chunk_count: int = 0
    linked_qa_count: int = 0


class DocDetail(BaseModel):
    doc_id: str
    content: str


class DocSaveRequest(BaseModel):
    content: str


class DocCreateRequest(BaseModel):
    doc_id: str
    content: str


class DocSaveResponse(BaseModel):
    doc_id: str
    chunks_created: int
    status: str


class DocUploadItemResult(BaseModel):
    # 화면이 보낸 경로 그대로. 결과 표에서 사람이 자기 폴더의 파일을 찾아야 한다.
    path: str
    doc_id: str = ""
    title: str = ""
    status: Literal["created", "updated", "skipped", "failed"]
    chunks: int = 0
    # skipped/failed 의 사유. 화면이 문구를 만들지 않고 그대로 보여준다.
    reason: str = ""


class DocUploadResponse(BaseModel):
    items: list[DocUploadItemResult] = Field(default_factory=list)
    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0


# ─────────────────────────────────────────────────────── 관리자 · QA 생성(studio)


class StudioGenerateRequest(BaseModel):
    # docs      : 문서에서 질문·답변을 함께 만든다(기본).
    # category  : 그 카테고리의 추천 질문에 답을 붙인다.
    # questions : 화면이 준 질문 목록에 답을 붙인다(질문 분석 탭의 미해결 질문).
    source: Literal["docs", "category", "questions"] = "docs"
    # 빈 목록이면 전체 문서.
    doc_ids: list[str] = Field(default_factory=list)
    category_id: Optional[str] = None
    questions: list[str] = Field(default_factory=list)
    # 역할별 모델. 비우면 .env 의 OLLAMA_QUESTION_MODEL / OLLAMA_ANSWER_MODEL,
    # 그것도 비었으면 OLLAMA_LLM_MODEL 을 쓴다.
    question_model: Optional[str] = None
    answer_model: Optional[str] = None
    # 채점 모델. 비우면 채점하지 않는다(답변 모델로 자기 채점을 하느니 안 하는 편이 낫다).
    judge_model: Optional[str] = None
    # 역할을 나누기 전 화면이 쓰던 필드. 값이 오면 두 역할 모두에 적용한다.
    model: Optional[str] = None
    items_per_chunk: int = Field(2, ge=1, le=5)
    # 적중률은 사실상 변형 질문이 결정한다. 기본 10개 — 요청서 8~15 구간의 가운데.
    variant_count: int = Field(10, ge=0, le=20)
    # 한 번에 만들 최대 항목 수. 검수 가능한 양을 넘겨 만들면 초안만 쌓인다.
    max_items: int = Field(50, ge=1, le=500)


class AnalyticsOverrideRequest(BaseModel):
    # status = 묶음 상태(신규/검토됨/…), category = 주제 지정. 둘 다 사람이 판단한 값이라
    # 다시 분석해도 살아남아야 한다.
    kind: Literal["status", "category"]
    cluster_ids: list[str] = Field(default_factory=list)
    value: Optional[str] = None


class StudioVariantRequest(BaseModel):
    question: str
    count: int = Field(10, ge=1, le=20)
    model: Optional[str] = None


class StudioApplyRequest(BaseModel):
    # 비우면 전체. 상태는 받지 않는다 — 생성 결과는 언제나 pending 으로만 들어간다.
    draft_ids: list[str] = Field(default_factory=list)
    # 채점 기준. 비우면 .env 의 QA_APPLY_MIN_SCORE. 채점하지 않은 배치에는 적용되지 않는다.
    min_score: Optional[int] = Field(default=None, ge=0, le=5)


# ─────────────────────────────────────────────────────────── 관리자 · 이력/설정


class QuestionLogPage(BaseModel):
    items: list = Field(default_factory=list)
    total: int = 0
    limit: int = 100
    offset: int = 0


class AdminSettings(BaseModel):
    qa_match_threshold: float = Field(ge=0.0, le=1.0)
    related_docs_floor: float = Field(ge=0.0, le=1.0)
    related_docs_count: int = Field(ge=1, le=10)
    qa_top_k: int = Field(ge=1, le=50)
    doc_top_k: int = Field(ge=1, le=50)


# ─────────────────────────────────────────────────────── 관리자 · 작업 현황판


class RunningJob(BaseModel):
    key: str
    title: str
    stage: str = ""
    percent: int = 0
    done: int = 0
    total: int = 0
    # "질문 A · 답변 B · 채점 C" 처럼 서버가 만든 한 줄. 화면은 그대로 출력한다.
    model: str = ""
    started_at: str = ""
    stopping: bool = False
    tab: str = ""


class JobStep(BaseModel):
    label: str
    tab: str


class RecentJob(BaseModel):
    key: str
    title: str
    status: Literal["done", "stopped", "failed"]
    finished_at: str = ""
    summary: str = ""
    elapsed: str = ""
    tab: str = ""
    # 다음에 할 일. **서버가 정한다** — 화면이 작업 종류를 보고 추측하면 순서를 바꿀 때마다
    # 둘이 다른 것을 안내한다. null 이면 화면이 버튼을 감춘다.
    next: Optional[JobStep] = None


class JobsResponse(BaseModel):
    # 실행 중인 배치는 한 번에 하나뿐이다. 없으면 화면이 블록을 통째로 숨긴다.
    running: Optional[RunningJob] = None
    recent: list[RecentJob] = Field(default_factory=list)


class ModeResponse(BaseModel):
    mode: Literal["serve", "studio"]
    embed_model: str
    llm_model: Optional[str] = None
    qa_serving: int = 0
    qa_vectors: int = 0
    # 아래는 화면이 **읽기 전용으로 보여주는** 값이다. `.env` 에서 오고 기동할 때 고정되므로
    # (`@lru_cache`) 관리자 화면에서 고칠 수 없다. 입력칸으로 두면 고칠 수 있다고 오해한다.
    # serve 에서는 LLM을 올리지 않으므로 비어 온다.
    question_model: Optional[str] = None
    answer_model: Optional[str] = None
    # 비어 있으면 채점하지 않는다는 뜻이다.
    judge_model: Optional[str] = None
    num_ctx: int = 0
    num_predict: int = 0
    # 문서 작성 안내(⑤ '가이드 문서 작성 형식')가 보여주는 길이 기준. serve 에서도 온다 —
    # 문서를 왜 못 찾는지 확인할 때 운영에서도 봅니다.
    embed_warn_chars: int = 0
