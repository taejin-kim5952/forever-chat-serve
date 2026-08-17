"""답변 피드백(👍/👎) — 요청서 10.

**여기서 지키는 것은 기능보다 경계다.** 사용자가 누른 값이 QA 상태를 절대 못 바꾼다는 것,
그리고 신고가 관리자 화면 두 곳(질문 이력 · 검수)에 실제로 도달한다는 것이다.
둘 중 하나라도 깨지면 이 기능은 "숫자만 쌓이고 아무도 안 고치는" 상태가 된다.
"""

from fastapi.testclient import TestClient

from app.core.feedback import FeedbackEntry, append_feedback, read_feedback, reports_by_qa
from app.core.question_log import QuestionLogEntry, append_question_log
from app.main import app
from app.qa import store as qa_store

AUTH = ("tester", "secret")


def _client() -> TestClient:
    return TestClient(app)


def _log(log_id: str, *, qa_id: str | None = None, question: str = "질문", similarity: float = 0.9):
    append_question_log(
        QuestionLogEntry(
            log_id=log_id,
            asked_at="2026-08-17T10:00:00",
            question=question,
            result_type="answer" if qa_id else "unresolved",
            matched_qa_id=qa_id,
            similarity=similarity,
        )
    )


# ── 적재 ──────────────────────────────────────────────────────────────────────


def test_vote_is_recorded_and_toggles_off():
    """다시 누르면 취소된다. 잘못 누르는 일이 잦아 한 번 누르면 잠그지 않는다."""
    client = _client()
    _log("q_1")

    assert client.post("/api/feedback", json={"log_id": "q_1", "vote": "down"}).status_code == 200
    assert read_feedback()["q_1"].vote == "down"

    client.post("/api/feedback", json={"log_id": "q_1", "vote": ""})
    assert "q_1" not in read_feedback()


def test_reason_keeps_the_vote():
    """이유는 투표 뒤에 따로 온다. 이유만 왔다고 투표가 사라지면 안 된다."""
    client = _client()
    _log("q_2")
    client.post("/api/feedback", json={"log_id": "q_2", "vote": "down"})
    client.post("/api/feedback", json={"log_id": "q_2", "vote": "down", "reason": "wrong"})

    entry = read_feedback()["q_2"]
    assert entry.vote == "down"
    assert entry.reason_label == "내용이 틀려요"


def test_unknown_reason_is_dropped_but_vote_survives():
    """모르는 이유 값 때문에 신고 자체를 잃지 않는다 — 화면이 바뀌어도 투표는 남아야 한다."""
    client = _client()
    _log("q_3")
    client.post("/api/feedback", json={"log_id": "q_3", "vote": "down", "reason": "made_up"})

    entry = read_feedback()["q_3"]
    assert entry.vote == "down"
    assert entry.reason is None


def test_feedback_needs_a_log_id():
    assert _client().post("/api/feedback", json={"log_id": " ", "vote": "up"}).status_code == 400


def test_feedback_is_public():
    """챗봇에서 부르는 경로다. 관리자 인증을 걸면 사용자가 아무도 못 누른다."""
    _log("q_4")
    response = _client().post("/api/feedback", json={"log_id": "q_4", "vote": "up"})
    assert response.status_code == 200


# ── 관리자 화면에 도달하는가 ──────────────────────────────────────────────────


def test_history_row_carries_feedback():
    client = _client()
    _log("q_5", question="권한그룹 설정")
    client.post("/api/feedback", json={"log_id": "q_5", "vote": "down", "reason": "mismatch"})

    page = client.get("/api/admin/questions", auth=AUTH).json()
    row = [r for r in page["items"] if r["log_id"] == "q_5"][0]
    assert row["feedback"] == "down"
    assert row["feedback_reason"] == "질문과 다른 답이에요"


def test_history_rows_without_feedback_are_blank_not_missing():
    """대부분의 행에는 신고가 없다. 그 행이 목록에서 빠지면 이력이 아니게 된다."""
    client = _client()
    _log("q_6")

    row = [r for r in client.get("/api/admin/questions", auth=AUTH).json()["items"]
           if r["log_id"] == "q_6"][0]
    assert row["feedback"] == ""


def test_down_only_filter():
    client = _client()
    _log("q_7")
    _log("q_8")
    client.post("/api/feedback", json={"log_id": "q_8", "vote": "down"})

    ids = [r["log_id"] for r in
           client.get("/api/admin/questions?feedback=down", auth=AUTH).json()["items"]]
    assert ids == ["q_8"]


