"""질문 로그 클러스터링 + 통계 집계 (관리자 탭 ④ '질문 분석 / 개선').

적재된 질문 로그를 읽어 유사 질문을 묶고, 대표 질문·요약·통계를 만들어
`data/analytics.json` 에 저장한다. 화면은 이 결과 파일을 읽는다.

설계 메모
- **임베딩을 다시 만들지 않는다.** 답변 시점에 계산해 `question_embeddings.jsonl` 에 남겨둔
  값을 그대로 쓴다(질문 수천 건이면 이 단계만으로 수십 분 차이).
- **대표 질문·요약도 LLM 없이 만든다.** 군집 중심에 가장 가까운 실제 질문을 대표로 쓰고,
  요약은 답변 때 이미 뽑아둔 `intent_summary` 중 가장 흔한 것을 쓴다. LLM을 클러스터 수만큼
  호출하면 4B 모델 기준 수십 분이 걸리는데, 그 값에 비해 얻는 게 크지 않다.
  (문서 초안 생성은 LLM을 쓴다 — 거기서는 생성이 본질이다.)
- 운영자가 지정한 상태(검토됨/제외 등)는 재분석해도 유지되어야 하므로 별도 보관한다.
"""

import io
import json
import os
import tempfile
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger, log_event
from app.core.question_log import (
    QuestionLogEntry,
    read_question_embeddings,
    read_question_logs,
)
from app.core.similarity import cosine_similarity

logger = get_logger("pipeline.clustering")

_LOCK = threading.Lock()

# 답변 경로 중 '미해결'로 세는 것
_UNRESOLVED_ROUTE = "fallback"

# 평가용 자동 질문. 실사용 통계에 섞이면 "무엇을 문서화할지" 판단이 왜곡되므로 기본 제외한다.
_TEST_CHANNELS = {"auto"}


@dataclass
class Progress:
    """분석 진행 상태. 오래 걸리는 작업이라 화면이 폴링해서 읽는다."""

    running: bool = False
    stage: str = ""
    percent: int = 0
    # 임베딩 단계처럼 남은 양을 알 수 없는 구간은 진행률 대신 이 플래그로 표시한다.
    indeterminate: bool = False
    error: str = ""
    finished_at: str = ""

    def snapshot(self) -> dict:
        return {
            "running": self.running,
            "stage": self.stage,
            "percent": self.percent,
            "indeterminate": self.indeterminate,
            "error": self.error,
            "finished_at": self.finished_at,
        }


_progress = Progress()


def get_progress() -> dict:
    return _progress.snapshot()


def _set_progress(stage: str, percent: int, indeterminate: bool = False) -> None:
    _progress.stage = stage
    _progress.percent = percent
    _progress.indeterminate = indeterminate


# ─────────────────────────────────────────────────────────────── 저장/불러오기


def _path() -> Path:
    return Path(get_settings().analytics_file)


def load_analytics() -> dict:
    path = _path()
    if not path.exists():
        return _empty_result()
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as exc:
        log_event(logger, "analytics file unreadable", error=str(exc))
        return _empty_result()


def save_analytics(result: dict) -> None:
    path = _path()
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False)
            os.replace(tmp_name, path)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise


def _empty_result() -> dict:
    return {
        "last_run_at": "",
        "log_count": 0,
        "period_days": 30,
        "kpi": {"total": 0, "unique": 0, "unresolved_rate": 0.0, "no_doc": 0, "avg_latency": 0.0},
        "routes": [],
        "trend": [],
        "top_unresolved": [],
        "clusters": [],
        "include_test": False,
        "excluded_test_count": 0,
        # 운영자가 지정한 값 — 재분석해도 살아남아야 한다.
        "overrides": {"cluster_status": {}, "cluster_category": {}, "excluded_raw_ids": []},
    }


