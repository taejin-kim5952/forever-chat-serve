"""QA 인덱스 저장소 — 이 서비스가 답하는 내용 전부.

`data/qa_index.json` 파일 하나가 원본이다. 벡터 인덱스(Chroma)는 이 파일에서 **파생**되며,
언제든 버리고 다시 만들 수 있다. 이 방향을 지키는 이유:

- 운영 배포가 파일 복사 한 번으로 끝난다. 폐쇄망에 DB를 세우지 않아도 된다.
- 검수 결과를 사람이 읽고 diff 로 확인할 수 있다. 벡터는 그게 안 된다.
- 임베딩 모델을 바꿔도 답변은 그대로다 — 재색인만 하면 된다.

### 상태(status)가 하는 일

`approved` 인 항목만 벡터 인덱스에 올라간다. 즉 **검수를 통과한 답변만 사용자에게 나간다.**
`pending`(검수대기) / `hold`(보류) / `disabled`(미사용)는 파일에는 남지만 검색되지 않는다.
AI가 만든 초안이 검수 없이 사용자에게 새어 나가는 경로를 아예 없애기 위한 구조다.
"""

import threading
import time
import uuid
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.jsonstore import read_json, write_json_atomic
from app.core.logging import get_logger, log_event

logger = get_logger("qa.store")

_LOCK = threading.RLock()

QaStatus = Literal["pending", "approved", "hold", "disabled"]

# 사용자에게 나가는 상태. 여기 없는 상태는 벡터 인덱스에 올리지 않는다.
SERVING_STATUSES: set[str] = {"approved"}


class QaItem(BaseModel):
    qa_id: str
    # 대표 질문. 관리자 목록에 보이는 제목이자 변형 질문의 기준이다.
    question: str
    # 사용자에게 그대로 나가는 답변(마크다운). 화면은 굵게/목록/코드/문단만 렌더한다.
    answer: str = ""
    # 같은 답변을 가리키는 다른 표현들. 적중률은 사실상 이 목록이 결정한다.
    variants: list[str] = Field(default_factory=list)
    category_id: Optional[str] = None
    source_doc_ids: list[str] = Field(default_factory=list)
    status: QaStatus = "pending"
    # 이 QA가 실제로 몇 번 걸렸는지. 검수 우선순위를 정하는 근거다.
    hit_count: int = 0
    created_at: str = ""
    updated_at: str = ""
    # 'ai' = 스튜디오에서 생성, 'human' = 사람이 직접 작성.
    created_by: str = "ai"
    model_used: Optional[str] = None
    # 검수 메모. 보류한 이유를 남겨두지 않으면 다음 사람이 같은 판단을 반복한다.
    note: str = ""

    def match_texts(self) -> list[str]:
        """벡터 인덱스에 올릴 문장들 — 대표 질문 + 변형 질문(중복·공백 제거)."""
        seen: dict[str, None] = {}
        for text in [self.question, *self.variants]:
            cleaned = text.strip()
            if cleaned:
                seen.setdefault(cleaned, None)
        return list(seen)


class QaIndexFile(BaseModel):
    items: list[QaItem] = Field(default_factory=list)


def new_qa_id() -> str:
    return f"qa_{uuid.uuid4().hex[:12]}"


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _path() -> Path:
    return Path(get_settings().qa_index_file)


def load_qa() -> list[QaItem]:
    data = read_json(_path())
    if data is None:
        return []
    try:
        return QaIndexFile(**data).items
    except ValueError as exc:
        # 여기서 조용히 빈 목록을 돌려주면 챗봇이 "답변이 하나도 없는" 상태로 정상 동작하는
        # 것처럼 보인다. 그건 장애를 숨기는 것이므로 반드시 남긴다.
        log_event(logger, "qa index file unreadable", path=str(_path()), error=str(exc))
        return []


def save_qa(items: list[QaItem]) -> None:
    with _LOCK:
        write_json_atomic(_path(), QaIndexFile(items=items).model_dump_json(indent=2))


def get_item(qa_id: str) -> QaItem | None:
    return next((i for i in load_qa() if i.qa_id == qa_id), None)


def serving_items(items: list[QaItem] | None = None) -> list[QaItem]:
    """사용자에게 나갈 수 있는 항목만. 답변이 비어 있으면 상태와 무관하게 제외한다."""
    pool = load_qa() if items is None else items
    return [i for i in pool if i.status in SERVING_STATUSES and i.answer.strip()]


def upsert_item(item: QaItem) -> QaItem:
    with _LOCK:
        items = load_qa()
        item.updated_at = now_iso()
        for idx, existing in enumerate(items):
            if existing.qa_id == item.qa_id:
                # hit_count 는 답변과 별개로 운영에서 쌓이는 값이라 편집 저장이 덮어쓰면 안 된다.
                item.hit_count = existing.hit_count
                item.created_at = existing.created_at or now_iso()
                items[idx] = item
                break
        else:
            item.created_at = item.created_at or now_iso()
            items.append(item)
        save_qa(items)
    return item


def delete_items(qa_ids: set[str]) -> int:
    with _LOCK:
        items = load_qa()
        remaining = [i for i in items if i.qa_id not in qa_ids]
        removed = len(items) - len(remaining)
        if removed:
            save_qa(remaining)
    return removed


def set_status(qa_ids: set[str], status: QaStatus) -> int:
    with _LOCK:
        items = load_qa()
        changed = 0
        for item in items:
            if item.qa_id in qa_ids and item.status != status:
                item.status = status
                item.updated_at = now_iso()
                changed += 1
        if changed:
            save_qa(items)
    return changed


def set_category(qa_ids: set[str], category_id: str | None) -> int:
    with _LOCK:
        items = load_qa()
        changed = 0
        for item in items:
            if item.qa_id in qa_ids:
                item.category_id = category_id
                item.updated_at = now_iso()
                changed += 1
        if changed:
            save_qa(items)
    return changed


def bump_hit_count(qa_id: str) -> None:
    """적중 1건 기록. 답변 응답 경로에서 불리므로 실패해도 사용자 응답을 막지 않는다.

    답변마다 파일 전체를 다시 쓰는 것은 낭비로 보이지만, 사내 트래픽(하루 수백 건)에서
    수백 KB 파일 쓰기는 무시할 만하고, 별도 카운터 저장소를 두면 배포 대상 파일이 하나 더
    늘어난다. 건수가 늘면 그때 분리한다.
    """
    try:
        with _LOCK:
            items = load_qa()
            for item in items:
                if item.qa_id == qa_id:
                    item.hit_count += 1
                    save_qa(items)
                    return
    except OSError as exc:
        log_event(logger, "hit count update failed", qa_id=qa_id, error=str(exc))


def summary() -> dict:
    items = load_qa()
    return {
        "total": len(items),
        "approved": sum(1 for i in items if i.status == "approved"),
        "pending": sum(1 for i in items if i.status == "pending"),
        "hold": sum(1 for i in items if i.status == "hold"),
        "disabled": sum(1 for i in items if i.status == "disabled"),
        "variants": sum(len(i.variants) for i in items),
        "serving": len(serving_items(items)),
    }
