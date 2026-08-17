"""진행 현황 집계 — 막힌 곳을 **서버가 하나만 고르는지**.

이 화면의 값어치는 숫자를 모아 보여주는 데 있지 않고 "지금 무엇을 해야 하는가"를 하나로
좁혀 주는 데 있다. 그래서 여기서 확인하는 것은 주로 그 판단이다.

- 강조(`todo`)는 **한 칸에만** 붙는가
- 앞 단계가 막혀 있으면 뒷 단계를 가리키지 않는가
- serve 모드에서 studio 전용 칸이 `off` 로 잠기는가

`app/pipeline/retrieve.py` 의 `result_type` 과 같은 원칙이다 — 화면이 숫자를 보고 다시
판단하면 기준이 두 곳에 생긴다.
"""

import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.pipeline.status import collect
from app.qa import store as qa_store
from app.studio import runner
from app.studio.evaluate import EvalReport, save_report


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth():
    return {"Authorization": f"Basic {base64.b64encode(b'tester:secret').decode()}"}


def _doc(isolated_data, name: str = "api-등록") -> None:
    Path(isolated_data.raw_docs_dir, f"{name}.md").write_text(
        "---\ntitle: API 등록\n---\n\n## 절차\n\n내용입니다.\n", encoding="utf-8",
    )


def _qa(status: str, question: str = "질문") -> None:
    qa_store.upsert_item(qa_store.QaItem(
        qa_id=qa_store.new_qa_id(), question=question, answer="답변", status=status,
    ))


def _steps(status) -> dict:
    return {s.key: s for s in status.steps}


# ────────────────────────────────────────────────────────── 인증 · 엔드포인트


def test_status_requires_admin(client):
    assert client.get("/api/admin/pipeline/status").status_code == 401


def test_status_endpoint_returns_six_steps(client, auth):
    body = client.get("/api/admin/pipeline/status", headers=auth).json()

    assert [s["key"] for s in body["steps"]] == [
        "documents", "drafts", "pending", "approved", "quality", "threshold",
    ]
    assert body["mode"] == "serve"


# ──────────────────────────────────────────────────────────────── 병목 판단


def test_no_documents_is_the_first_bottleneck(isolated_data):
    """문서가 없으면 뒤를 아무리 풀어도 흐르지 않는다. 검수 대기가 있어도 문서가 먼저다."""
    _qa("pending")

    status = collect()

    assert status.todo.kind == "docs"
    assert status.todo.tab == "docs"
    assert _steps(status)["documents"].state == "todo"


def test_pending_review_is_the_bottleneck(isolated_data):
    _doc(isolated_data)
    _qa("pending", "검수 기다리는 질문")

    status = collect()

    assert status.todo.kind == "review"
    assert status.todo.tab == "review"
    assert "1건" in status.todo.message


def test_only_one_step_is_highlighted(isolated_data):
    """여섯 칸이 다 강조되면 아무것도 안 읽힌다."""
    _doc(isolated_data)
    _qa("pending")

    status = collect()

    assert sum(1 for s in status.steps if s.state == "todo") == 1


def test_nothing_to_do_in_serve_mode(isolated_data):
    _doc(isolated_data)
    _qa("approved")

    status = collect()

    assert status.todo.kind == "clear"
    assert status.todo.tab is None
    assert not any(s.state == "todo" for s in status.steps)


def test_studio_suggests_generating_when_clear(isolated_data, monkeypatch):
    _doc(isolated_data)
    _qa("approved")
    monkeypatch.setattr("app.pipeline.status.is_studio", lambda: True)

    status = collect()

    assert status.todo.kind == "generate"
    assert _steps(status)["drafts"].state == "todo"


# ───────────────────────────────────────────────────────────────── 칸 상태


def test_unindexed_document_warns(isolated_data):
    """문서를 넣고 색인을 안 하면 그 문서로는 아무것도 검색되지 않는다."""
    _doc(isolated_data)

    step = _steps(collect())["documents"]

    assert step.value == 1
    assert "미색인 1건" in step.note


