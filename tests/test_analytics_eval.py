"""탭 ② 질문 분석 · 탭 ⑦ 품질 평가.

두 기능 모두 "숫자가 그럴듯하게 나오는지"가 아니라 **판단이 뒤집히지 않는지**를 본다.

- 분석: 사람이 지정한 상태·주제가 재분석에도 살아남아야 한다. 초기화되면 아무도 지정하지 않는다.
- 평가: 문항이 인덱스 안에 들어 있어서, 자기 자신을 빼지 않으면 적중률이 항상 100%로 나온다.
  그러면 임계값을 정할 근거로 쓸 수 없다.
"""

import base64

import pytest
from fastapi.testclient import TestClient

from app.core.question_log import (
    QuestionLogEntry,
    append_question_embedding,
    append_question_log,
    new_log_id,
)
from app.main import app
from app.pipeline import analytics
from app.qa import store as qa_store
from app.qa.index import QaIndex
from app.studio import evaluate


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth():
    token = base64.b64encode(b"tester:secret").decode()
    return {"Authorization": f"Basic {token}"}


@pytest.fixture
def studio(monkeypatch):
    monkeypatch.setattr("app.api.studio_eval.is_studio", lambda: True)


def log_question(question: str, result_type: str = "unresolved", channel: str = "web", vector=None):
    """질문 1건 + 임베딩을 이력에 남긴다. 실제 응답 경로가 하는 일과 같다."""
    log_id = new_log_id()
    append_question_log(QuestionLogEntry(
        log_id=log_id, asked_at="2026-08-15T09:00:00", question=question,
        result_type=result_type, channel=channel,
    ))
    append_question_embedding(log_id, vector or [1.0, 0.0, 0.0])
    return log_id


# ─────────────────────────────────────────────────────────── 탭 ② 분석


def test_similar_questions_are_grouped(client, auth):
    log_question("API 등록은 어떻게 하나요?", vector=[1.0, 0.0, 0.0])
    log_question("API 등록 방법 알려주세요", vector=[0.99, 0.1, 0.0])
    log_question("템플릿을 삭제하고 싶습니다", vector=[0.0, 0.0, 1.0])

    body = client.post("/api/admin/analytics/run", headers=auth).json()

    assert len(body["clusters"]) == 2
    biggest = body["clusters"][0]
    assert biggest["count"] == 2
    # 대표 질문은 실제로 들어온 문장이어야 한다. 지어낸 문장이면 안 된다.
    assert biggest["question"] in ("API 등록은 어떻게 하나요?", "API 등록 방법 알려주세요")


def test_test_channel_is_excluded_by_default(client, auth):
    log_question("실제 사용자 질문", channel="web")
    log_question("평가용 자동 질문", channel="auto")

    body = client.post("/api/admin/analytics/run", headers=auth).json()

    assert body["log_count"] == 1

    with_test = client.post("/api/admin/analytics/run?include_test=true", headers=auth).json()
    assert with_test["log_count"] == 2


def test_cluster_marks_missing_qa(client, auth):
    """QA가 한 번도 안 걸린 묶음이 'QA 없음'이다 — 다음에 만들 QA 후보."""
    log_question("답이 없는 질문", result_type="unresolved")

    body = client.post("/api/admin/analytics/run", headers=auth).json()

    assert body["clusters"][0]["has_qa"] is False
    assert body["clusters"][0]["hit_rate"] == 0


def test_override_survives_reanalysis(client, auth):
    log_question("두 번 분석해도 상태가 남아야 하는 질문")
    first = client.post("/api/admin/analytics/run", headers=auth).json()
    cluster_id = first["clusters"][0]["cluster_id"]

    client.post("/api/admin/analytics/override",
                json={"kind": "status", "cluster_ids": [cluster_id], "value": "reviewed"},
                headers=auth)
    again = client.post("/api/admin/analytics/run", headers=auth).json()

    assert again["clusters"][0]["status"] == "reviewed"


def test_unknown_status_is_rejected(client, auth):
    response = client.post("/api/admin/analytics/override",
                           json={"kind": "status", "cluster_ids": ["cl_x"], "value": "이상한상태"},
                           headers=auth)

    assert response.status_code == 400


def test_analytics_requires_auth(client):
    assert client.get("/api/admin/analytics").status_code == 401


# ─────────────────────────────────────────────────────────── 탭 ⑦ 평가


def approved_qa(question: str, variants: list[str], answer: str = "답변입니다") -> qa_store.QaItem:
    item = qa_store.upsert_item(qa_store.QaItem(
        qa_id=qa_store.new_qa_id(), question=question, answer=answer,
        variants=variants, status="approved",
    ))
    QaIndex().upsert_item(item)
    return item


