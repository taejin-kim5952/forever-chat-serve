"""스튜디오에서 만든 QA를 서버로 들여온다 (요청서 11).

### 왜 필요한가

답변을 **만드는 곳과 답하는 곳이 다르다.** 운영 서버에는 GPU가 없어 LLM을 올리지 않으므로
QA는 사내 작업 PC(studio)에서 미리 만들고, 서버는 그것을 검수해서 내보내기만 한다.
검수·승인 화면은 serve 에서도 동작한다 — 빠져 있던 것은 "들여오는 길" 하나였다.

이 모듈은 **운영 경로**다. `app/studio/` 를 import 하지 않는다.

### 지키는 것 셋

1. **들여온 QA는 무조건 `pending`.** 파일에 `approved` 라고 적혀 있어도 대기로 들어온다.
   검수를 거치지 않은 답변이 사용자에게 나가는 경로를 만들지 않는다 — 이 제품의 전제다.
2. **운영에서 쌓인 값은 덮지 않는다.** `hit_count` 는 서버 것을 유지하고(`upsert_item`),
   `qa_id` 도 서버 것을 쓴다. 사용자 신고는 `qa_id` 로 이어져 있어 덮어도 남는다.
3. **미리보기와 실제 반영이 같은 판단을 쓴다.** 화면이 "덮어씀 3건"을 보여준 뒤 실제로는
   다르게 동작하면 확인 절차가 의미를 잃는다. 두 경로가 `_lookup()` 하나를 공유한다.

### 화면과 주고받는 모양

미리보기 응답의 항목이 **그대로 다시 올라온다.** 그래서 답변·변형 질문까지 실어 보낸다 —
화면이 파일을 들고 있다가 다시 조립하게 하면, 파일 형식이 바뀔 때마다 화면을 고쳐야 한다.
"""

import json
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.core.categories import load_categories
from app.qa import store as qa_store

# 미리보기 상태 — 새로 들어옴 / 이미 있음(덮어쓰기 대상) / 건너뜀
PreviewStatus = Literal["new", "over", "skip"]
# 반영 결과 — 추가 / 덮음 / 건너뜀 / 실패
ResultStatus = Literal["created", "updated", "skipped", "failed"]


class ImportItem(BaseModel):
    """QA 한 건. 파일에서 읽은 값과 서버가 붙인 판단이 함께 실린다."""

    qa_id: Optional[str] = None
    question: str = ""
    answer: str = ""
    variants: list[str] = Field(default_factory=list)
    category_id: Optional[str] = None
    source_doc_ids: list[str] = Field(default_factory=list)
    # 생성 때 판정 모델이 매긴 점수. 0 은 '나쁨'이 아니라 **'판정하지 않음'** 이다.
    score: int = 0
    judge_model: str = ""
    judge_reason: str = ""
    model_used: Optional[str] = None

    # ── 서버가 붙이는 값 ──
    status: PreviewStatus = "new"
    # 화면 표에 그대로 나가는 주제 이름. 화면이 id로 다시 찾게 하면 목록을 통째로 들고 있어야 한다.
    category_label: str = ""
    reason: str = ""


class PreviewResponse(BaseModel):
    items: list[ImportItem] = Field(default_factory=list)


class ResultRow(BaseModel):
    question: str = ""
    status: ResultStatus
    reason: str = ""
    qa_id: str = ""


class ImportResponse(BaseModel):
    items: list[ResultRow] = Field(default_factory=list)


class ImportRequest(BaseModel):
    items: list[ImportItem] = Field(default_factory=list)
    # 끈 상태가 기본. 켜도 적중 횟수 같은 운영 수치는 서버 것이 유지된다.
    overwrite: bool = False


# ─────────────────────────────────────────────────────────────────────── 읽기


def read_items(data: object) -> list[ImportItem]:
    """파일 내용에서 QA 목록을 꺼낸다.

    두 가지 모양을 모두 받는다 — 검수자가 어느 파일을 올릴지 알고 있을 필요가 없어야 한다.

        {"drafts": [...]}   생성 초안 (data/generated_qa.json)
        {"items":  [...]}   QA 인덱스 (data/qa_index.json)
        [...]               목록만 있는 파일

    모르는 필드는 버린다. 스튜디오 쪽 파일 형식이 늘어나도 여기서 막히지 않게 한다.
    """
    if isinstance(data, dict):
        raw = data.get("drafts") or data.get("items") or []
    elif isinstance(data, list):
        raw = data
    else:
        raw = []

    # `status` 는 파일에도 있고(`qa_index.json` 의 approved/pending) 여기서도 쓰지만 **뜻이 다르다.**
    # 파일 쪽 값은 어차피 무시한다 — 무엇이 적혀 있든 검수 대기로 들어온다. 그대로 읽으면
    # `approved` 가 미리보기 상태값과 충돌해 파일 전체를 못 읽는다(실제로 겪음).
    server_side = {"status", "category_label", "reason"}
    known = set(ImportItem.model_fields) - server_side

    items: list[ImportItem] = []
    for entry in raw:
        if isinstance(entry, dict):
            items.append(ImportItem(**{k: v for k, v in entry.items() if k in known}))
    return items