def test_draft_button_says_what_to_do_now(isolated_data, monkeypatch):
    """초안이 쌓여 있으면 버튼은 '생성'이 아니라 '검토'라고 해야 한다.

    12건이 기다리는데 버튼이 `생성 시작` 이면 "또 만들라는 건가"가 되고, 정작 그 12건을
    어디서 보는지 못 찾는다 — 실제로 겪었다.
    """
    _doc(isolated_data)
    monkeypatch.setattr("app.pipeline.status.is_studio", lambda: True)

    assert _steps(collect())["drafts"].action == "생성 시작"

    from app.studio import runner
    runner._write_drafts(runner.DraftFile(
        generated_at="2026-08-17T09:43:00",
        drafts=[runner.QaDraft(question=f"질문 {n}", answer="답변") for n in range(12)],
    ))

    step = _steps(collect())["drafts"]
    assert step.value == 12
    assert step.action == "초안 12건 보기"


def test_studio_only_steps_are_locked_in_serve(isolated_data):
    _doc(isolated_data)

    steps = _steps(collect())

    assert steps["drafts"].state == "off"
    assert steps["quality"].state == "off"


def test_threshold_step_reads_runtime_config(isolated_data):
    step = _steps(collect())["threshold"]

    assert step.value == 0.90
    assert "0.55" in step.note


# ─────────────────────────────────────────────────────────────── 품질 리포트


def test_quality_is_unknown_without_a_report(isolated_data):
    assert _steps(collect())["quality"].note == "측정 이력 없음"


def test_high_mismatch_warns_and_becomes_the_bottleneck(isolated_data):
    """오매칭은 못 찾는 것보다 나쁘다 — 사용자가 틀린 답을 맞는 줄 안다."""
    _doc(isolated_data)
    _qa("approved")
    save_report(EvalReport(run_at="2026-08-14T10:00:00", total=50, mismatch_rate=9.4))

    status = collect()
    step = _steps(status)["quality"]

    assert step.value == 9.4
    assert step.state == "todo"           # 병목이라 warn 보다 todo 가 우선
    assert status.todo.kind == "quality"
    assert "9.4%" in status.todo.message


def test_report_survives_restart(isolated_data):
    """메모리에만 두면 재시작 한 번에 사라져 '측정 이력 없음'이 된다."""
    save_report(EvalReport(run_at="2026-08-14T10:00:00", total=50, mismatch_rate=1.2))

    from app.studio.evaluate import load_last_report
    assert load_last_report().mismatch_rate == 1.2


def test_stopped_evaluation_is_not_saved(isolated_data):
    """일부만 돌린 오매칭률이 최신 품질로 남으면 틀린 숫자가 근거로 쓰인다."""
    from app.studio import evaluate

    job = evaluate.get_job()
    job.request_stop()
    job._run(limit=10, top_k=5)   # 문항이 없어 실패로 끝난다 — 저장되지 않아야 한다

    assert evaluate.load_last_report() is None


# ─────────────────────────────────────────────────────────────── 흐름 요약


def test_summary_is_hidden_without_a_generation_run(isolated_data):
    assert collect().summary.has_run is False


def test_summary_reports_what_was_dropped(isolated_data):
    """근거 없음이 많다는 것은 QA가 아니라 **문서를 써야 한다**는 신호다."""
    _doc(isolated_data)
    runner._write_drafts(runner.DraftFile(
        generated_at="2026-08-15T09:00:00",
        stats=runner.GenerationStats(
            source="docs", questions_made=38, dropped_language=2,
            dropped_ungrounded=9, drafts=27, low_score=3,
        ),
    ))

    summary = collect().summary

    assert summary.has_run is True
    assert (summary.questions_made, summary.dropped_ungrounded) == (38, 9)
    assert summary.low_score == 3
