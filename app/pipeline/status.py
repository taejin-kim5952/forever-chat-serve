"""진행 현황 집계 — 콘텐츠 파이프라인의 어디가 막혀 있는지 한 번에 내려준다.

관리자 화면의 첫 화면(`#panel_flow`)이 쓰는 유일한 데이터원이다.

### 왜 한 번에 내려주나 ★

칸이 여섯이라 칸마다 부르면 화면 하나 여는 데 요청이 여섯 번이다. 게다가 요청 사이에
QA가 승인되면 **칸끼리 앞뒤가 안 맞는 화면**이 나온다(대기 12건인데 서비스 중은 승인 전
숫자). 한 번에 읽어서 같은 시점의 값으로 맞춘다.

### 여기서 새로 세지 않는다

숫자는 전부 이미 있는 것을 모으기만 한다 — `qa_store.summary()`, 초안 파일, 문서 청크 수,
마지막 평가 리포트, 런타임 설정. 집계 로직을 여기서 다시 짜면 관리자 화면의 각 탭이
보여주는 값과 진행 현황의 값이 조용히 어긋난다.

### 병목은 서버가 정한다

"지금 할 일"을 화면이 숫자를 보고 판단하게 두면, 판단 기준이 화면과 서버 두 곳에 생긴다.
`todo` 필드로 **서버가 하나만 지정해서** 내려준다 — 화면은 그대로 그린다
(`app/pipeline/retrieve.py` 의 `result_type` 과 같은 원칙이다).
"""

import time
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.core.config import get_settings, is_studio
from app.core.runtime_config import load_runtime_config
from app.qa import store as qa_store
from app.studio import runner
from app.studio.evaluate import load_last_report

# 오매칭이 이 값을 넘으면 '주의'. 못 찾는 것보다 **틀린 답이 나가는 것**이 나쁘다는
# 판단(app/studio/evaluate.py)에 맞춰 낮게 잡았다.
MISMATCH_WARN_PERCENT = 5.0

# 최근 증가분을 셀 기간.
RECENT_DAYS = 7

StepState = Literal["ok", "warn", "todo", "off"]
TodoKind = Literal["review", "apply", "generate", "quality", "docs", "clear"]


class Step(BaseModel):
    """상태판 한 칸. 화면은 이 값을 그대로 그린다."""

    key: str
    value: int | float = 0
    # 큰 숫자 아래 보조 한 줄. 서버가 문장으로 만들어 내려준다.
    note: str = ""
    state: StepState = "ok"
    # 칸 아래 버튼 문구. **상태에 따라 달라지므로 서버가 정한다** — 초안이 12건 쌓여 있는데
    # 버튼이 `생성 시작` 이면 "또 만들라는 건가"가 된다. 비우면 화면의 기본 문구를 쓴다.
    action: str = ""


class FlowSummary(BaseModel):
    """단계 사이에서 걸러져 나간 것. 생성 이력이 없으면 `has_run=False`."""

    has_run: bool = False
    generated_at: str = ""
    documents: int = 0
    questions_made: int = 0
    dropped_language: int = 0
    dropped_ungrounded: int = 0
    low_score: int = 0
    pending: int = 0
    approved: int = 0


class Todo(BaseModel):
    kind: TodoKind = "clear"
    message: str = ""
    # 화면이 이동할 곳. 사이드바의 `data-tab` 값과 같다.
    tab: Optional[str] = None


class PipelineStatus(BaseModel):
    mode: str = "serve"
    checked_at: str = ""
    steps: list[Step] = Field(default_factory=list)
    todo: Todo = Field(default_factory=Todo)
    summary: FlowSummary = Field(default_factory=FlowSummary)


# ─────────────────────────────────────────────────────────────── 조각별 집계


def _document_counts() -> tuple[int, int]:
    """`(문서 수, 미색인 수)`.

    색인 여부는 청크 수로 본다 — 0이면 벡터 저장소에 없다는 뜻이다. 문서를 넣고 색인을
    안 한 상태가 흔한데, 그러면 그 문서로는 아무것도 검색되지 않는다.
    """
    from app.pipeline.retrieve import get_retriever

    paths = sorted(Path(get_settings().raw_docs_dir).glob("*.md"))
    index = get_retriever().doc_index
    unindexed = sum(1 for p in paths if index.count_chunks(p.stem) == 0)
    return len(paths), unindexed


def _recent_approved(items: list[qa_store.QaItem]) -> int:
    """최근 `RECENT_DAYS` 일 안에 수정된 approved 건수.

    승인 시각을 따로 두지 않으므로 `updated_at` 으로 본다. 승인이 마지막 수정인 경우가
    대부분이라 실용적으로 맞는다. 정확한 승인 이력이 필요해지면 그때 필드를 늘린다.
    """
    cutoff = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() - RECENT_DAYS * 86400))
    return sum(1 for i in items if i.status == "approved" and i.updated_at >= cutoff)