def parse_file(raw: bytes) -> list[ImportItem]:
    """올린 파일을 읽는다. 못 읽으면 `ValueError` — 화면이 그대로 사용자에게 보여준다."""
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("UTF-8 로 저장된 파일만 읽을 수 있습니다.") from exc
    try:
        return read_items(json.loads(text))
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 형식이 아닙니다 ({exc.lineno}번째 줄).") from exc


# ─────────────────────────────────────────────────────────────────── 판단·반영


def _category_labels() -> dict[str, str]:
    store = load_categories()
    return {c.category_id: c.name for g in store.groups for c in g.categories}


class _Lookup:
    """서버에 이미 있는지 찾는 규칙. 미리보기와 반영이 **같은 것**을 써야 한다.

    두 가지로 본다.

    - `qa_id` 가 서버에 있으면 그 항목
    - 없으면 **대표 질문**으로 찾는다. 스튜디오에서 다시 생성하면 id가 새로 붙는데
      질문이 같으면 사람이 보기엔 같은 항목이다. id만 보면 같은 질문이 두 벌 쌓인다.
    """

    def __init__(self) -> None:
        items = qa_store.load_qa()
        self.by_id = {i.qa_id: i for i in items}
        self.by_question = {qa_store.normalize_question(i.question): i for i in items}

    def find(self, item: ImportItem) -> qa_store.QaItem | None:
        return self.by_id.get(item.qa_id or "") or self.by_question.get(
            qa_store.normalize_question(item.question)
        )


def preview(items: list[ImportItem]) -> PreviewResponse:
    """올리기 **전에** 무엇이 어떻게 될지 표시해 돌려준다.

    되돌리기가 없어서 이 단계가 필수다. 덮어쓰기 여부는 붙이지 않는다 — 화면이 체크박스를
    켜고 끌 때마다 서버를 다시 부르지 않아도 되도록, `over` 로 표시만 하고 최종 선택은
    화면이 한다. 실제 반영에서 서버가 다시 판단하므로 어긋나지 않는다.
    """
    lookup = _Lookup()
    labels = _category_labels()
    out: list[ImportItem] = []
    seen: set[str] = set()

    for item in items:
        item.question = item.question.strip()
        item.category_label = labels.get(item.category_id or "", "")

        if not item.question:
            out.append(item.model_copy(update={"status": "skip", "reason": "대표 질문이 비어 있습니다"}))
            continue

        key = qa_store.normalize_question(item.question)
        if key in seen:
            out.append(item.model_copy(update={"status": "skip", "reason": "파일 안에 같은 질문이 두 번 있습니다"}))
            continue
        seen.add(key)

        found = lookup.find(item)
        if found is None:
            out.append(item.model_copy(update={"status": "new", "reason": ""}))
        else:
            out.append(item.model_copy(update={"status": "over", "reason": "이미 있는 항목입니다"}))

    return PreviewResponse(items=out)


def apply(items: list[ImportItem], overwrite: bool) -> ImportResponse:
    """실제로 반영한다.

    화면이 이미 걸러서 보내지만 **서버가 다시 판단한다.** 미리보기와 반영 사이에 다른
    사람이 승인했을 수도 있고, 화면을 거치지 않는 경로(`scripts/push_qa.py`)도 있다.
    """
    lookup = _Lookup()
    rows: list[ResultRow] = []
    seen: set[str] = set()

    for item in items:
        question = item.question.strip()
        if not question:
            rows.append(ResultRow(question="(대표 질문 없음)", status="skipped",
                                  reason="대표 질문이 비어 있습니다"))
            continue

        key = qa_store.normalize_question(question)
        if key in seen:
            rows.append(ResultRow(question=question, status="skipped",
                                  reason="파일 안에 같은 질문이 두 번 있습니다"))
            continue
        seen.add(key)

        found = lookup.find(item)
        if found is not None and not overwrite:
            rows.append(ResultRow(question=question, status="skipped", reason="이미 있습니다",
                                  qa_id=found.qa_id))
            continue

        saved = qa_store.upsert_item(qa_store.QaItem(
            # 서버 id를 유지해야 사용자 신고·질문 이력이 계속 이어진다.
            qa_id=found.qa_id if found else (item.qa_id or qa_store.new_qa_id()),
            question=question,
            answer=item.answer,
            variants=item.variants,
            category_id=item.category_id,
            source_doc_ids=item.source_doc_ids,
            # ★ 파일이 뭐라고 적었든 검수 대기로 들어온다.
            status="pending",
            created_by="ai",
            model_used=item.model_used,
            score=item.score,
            judge_model=item.judge_model,
            judge_reason=item.judge_reason,
            # 덮어쓸 때도 검수 메모는 서버 것을 남긴다 — 보류한 이유가 사라지면
            # 다음 사람이 같은 판단을 반복한다.
            note=found.note if found else "",
        ))
        # 방금 넣은 것을 다음 항목이 다시 '새로'로 보지 않게 갱신한다.
        lookup.by_id[saved.qa_id] = saved
        lookup.by_question[key] = saved

        rows.append(ResultRow(question=question, qa_id=saved.qa_id,
                              status="updated" if found else "created", reason="검수 대기"))

    return ImportResponse(items=rows)
