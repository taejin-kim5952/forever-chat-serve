"""사용자 질문 로그 적재.

관리자 화면 탭 ①(질문 이력)이 그대로 읽고, 탭 ②(질문 분석)가 원재료로 쓴다.
**운영에서 계속 살아 있는 기능**이다 — 답변 생성은 스튜디오로 옮겼지만, 사용자가 무엇을
물었는지는 운영에서만 알 수 있다. 여기 쌓인 질문이 다음에 만들 QA를 정한다.

`data/logs/app.jsonl` 의 운영 이벤트 로그와 분리한 이유:
- 이벤트 로그는 포맷이 언제든 바뀌는 디버깅용이고, 이쪽은 분석이 의존하는 데이터다.
- 질문 단위로 조회·집계해야 하는데 이벤트 로그는 한 질문이 여러 줄로 흩어진다.

JSONL 추가 기록(append)만 하므로 동시 요청에도 줄이 섞이지 않는다(한 줄 단위 write).
"""

import base64
import io
import json
import struct
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logging import get_logger, log_event

logger = get_logger("core.question_log")

_LOCK = threading.Lock()


class QuestionLogEntry(BaseModel):
    log_id: str
    asked_at: str
    question: str
    lang: str = "ko"
    # 화면에서 고른 주제. 클러스터를 카테고리별로 묶을 때 쓴다.
    category_id: Optional[str] = None
    category_label: Optional[str] = None
    # answer | related_docs | unresolved — 화면 응답 상태와 같은 값이다.
    result_type: str = ""
    # 어떤 QA가 걸렸는지. 적중 횟수 집계와 "이 QA가 엉뚱한 질문에 걸린다" 추적에 쓴다.
    matched_qa_id: Optional[str] = None
    matched_question: Optional[str] = None
    similarity: Optional[float] = None
    response_time_ms: int = 0
    answer: Optional[str] = None
    source_doc_titles: list[str] = Field(default_factory=list)
    ticket_id: Optional[str] = None
    user_id: Optional[str] = None
    # 질문이 들어온 경로. 'web' = 실제 사용자, 'auto' = 내부 테스트/평가.
    # 테스트 질문이 실사용 통계에 섞이면 "무엇을 문서화할지" 판단이 왜곡된다.
    channel: str = "web"


# 실사용 통계에서 기본으로 빼는 채널.
TEST_CHANNELS = {"auto", "eval"}


def new_log_id() -> str:
    return f"q_{uuid.uuid4().hex[:12]}"


def new_ticket_id() -> str:
    """접수번호. 사용자가 담당자에게 그대로 불러 줄 값이라 읽기 쉬워야 한다."""
    return f"TCK-{time.strftime('%Y%m%d')}-{uuid.uuid4().hex[:5].upper()}"


def _path() -> Path:
    return Path(get_settings().question_log_file)