# ─────────────────────────────────────────────────────────────────── 클러스터링


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

    질문 수가 수천 건 수준이라 계층적 군집화까지 갈 필요가 없다. 새 질문마다 기존 군집
    중심과 비교해 임계값을 넘는 가장 가까운 군집에 넣고, 없으면 새 군집을 만든다.
    """
    clusters: list[_Cluster] = []
    # 임베딩 모델을 바꾸면 예전 로그와 차원이 달라진다. 섞이면 유사도 계산이 터지므로
    # 가장 많이 쓰인 차원만 남기고 나머지는 건너뛴다.
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
        log_event(logger, "clustering skipped mismatched embeddings", skipped=skipped, expected_dim=expected_dim)
    return clusters


def _representative(cluster: _Cluster) -> QuestionLogEntry:
    """군집 중심에 가장 가까운 실제 질문을 대표로 삼는다.

    사용자가 실제로 입력한 문장이라 날것일 수 있지만, 없는 문장을 지어내는 것보다 낫다.
    (다듬는 일은 '추천 질문으로 등록' 화면에서 운영자가 한다.)
    """
    best = cluster.members[0]
    best_similarity = -1.0
    for entry, vector in zip(cluster.members, cluster.vectors):
        similarity = cosine_similarity(vector, cluster.centroid)
        if similarity > best_similarity:
            best_similarity = similarity
            best = entry
    return best


def _most_common(values: list) -> object | None:
    values = [v for v in values if v]
    if not values:
        return None
    return Counter(values).most_common(1)[0][0]


def _trend_percent(members: list[QuestionLogEntry], period_days: int) -> int:
    """기간 전반부 대비 후반부 증감률(%). 데이터가 적으면 0."""
    if len(members) < 2:
        return 0
    midpoint = datetime.now() - timedelta(days=period_days / 2)
    later = sum(1 for m in members if _parse_dt(m.asked_at) >= midpoint)
    earlier = len(members) - later
    if earlier == 0:
        return 100 if later else 0
    return int(round((later - earlier) / earlier * 100))


def _parse_dt(value: str) -> datetime:
    try:
        return datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S")
    except (ValueError, TypeError):
        return datetime.min


def _build_cluster(cluster: _Cluster, period_days: int, overrides: dict) -> dict:
    rep = _representative(cluster)
    members = cluster.members
    excluded = set(overrides.get("excluded_raw_ids", []))
    counted = [m for m in members if m.log_id not in excluded]
    if not counted:
        counted = members

    unresolved = sum(1 for m in counted if m.answered_by == _UNRESOLVED_ROUTE)
    cluster_id = f"clu_{rep.log_id}"
    category_id = overrides.get("cluster_category", {}).get(cluster_id) \
        or _most_common([m.category_id for m in counted])

    return {
        "id": cluster_id,
        "question": rep.question,
        "summary": _most_common([m.intent_summary for m in counted]) or "",
        "category_id": category_id,
        "category_confirmed": cluster_id in overrides.get("cluster_category", {}),
        "promoted": overrides.get("cluster_status", {}).get(cluster_id) == "promoted",
        "count": len(counted),
        "unresolved_rate": round(unresolved / len(counted) * 100, 1),
        "top_route": _most_common([m.answered_by for m in counted]) or "",
        "trend": _trend_percent(counted, period_days),
        "status": overrides.get("cluster_status", {}).get(cluster_id, "new"),
        # 한 번이라도 문서를 근거로 답한 적이 있으면 '문서 있음'으로 본다.
        "has_doc": any(m.source_doc_titles for m in counted),
        "last_asked": max((m.asked_at for m in counted), default="")[:10],
        "raws": [
            {
                "id": m.log_id,
                "text": m.question,
                "answered_by": m.answered_by,
                "asked_at": m.asked_at.replace("T", " ")[:16],
                "excluded": m.log_id in excluded,
            }
            for m in sorted(members, key=lambda x: x.asked_at, reverse=True)
        ],
    }


# ─────────────────────────────────────────────────────────────────────── 통계


def _build_stats(entries: list[QuestionLogEntry], clusters: list[dict], period_days: int) -> dict:
    total = len(entries)
    unresolved = sum(1 for e in entries if e.answered_by == _UNRESOLVED_ROUTE)
    latencies = [e.response_time_ms for e in entries if e.response_time_ms]

    route_counts = Counter(e.answered_by for e in entries)
    routes = [
        {
            "key": key,
            "label": key,
            "count": route_counts.get(key, 0),
            "rate": round(route_counts.get(key, 0) / total * 100, 1) if total else 0.0,
        }
        for key in ("cache", "intent", "rag", "fallback")
    ]

    # 일자별 추이 — 질문이 없는 날도 0으로 채워 그래프가 끊기지 않게 한다.
    day_total: Counter = Counter()
    day_unresolved: Counter = Counter()
    for entry in entries:
        day = entry.asked_at[:10]
        day_total[day] += 1
        if entry.answered_by == _UNRESOLVED_ROUTE:
            day_unresolved[day] += 1

    trend = []
    today = datetime.now().date()
    for offset in range(period_days - 1, -1, -1):
        day = (today - timedelta(days=offset)).strftime("%Y-%m-%d")
        trend.append({"d": day[5:], "total": day_total.get(day, 0), "unresolved": day_unresolved.get(day, 0)})

    # 미해결 상위 카테고리 — 클러스터 기준(질문 1건이 아니라 주제 단위로 보는 게 맞다)
    by_category: dict[str, list[dict]] = {}
    for cluster in clusters:
        by_category.setdefault(cluster["category_id"] or "", []).append(cluster)

    top_unresolved = []
    for category_id, group in by_category.items():
        counted = sum(c["count"] for c in group)
        if not counted:
            continue
        weighted = sum(c["unresolved_rate"] * c["count"] for c in group) / counted
        top_unresolved.append({"category_id": category_id or None, "rate": round(weighted, 1)})
    top_unresolved.sort(key=lambda x: x["rate"], reverse=True)

    return {
        "kpi": {
            "total": total,
            "unique": len(clusters),
            "unresolved_rate": round(unresolved / total * 100, 1) if total else 0.0,
            "no_doc": sum(1 for c in clusters if not c["has_doc"]),
            "avg_latency": round(sum(latencies) / len(latencies) / 1000, 1) if latencies else 0.0,
        },
        "routes": routes,
        "trend": trend,
        "top_unresolved": top_unresolved[:5],
    }


# ────────────────────────────────────────────────────────────────────── 실행


def run_analysis(period_days: int = 30, include_test: bool = False) -> dict:
    """질문 로그를 분석해 결과를 저장하고 반환한다. 진행 상태는 `get_progress()` 로 읽는다.

    `include_test=True` 면 자동 질문(평가용)까지 포함한다. 기본은 제외 —
    테스트로 던진 질문이 실사용 통계에 섞이면 문서화 우선순위 판단을 망친다.
    """
    settings = get_settings()
    previous = load_analytics()
    overrides = previous.get("overrides") or _empty_result()["overrides"]

    _progress.running = True
    _progress.error = ""
    try:
        _set_progress("질문 로그 읽는 중…", 5, indeterminate=True)
        all_entries, _ = read_question_logs(limit=1_000_000)
        since = datetime.now() - timedelta(days=period_days)
        in_period = [e for e in all_entries if _parse_dt(e.asked_at) >= since]
        entries = in_period if include_test else [e for e in in_period if e.channel not in _TEST_CHANNELS]
        excluded_test = len(in_period) - len(entries)
        entries.sort(key=lambda e: e.asked_at)

        _set_progress("질문 임베딩 불러오는 중…", 20, indeterminate=True)
        embeddings = read_question_embeddings({e.log_id for e in entries})

        _set_progress("유사 질문 클러스터링 중…", 45)
        clusters = _cluster_entries(entries, embeddings, settings.cluster_similarity_threshold)

        _set_progress("대표 질문·요약 정리 중…", 75)
        built = [_build_cluster(c, period_days, overrides) for c in clusters]
        built.sort(key=lambda c: c["count"], reverse=True)

        _set_progress("통계 집계 중…", 90)
        result = _empty_result()
        result.update(_build_stats(entries, built, period_days))
        result.update({
            "last_run_at": time.strftime("%Y-%m-%d %H:%M"),
            "log_count": len(entries),
            "period_days": period_days,
            "clusters": built,
            "overrides": overrides,
            "include_test": include_test,
            "excluded_test_count": excluded_test,
        })

        save_analytics(result)
        _set_progress("완료", 100)
        _progress.finished_at = result["last_run_at"]
        log_event(
            logger, "analytics run finished",
            logs=len(entries), clusters=len(built), embedded=len(embeddings),
            excluded_test=excluded_test,
        )
        return result
    except Exception as exc:  # noqa: BLE001 — 배치 실패가 서버를 죽이면 안 된다
        _progress.error = str(exc)
        log_event(logger, "analytics run failed", error=str(exc))
        raise
    finally:
        _progress.running = False


def _recount(cluster: dict) -> None:
    """제외되지 않은 원문만으로 건수·미해결률·주요 경로를 다시 센다."""
    counted = [r for r in cluster["raws"] if not r.get("excluded")]
    if not counted:
        cluster["count"] = 0
        cluster["unresolved_rate"] = 0.0
        return
    unresolved = sum(1 for r in counted if r["answered_by"] == _UNRESOLVED_ROUTE)
    cluster["count"] = len(counted)
    cluster["unresolved_rate"] = round(unresolved / len(counted) * 100, 1)
    cluster["top_route"] = _most_common([r["answered_by"] for r in counted]) or ""


def update_override(kind: str, key: str, value) -> dict:
    """운영자 지정값(상태·카테고리·원문 제외)을 저장하고 클러스터에 즉시 반영한다."""
    result = load_analytics()
    overrides = result.setdefault("overrides", _empty_result()["overrides"])

    if kind == "status":
        overrides.setdefault("cluster_status", {})[key] = value
        for cluster in result.get("clusters", []):
            if cluster["id"] == key:
                cluster["status"] = value
                cluster["promoted"] = cluster["promoted"] or value == "promoted"
    elif kind == "category":
        overrides.setdefault("cluster_category", {})[key] = value
        for cluster in result.get("clusters", []):
            if cluster["id"] == key:
                cluster["category_id"] = value
                cluster["category_confirmed"] = True
    elif kind == "raw":
        excluded = set(overrides.setdefault("excluded_raw_ids", []))
        excluded.symmetric_difference_update({key})   # 토글
        overrides["excluded_raw_ids"] = sorted(excluded)
        for cluster in result.get("clusters", []):
            touched = False
            for raw in cluster["raws"]:
                if raw["id"] == key:
                    raw["excluded"] = key in excluded
                    touched = True
            # 건수·미해결률은 화면에 바로 보이는 값이라, 다음 분석까지 기다리지 않고 즉시 다시 센다.
            if touched:
                _recount(cluster)

    save_analytics(result)
    return result