def test_csv_export_includes_feedback():
    client = _client()
    _log("q_9", question="CSV 확인")
    client.post("/api/feedback", json={"log_id": "q_9", "vote": "down", "reason": "thin"})

    body = client.get("/api/admin/questions/export", auth=AUTH).text
    assert "feedback_reason" in body
    assert "설명이 부족해요" in body


# ── 검수 화면 ────────────────────────────────────────────────────────────────


def _approved_qa(qa_id: str = "qa_x") -> None:
    qa_store.save_qa([
        qa_store.QaItem(
            qa_id=qa_id, question="권한그룹은 어떻게 설정하나요",
            answer="권한그룹 메뉴에서 설정합니다.", status="approved",
        )
    ])


def test_reports_reach_the_review_screen():
    """숫자가 아니라 **질문 원문**이 가야 한다. 검수자는 그걸 보고 변형 질문을 추가한다."""
    client = _client()
    _approved_qa()
    _log("q_10", qa_id="qa_x", question="그룹 권한 주는 법", similarity=0.91)
    client.post("/api/feedback", json={"log_id": "q_10", "vote": "down", "reason": "mismatch"})

    detail = client.get("/api/admin/qa/qa_x", auth=AUTH).json()
    assert detail["report_count"] == 1
    assert detail["reports"][0]["question"] == "그룹 권한 주는 법"
    assert detail["reports"][0]["reason_label"] == "질문과 다른 답이에요"
    assert detail["reports"][0]["similarity"] == 0.91


def test_up_votes_are_not_reports():
    """👍는 검수 화면에 할 일을 만들지 않는다. 섞이면 신고 개수가 부풀려진다."""
    client = _client()
    _approved_qa()
    _log("q_11", qa_id="qa_x")
    client.post("/api/feedback", json={"log_id": "q_11", "vote": "up"})

    assert client.get("/api/admin/qa/qa_x", auth=AUTH).json()["report_count"] == 0


def test_qa_list_can_sort_by_report_count():
    client = _client()
    qa_store.save_qa([
        qa_store.QaItem(qa_id="qa_quiet", question="조용한 질문", answer="답", status="approved"),
        qa_store.QaItem(qa_id="qa_loud", question="신고 많은 질문", answer="답", status="approved"),
    ])
    for i in range(2):
        _log(f"q_loud_{i}", qa_id="qa_loud")
        client.post("/api/feedback", json={"log_id": f"q_loud_{i}", "vote": "down"})

    items = client.get("/api/admin/qa?sort=report_count", auth=AUTH).json()["items"]
    assert items[0]["qa_id"] == "qa_loud"
    assert items[0]["report_count"] == 2


# ── ★ 경계 ───────────────────────────────────────────────────────────────────


def test_feedback_never_changes_qa_status():
    """이 프로젝트의 전제 — 검수한 답변만 사용자에게 나간다.

    사용자 클릭이 승인 상태를 움직이면 그 전제가 무너진다. 나중에 '👎 3건이면 자동 미사용'
    같은 편의 기능을 넣고 싶어질 때 이 테스트가 막는다.
    """
    client = _client()
    _approved_qa()
    for i in range(5):
        _log(f"q_many_{i}", qa_id="qa_x")
        client.post("/api/feedback", json={"log_id": f"q_many_{i}", "vote": "down", "reason": "wrong"})

    assert qa_store.get_item("qa_x").status == "approved"
    assert len(reports_by_qa()["qa_x"]) == 5


def test_reports_ignore_feedback_without_a_matched_qa():
    """답을 못 찾은 질문(unresolved)에도 👎를 누를 수 있다 — 붙을 QA가 없을 뿐이다."""
    client = _client()
    _log("q_none")
    client.post("/api/feedback", json={"log_id": "q_none", "vote": "down"})

    assert reports_by_qa() == {}


def test_broken_line_does_not_kill_the_rest(tmp_path):
    """포맷이 바뀌기 전 줄이 섞여 있어도 나머지는 살린다(질문 로그와 같은 규칙)."""
    from app.core.config import get_settings

    path = tmp_path / "question_feedback.jsonl"
    assert str(path) == get_settings().question_feedback_file
    append_feedback(FeedbackEntry(log_id="q_ok", vote="down"))
    with open(path, "a", encoding="utf-8") as f:
        f.write("{망가진 줄\n")

    assert "q_ok" in read_feedback()
