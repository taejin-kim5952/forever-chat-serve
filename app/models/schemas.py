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


class ModeResponse(BaseModel):
    mode: Literal["serve", "studio"]
    embed_model: str
    llm_model: Optional[str] = None
    qa_serving: int = 0
    qa_vectors: int = 0
