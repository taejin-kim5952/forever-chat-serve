"""질문 로그 분석 — 비슷한 질문을 묶어 "무엇을 다음 QA로 만들지" 고르게 한다(관리자 탭 ②).

이 화면이 이 프로젝트의 순환을 닫는다.

```
사용자 질문 → 이력 → [여기] 비슷한 질문끼리 묶기 → 답이 없는 묶음 발견
                                                        ↓
                                          QA 생성(탭 ⑥) → 검수(탭 ④) → 답변
```

### LLM을 쓰지 않는다 ★

운영 서버에는 GPU가 없다. 그래서 대표 질문도, 요약도 **계산으로** 만든다.

- 대표 질문: 군집 중심에 가장 가까운 **실제 질문**. 없는 문장을 지어내지 않는다.
- 요약: 묶인 표현이 몇 가지인지 세어 그대로 적는다.

이전 프로젝트는 여기서 LLM 요약을 붙일 수 있었지만(스튜디오 전용이었다), 이 화면은 운영에서
돌아야 한다. 묶음이 60개면 LLM 호출도 60번이고, CPU에서는 한 번에 끝나지 않는다.

### 임베딩을 다시 만들지 않는다 ★

답변할 때 이미 계산해 `data/question_embeddings.jsonl` 에 남겨 둔 벡터를 그대로 쓴다.
수천 건을 다시 임베딩하면 GPU 없는 운영에서 수십 분이 걸린다 — 이 재사용이 없으면
분석 기능 자체가 운영에서 못 돈다.

### 운영자가 지정한 값은 다시 분석해도 살아남는다

상태(검토됨·QA 생성됨 등)와 주제 지정은 사람이 판단한 결과다. 재분석 때마다 초기화되면
아무도 상태를 지정하지 않게 된다. `overrides` 로 따로 보관하고 매번 다시 얹는다.
"""

import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from app.core.categories import load_categories
from app.core.config import get_settings
from app.core.jsonstore import read_json, write_json_atomic
from app.core.logging import get_logger, log_event
from app.core.question_log import (
    TEST_CHANNELS,
    QuestionLogEntry,
    read_all_question_logs,
    read_question_embeddings,
)
from app.core.similarity import cosine_similarity

logger = get_logger("pipeline.analytics")

_LOCK = threading.Lock()

# 화면 상태 배지 5종과 같은 값(신규/검토됨/QA 생성됨/반영됨/제외).
CLUSTER_STATUSES = {"new", "reviewed", "generated", "applied", "excluded"}


@dataclass
class Progress:
    """분석 진행 상태. 수천 건이면 몇 초~수십 초 걸리므로 화면이 폴링한다."""

    running: bool = False
    stage: str = ""
    percent: int = 0
    error: str = ""
    finished_at: str = ""

    def snapshot(self) -> dict:
        return {
            "running": self.running, "stage": self.stage, "percent": self.percent,
            "error": self.error, "finished_at": self.finished_at,
        }


_progress = Progress()


def get_progress() -> dict:
    return _progress.snapshot()


def _set_progress(stage: str, percent: int) -> None:
    _progress.stage = stage
    _progress.percent = percent


# ─────────────────────────────────────────────────────────── 저장


def _path() -> Path:
    return Path(get_settings().analytics_file)


def _empty() -> dict:
    return {
        "last_run_at": "",
        "log_count": 0,
        "period_days": 30,
        "include_test": False,
        "clusters": [],
        "overrides": {"cluster_status": {}, "cluster_category": {}},
    }


def load_analytics() -> dict:
    data = read_json(_path())
    if not isinstance(data, dict):
        return _empty()
    merged = _empty()
    merged.update(data)
    return merged


def save_analytics(result: dict) -> None:
    import json

    with _LOCK:
        write_json_atomic(_path(), json.dumps(result, ensure_ascii=False, indent=2))


# ─────────────────────────────────────────────────────────── 군집화