def test_evaluation_excludes_the_question_itself(studio):
    """문항이 인덱스에 그대로 들어 있다. 안 빼면 유사도 1.000 으로 항상 적중이다."""
    approved_qa("API 등록은 어떻게 하나요?", ["API 등록 방법", "API 등록 절차"])

    report = evaluate.run_evaluation(limit=10)

    assert report.total == 2
    # 자기 자신을 뺐으므로 1.0 이 나올 수 없다.
    assert all(item.similarity < 0.999 for item in report.items)


def test_variant_finds_its_own_qa(studio):
    """변형 질문을 던지면 **그 QA가 다시 걸려야** 한다 — 이 평가의 존재 이유다.

    검색 결과를 `qa_id` 단위로 접은 뒤에 '자기 자신'을 빼면, 그 QA는 한 줄뿐이라 통째로
    사라진다. 그러면 어떤 데이터로 재도 적중률이 0%, 미검색 100% 로 나온다 —
    2026-08-17 에 실제 데이터로 처음 돌렸을 때 그 상태였고, 그전까지 아무도 몰랐다.
    """
    approved_qa("API 등록은 어떻게 하나요?",
                ["API 등록 방법", "API 등록 절차 알려주세요", "API 어떻게 등록해요"])

    report = evaluate.run_evaluation(limit=10)

    assert report.total == 3
    assert report.top1 > 0, "변형 질문이 자기 QA를 못 찾습니다 — 접기와 자기 제외 순서 문제"
    # 순위는 '얼마나 잘 찾았나'이고, 미검색(miss)은 거기에 임계값을 더한 판정이다.
    # 유사도가 임계값에 못 미치면 rank=1 이어도 miss 다 — 둘을 섞어 보면 안 된다.
    assert all(item.rank == 1 for item in report.items)


def test_evaluation_detects_mismatch(studio, monkeypatch):
    """다른 QA가 임계값을 넘겨 1등이면 오매칭 — 사용자에게 틀린 답이 나가는 경우다."""
    from app.core.runtime_config import RuntimeConfig, save_runtime_config
    # 가짜 임베딩은 글자가 겹치면 가까워진다. 임계값을 낮춰 두 QA가 서로 걸리게 만든다.
    save_runtime_config(RuntimeConfig(
        qa_match_threshold=0.5, related_docs_floor=0.3,
        related_docs_count=3, qa_top_k=10, doc_top_k=10))
    approved_qa("API 등록 절차", ["API 등록 방법 안내"])
    approved_qa("API 등록 화면 설명", ["API 등록 방법 설명"])

    report = evaluate.run_evaluation(limit=10)

    assert report.total == 2
    assert {i.verdict for i in report.items} <= {"hit", "mismatch", "miss"}
    # 오매칭률과 적중률의 합은 답변으로 나간 비율이다.
    assert report.mismatch_rate + report.top1 <= 100.0 + 1e-6


def test_evaluation_without_variants_fails_loudly(studio):
    """변형 질문이 없으면 잴 것이 없다. 0건으로 조용히 끝나면 원인을 못 찾는다."""
    approved_qa("변형 질문이 없는 QA", [])

    with pytest.raises(RuntimeError, match="변형 질문"):
        evaluate.run_evaluation(limit=10)


def test_threshold_sweep_is_included(studio):
    approved_qa("API 등록은 어떻게 하나요?", ["API 등록 방법", "API 등록 절차"])

    report = evaluate.run_evaluation(limit=10)

    thresholds = [row["threshold"] for row in report.threshold_sweep]
    assert thresholds == [0.75, 0.80, 0.85, 0.90, 0.95]
    # 임계값을 올리면 답변으로 나가는 비율은 줄기만 해야 한다.
    rates = [row["answer_rate"] for row in report.threshold_sweep]
    assert rates == sorted(rates, reverse=True)


def test_eval_is_blocked_in_serve_mode(client, auth):
    """운영에서 100문항을 임베딩하면 그 시간만큼 사용자 질문이 밀린다."""
    assert client.post("/api/studio/eval", headers=auth).status_code == 403
    assert client.get("/api/studio/eval/result", headers=auth).status_code == 403


def test_eval_endpoint_runs_in_studio(client, auth, studio):
    approved_qa("API 등록은 어떻게 하나요?", ["API 등록 방법", "API 등록 절차"])

    client.post("/api/studio/eval", headers=auth)
    assert evaluate.get_job().join(timeout=10)

    result = client.get("/api/studio/eval/result", headers=auth).json()
    assert result["total"] == 2
    assert client.get("/api/studio/eval/progress", headers=auth).json()["status"] == "done"