def _pick_todo(
    *, documents: int, pending: int, unapplied: int, mismatch: float | None, studio: bool,
) -> Todo:
    """막힌 곳 **하나만** 고른다. 앞 단계일수록 먼저다 — 뒤를 풀어도 앞이 막혀 있으면 안 흐른다."""
    if documents == 0:
        return Todo(kind="docs", message="문서가 없습니다. 먼저 문서를 넣어 주세요.", tab="docs")
    if pending:
        return Todo(
            kind="review",
            message=f"검수 대기 {pending}건. 승인해야 사용자에게 나갑니다.",
            tab="review",
        )
    if unapplied:
        return Todo(
            kind="apply", message=f"초안 {unapplied}건이 반영을 기다립니다.", tab="generate",
        )
    if mismatch is not None and mismatch > MISMATCH_WARN_PERCENT:
        return Todo(
            kind="quality",
            message=f"검색 오매칭이 {mismatch}%입니다. 변형 질문이나 임계값을 손봐야 합니다.",
            tab="eval",
        )
    if studio:
        return Todo(
            kind="generate", message="문서에서 QA를 생성할 수 있습니다.", tab="generate",
        )
    return Todo(kind="clear", message="막힌 곳이 없습니다.")


# ─────────────────────────────────────────────────────────────────── 진입점


def collect() -> PipelineStatus:
    studio = is_studio()
    config = load_runtime_config()
    items = qa_store.load_qa()
    counts = qa_store.summary()

    documents, unindexed = _document_counts()
    draft_file = runner.read_draft_file()
    unapplied = sum(1 for d in draft_file.drafts if not d.applied_qa_id)
    report = load_last_report()
    mismatch = report.mismatch_rate if report else None

    pending, approved, hold = counts["pending"], counts["approved"], counts["hold"]
    low_score = draft_file.stats.low_score

    # ── ① 문서
    step_docs = Step(
        key="documents", value=documents,
        note=f"미색인 {unindexed}건" if unindexed else "모두 색인됨",
        state="warn" if unindexed else "ok",
    )
    # ── ② 초안 (생성은 studio 전용)
    step_drafts = Step(
        key="drafts", value=unapplied,
        note=draft_file.generated_at.replace("T", " ")[:16] if draft_file.generated_at
        else "생성 이력 없음",
        state="off" if not studio else "ok",
        # 쌓인 초안이 있으면 할 일은 '생성'이 아니라 '검토'다. 같은 화면으로 가지만
        # 문구가 다르면 무엇을 하러 가는지가 달라진다.
        action=f"초안 {unapplied}건 보기" if unapplied else "생성 시작",
    )
    # ── ③ 검수 대기
    parts = [f"보류 {hold}건"] if hold else []
    if low_score:
        parts.append(f"4점 미만 {low_score}건 제외됨")
    step_pending = Step(
        key="pending", value=pending, note=" · ".join(parts) or "대기 없음", state="ok",
    )
    # ── ④ 서비스 중
    step_approved = Step(
        key="approved", value=approved,
        note=f"최근 {RECENT_DAYS}일 +{_recent_approved(items)}", state="ok",
    )
    # ── ⑤ 품질
    step_quality = Step(
        key="quality", value=mismatch if mismatch is not None else 0.0,
        note=report.run_at.replace("T", " ")[:16] if report else "측정 이력 없음",
        state=("off" if not studio and report is None
               else "warn" if mismatch is not None and mismatch > MISMATCH_WARN_PERCENT
               else "ok"),
    )
    # ── ⑥ 임계값
    step_threshold = Step(
        key="threshold", value=config.qa_match_threshold,
        note=f"문서 {config.related_docs_floor}", state="ok",
    )

    todo = _pick_todo(
        documents=documents, pending=pending, unapplied=unapplied,
        mismatch=mismatch, studio=studio,
    )
    # 강조는 한 칸만. 여섯 칸이 다 빨가면 아무것도 안 읽힌다.
    steps = [step_docs, step_drafts, step_pending, step_approved, step_quality, step_threshold]
    highlight = {"docs": "documents", "apply": "drafts", "generate": "drafts",
                 "review": "pending", "quality": "quality"}.get(todo.kind)
    for step in steps:
        if step.key == highlight and step.state != "off":
            step.state = "todo"

    stats = draft_file.stats
    return PipelineStatus(
        mode="studio" if studio else "serve",
        checked_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        steps=steps,
        todo=todo,
        summary=FlowSummary(
            has_run=bool(draft_file.generated_at),
            generated_at=draft_file.generated_at,
            documents=documents,
            questions_made=stats.questions_made,
            dropped_language=stats.dropped_language,
            dropped_ungrounded=stats.dropped_ungrounded,
            low_score=stats.low_score,
            pending=pending,
            approved=approved,
        ),
    )