def append_question_log(entry: QuestionLogEntry) -> None:
    """질문 1건을 기록한다. 적재 실패가 답변 응답을 막아서는 안 된다."""
    try:
        path = _path()
        path.parent.mkdir(parents=True, exist_ok=True)
        line = entry.model_dump_json() + "\n"
        with _LOCK, io.open(path, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError as exc:
        log_event(logger, "question log append failed", error=str(exc))


def read_all_question_logs() -> list[QuestionLogEntry]:
    """파일 순서(오래된 것 먼저) 그대로 전부 읽는다."""
    path = _path()
    if not path.exists():
        return []

    entries: list[QuestionLogEntry] = []
    with io.open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(QuestionLogEntry(**json.loads(line)))
            except ValueError:
                # 포맷이 바뀌기 전 줄이 섞여 있어도 나머지는 살린다.
                continue
    return entries


def read_question_logs(
    limit: int = 100,
    offset: int = 0,
    result_type: str | None = None,
    category_id: str | None = None,
    keyword: str | None = None,
    since: str | None = None,
    include_test: bool = False,
    log_ids: set[str] | None = None,
) -> tuple[list[QuestionLogEntry], int]:
    """최근 질문부터 반환한다. `(항목, 필터 적용 후 전체 건수)`.

    PoC 규모(수천 건)라 파일 전체를 읽어 필터링한다. 건수가 커지면 SQLite 등으로 옮긴다.

    `log_ids` 는 다른 파일에서 고른 결과로 좁힐 때 쓴다(지금은 '👎만' 필터). 여기서 피드백
    파일을 직접 읽지 않는 이유는, 질문 이력이 다른 파일의 사정을 몰라야 하기 때문이다 —
    고르는 쪽이 id 집합만 넘긴다.
    """
    entries = read_all_question_logs()

    if log_ids is not None:
        entries = [e for e in entries if e.log_id in log_ids]
    if not include_test:
        entries = [e for e in entries if e.channel not in TEST_CHANNELS]
    if result_type:
        entries = [e for e in entries if e.result_type == result_type]
    if category_id:
        entries = [e for e in entries if e.category_id == category_id]
    if since:
        entries = [e for e in entries if e.asked_at >= since]
    if keyword:
        needle = keyword.lower()
        entries = [e for e in entries if needle in e.question.lower()]

    entries.reverse()   # 최근 질문 우선
    return entries[offset: offset + limit], len(entries)


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


# ─────────────────────────────────────────────────────────────────────────────
# 질문 임베딩 (클러스터링용)
#
# 답변 과정에서 이미 계산한 임베딩을 버리지 않고 함께 남긴다. 나중에 클러스터링 배치가
# 수천 건을 전부 다시 임베딩하는 단계를 통째로 생략할 수 있다(추가 비용 0).
# 특히 serve 모드에서는 이 재사용이 필수다 — 분석하겠다고 수천 건을 다시 임베딩하면
# GPU 없는 운영 서버에서 수십 분이 걸린다.
#
# 질문 로그와 **파일을 나눈** 이유: bge-m3 는 1024차원이라 JSON 실수 배열로 넣으면 한 줄이
# 14KB를 넘는다. 질문 로그는 관리자 화면 목록 조회에 그대로 읽히는 파일이라 그렇게 되면 못 쓴다.
# 여기서는 float32 로 묶어 base64 로 저장해 1건당 5.5KB 수준으로 줄인다. 두 파일은 log_id 로 연결된다.
# ─────────────────────────────────────────────────────────────────────────────


def _embedding_path() -> Path:
    return Path(get_settings().question_embedding_file)


def encode_embedding(vector: list[float]) -> str:
    return base64.b64encode(struct.pack(f"<{len(vector)}f", *vector)).decode("ascii")


def decode_embedding(encoded: str) -> list[float]:
    raw = base64.b64decode(encoded)
    return list(struct.unpack(f"<{len(raw) // 4}f", raw))


def append_question_embedding(log_id: str, vector: list[float]) -> None:
    """질문 임베딩 1건을 기록한다. 실패해도 답변 응답을 막지 않는다."""
    if not vector:
        return
    try:
        path = _embedding_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({"log_id": log_id, "dim": len(vector), "vec": encode_embedding(vector)}) + "\n"
        with _LOCK, io.open(path, "a", encoding="utf-8") as f:
            f.write(line)
    except (OSError, struct.error) as exc:
        log_event(logger, "question embedding append failed", log_id=log_id, error=str(exc))


def read_question_embeddings(log_ids: set[str] | None = None) -> dict[str, list[float]]:
    """`{log_id: 임베딩}`. `log_ids` 를 주면 그 건만 골라 읽는다(메모리 절약)."""
    path = _embedding_path()
    if not path.exists():
        return {}

    out: dict[str, list[float]] = {}
    with io.open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                log_id = entry["log_id"]
                if log_ids is not None and log_id not in log_ids:
                    continue
                # 같은 log_id 가 중복 기록돼도 마지막 값이 이긴다.
                out[log_id] = decode_embedding(entry["vec"])
            except (ValueError, KeyError, struct.error):
                continue
    return out