@dataclass
class _Cluster:
    members: list[QuestionLogEntry] = field(default_factory=list)
    vectors: list[list[float]] = field(default_factory=list)
    centroid: list[float] = field(default_factory=list)

    def add(self, entry: QuestionLogEntry, vector: list[float]) -> None:
        self.members.append(entry)
        self.vectors.append(vector)
        if not self.centroid:
            self.centroid = list(vector)
            return
        n = len(self.vectors)
        self.centroid = [(c * (n - 1) + v) / n for c, v in zip(self.centroid, vector)]


def _cluster_entries(
    entries: list[QuestionLogEntry], embeddings: dict[str, list[float]], threshold: float,
) -> list[_Cluster]:
    """중심점 기준 단일 패스 군집화.

    질문이 수천 건 수준이라 계층적 군집화까지 갈 필요가 없다. 질문마다 기존 군집 중심과
    비교해 임계값을 넘는 가장 가까운 군집에 넣고, 없으면 새 군집을 만든다.

    임베딩 모델을 바꾸면 예전 로그와 차원이 달라진다. 섞이면 유사도 계산이 터지므로
    가장 많이 쓰인 차원만 남기고 건너뛴다.
    """
    clusters: list[_Cluster] = []
    dims = Counter(len(v) for v in embeddings.values() if v)
    expected_dim = dims.most_common(1)[0][0] if dims else 0
    skipped = 0

    for entry in entries:
        vector = embeddings.get(entry.log_id)
        if not vector:
            continue
        if len(vector) != expected_dim:
            skipped += 1
            continue

        best: _Cluster | None = None
        best_similarity = threshold
        for cluster in clusters:
            similarity = cosine_similarity(vector, cluster.centroid)
            if similarity >= best_similarity:
                best_similarity = similarity
                best = cluster

        if best is None:
            best = _Cluster()
            clusters.append(best)
        best.add(entry, vector)

    if skipped:
        log_event(logger, "clustering skipped mismatched embeddings", skipped=skipped, dim=expected_dim)
    return clusters


def _representative(cluster: _Cluster) -> QuestionLogEntry:
    """군집 중심에 가장 가까운 실제 질문. 사용자가 실제로 친 문장이라 날것일 수 있지만,
    없는 문장을 지어내는 것보다 낫다 — 다듬는 일은 '추천 질문 등록'에서 사람이 한다."""
    best, best_similarity = cluster.members[0], -1.0
    for entry, vector in zip(cluster.members, cluster.vectors):
        similarity = cosine_similarity(vector, cluster.centroid)
        if similarity > best_similarity:
            best_similarity, best = similarity, entry
    return best


def _most_common(values: list) -> object | None:
    values = [v for v in values if v]
    return Counter(values).most_common(1)[0][0] if values else None


def _category_names() -> dict[str, str]:
    store = load_categories()
    return {c.category_id: c.name for g in store.groups for c in g.categories}


def _build_cluster(cluster: _Cluster, overrides: dict, names: dict[str, str]) -> dict:
    rep = _representative(cluster)
    members = cluster.members
    cluster_id = f"cl_{rep.log_id}"

    answered = sum(1 for m in members if m.result_type == "answer")
    hit_rate = round(answered / len(members) * 100) if members else 0
    category_id = overrides.get("cluster_category", {}).get(cluster_id) \
        or _most_common([m.category_id for m in members]) or ""

    return {
        "cluster_id": cluster_id,
        "question": rep.question,
        "summary": f"같은 뜻의 표현 {len({m.question for m in members})}가지가 묶였습니다.",
        "count": len(members),
        "hit_rate": hit_rate,
        # 묶음 전체를 대표하는 결과 유형 — 가장 많이 나온 것.
        "result_type": _most_common([m.result_type for m in members]) or "unresolved",
        "category_id": category_id,
        "category_name": names.get(category_id, "미분류"),
        "status": overrides.get("cluster_status", {}).get(cluster_id, "new"),
        # 한 번이라도 QA가 걸린 적이 있으면 '답변 있음'. 0이면 QA를 만들 후보다.
        "has_qa": answered > 0,
        "last_asked": max((m.asked_at for m in members), default="")[:16].replace("T", " "),
        # 화면이 펼침 행에 그대로 뿌린다. 최근 것부터, 너무 길면 잘라서 — 한 묶음에 수백 건이면
        # 응답이 통째로 커진다.
        "members": [m.question for m in sorted(members, key=lambda x: x.asked_at, reverse=True)][:50],
    }


# ─────────────────────────────────────────────────────────── 실행


def _parse_dt(value: str) -> datetime:
    try:
        return datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S")
    except (ValueError, TypeError):
        return datetime.min


def run_analysis(period_days: int = 30, include_test: bool = False) -> dict:
    """질문 로그를 묶어 저장하고 결과를 돌려준다.

    `include_test=False`(기본)면 자동 질문(`channel=auto|eval`)을 뺀다. 평가로 던진 질문이
    실사용 통계에 섞이면 "무엇을 문서화할지" 판단이 통째로 왜곡된다.
    """
    settings = get_settings()
    previous = load_analytics()
    overrides = previous.get("overrides") or _empty()["overrides"]

    _progress.running = True
    _progress.error = ""
    try:
        _set_progress("질문 이력 읽는 중…", 10)
        entries = read_all_question_logs()
        since = datetime.now() - timedelta(days=period_days)
        entries = [e for e in entries if _parse_dt(e.asked_at) >= since]
        if not include_test:
            entries = [e for e in entries if e.channel not in TEST_CHANNELS]
        entries.sort(key=lambda e: e.asked_at)

        _set_progress("질문 임베딩 불러오는 중…", 35)
        embeddings = read_question_embeddings({e.log_id for e in entries})

        _set_progress("비슷한 질문 묶는 중…", 60)
        clusters = _cluster_entries(entries, embeddings, settings.cluster_similarity_threshold)

        _set_progress("대표 질문 정리 중…", 85)
        names = _category_names()
        built = [_build_cluster(c, overrides, names) for c in clusters]
        built.sort(key=lambda c: c["count"], reverse=True)

        result = _empty()
        result.update({
            "last_run_at": time.strftime("%Y-%m-%d %H:%M"),
            "log_count": len(entries),
            "period_days": period_days,
            "include_test": include_test,
            "clusters": built,
            "overrides": overrides,
            # 임베딩이 없는 질문은 묶이지 않는다. 조용히 빠지면 "왜 건수가 다르지"가 된다.
            "unembedded": len(entries) - len(embeddings),
        })
        save_analytics(result)

        _set_progress("완료", 100)
        _progress.finished_at = result["last_run_at"]
        log_event(
            logger, "analytics finished",
            logs=len(entries), clusters=len(built), unembedded=result["unembedded"],
        )
        return result
    except Exception as exc:  # noqa: BLE001 — 분석 실패가 서버를 죽이면 안 된다
        _progress.error = str(exc)
        log_event(logger, "analytics failed", error=str(exc))
        raise
    finally:
        _progress.running = False


def set_override(kind: str, cluster_ids: list[str], value: str | None) -> dict:
    """운영자가 지정한 상태·주제를 저장하고 결과에 즉시 반영한다.

    다음 분석까지 기다리게 하면 화면이 방금 누른 것을 안 보여준다.
    """
    result = load_analytics()
    overrides = result.setdefault("overrides", _empty()["overrides"])
    targets = set(cluster_ids)
    names = _category_names()

    for cluster in result.get("clusters", []):
        if cluster["cluster_id"] not in targets:
            continue
        if kind == "status":
            overrides.setdefault("cluster_status", {})[cluster["cluster_id"]] = value
            cluster["status"] = value
        elif kind == "category":
            overrides.setdefault("cluster_category", {})[cluster["cluster_id"]] = value
            cluster["category_id"] = value or ""
            cluster["category_name"] = names.get(value or "", "미분류")

    save_analytics(result)
    return result
