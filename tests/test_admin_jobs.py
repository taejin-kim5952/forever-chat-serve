"""작업 현황판 — 실행 중인 배치와 최근 작업(퍼블 요청서 06).

여기서 지키려는 것은 두 가지다.

1. **다음에 할 일은 서버가 정한다.** 화면이 작업 종류를 보고 추측하면, 순서를 바꿀 때마다
   화면과 서버가 서로 다른 것을 안내한다. `result_type` 을 서버가 정하는 것과 같은 원칙이다.
2. **운영에는 실행 중인 배치가 없다.** 생성·평가는 studio 전용이므로 serve 에서는 `running`
   이 언제나 비어야 한다. 여기서 뭔가 뜨면 운영에 LLM 배치가 돈다는 뜻이다.
"""

import base64
import io
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core import jobs
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth():
    token = base64.b64encode(b"tester:secret").decode()
    return {"Authorization": f"Basic {token}"}


@pytest.fixture
def studio(monkeypatch):
    monkeypatch.setattr("app.api.admin_jobs.is_studio", lambda: True)


def fake_generation(**fields):
    """실행 중인 생성 잡 흉내. 스레드를 띄우지 않고 상태만 만든다."""
    from app.studio.runner import JobProgress

    progress = JobProgress(**{
        "status": "running", "stage": "문서에서 QA 생성 중… (3건) API 등록",
        "percent": 62, "done": 38, "total": 61,
        "model": "질문 gemma4:latest · 답변 gemma4:12b", "started_at": jobs.now(),
        **fields,
    })
    return SimpleNamespace(
        progress=lambda: progress,
        is_stopping=lambda: fields.get("stopping", False),
        request_stop=lambda: progress,
    )


# ─────────────────────────────────────────────────────────── 인증 · 모드


def test_jobs_requires_auth(client):
    assert client.get("/api/admin/jobs").status_code == 401


def test_serve_mode_has_no_running_job(client, auth, monkeypatch):
    """운영에는 생성·평가가 없다. 잡이 돌고 있다고 답해도 serve 면 비어야 한다."""
    monkeypatch.setattr("app.studio.runner.get_job", fake_generation)

    body = client.get("/api/admin/jobs", headers=auth).json()

    assert body["running"] is None


def test_running_generation_is_reported(client, auth, studio, monkeypatch):
    monkeypatch.setattr("app.studio.runner.get_job", fake_generation)

    running = client.get("/api/admin/jobs", headers=auth).json()["running"]

    assert running["key"] == "generate"
    assert running["title"] == "QA 생성"
    assert (running["percent"], running["done"], running["total"]) == (62, 38, 61)
    # 단계 문구와 모델 표시는 서버가 만든 것을 화면이 그대로 출력한다.
    assert running["stage"].startswith("문서에서 QA 생성 중")
    assert "답변 gemma4:12b" in running["model"]
    assert running["tab"] == "generate"
    assert running["stopping"] is False


def test_stopping_flag_locks_the_button(client, auth, studio, monkeypatch):
    monkeypatch.setattr("app.studio.runner.get_job", lambda: fake_generation(stopping=True))

    assert client.get("/api/admin/jobs", headers=auth).json()["running"]["stopping"] is True


def test_finished_generation_is_not_running(client, auth, studio, monkeypatch):
    monkeypatch.setattr("app.studio.runner.get_job", lambda: fake_generation(status="done"))

    assert client.get("/api/admin/jobs", headers=auth).json()["running"] is None


# ─────────────────────────────────────────────────────────── 중지


def test_stop_asks_the_job_to_stop(client, auth, studio, monkeypatch):
    stopped = {"called": False}

    def job():
        namespace = fake_generation()
        namespace.request_stop = lambda: stopped.update(called=True)
        return namespace

    monkeypatch.setattr("app.studio.runner.get_job", job)
    assert client.post("/api/admin/jobs/generate/stop", headers=auth).status_code == 200
    assert stopped["called"]


def test_unstoppable_job_is_rejected(client, auth, studio):
    """색인·업로드는 요청 안에서 끝난다. 멈출 지점이 없다."""
    assert client.post("/api/admin/jobs/index/stop", headers=auth).status_code == 400


def test_stop_is_blocked_in_serve_mode(client, auth):
    assert client.post("/api/admin/jobs/generate/stop", headers=auth).status_code == 403


# ─────────────────────────────────────────────────────────── 다음 단계


@pytest.mark.parametrize("key,counts,expected_tab,expected_label", [
    ("upload", {"docs": 3}, "generate", "QA 생성하기"),
    ("index", {"docs": 39}, "generate", "QA 생성하기"),
    ("generate", {"drafts": 12}, "generate", "초안 검토하기"),
    ("apply", {"saved": 12}, "review", "검수하기"),
    ("evaluate", {"total": 120}, "settings", "임계값 조정하기"),
])
def test_next_step_points_to_the_following_stage(client, auth, key, counts, expected_tab, expected_label):
    jobs.record(key, summary="완료", counts=counts)

    row = client.get("/api/admin/jobs", headers=auth).json()["recent"][0]

    assert row["next"] == {"label": expected_label, "tab": expected_tab}


@pytest.mark.parametrize("key,counts", [
    ("upload", {"docs": 0}),      # 들어간 문서가 없으면 생성할 것이 없다
    ("generate", {"drafts": 0}),  # 초안이 0건이면 검토할 것이 없다
    ("apply", {"saved": 0}),
])
def test_no_next_step_when_nothing_was_produced(client, auth, key, counts):
    jobs.record(key, summary="0건", counts=counts)

    assert client.get("/api/admin/jobs", headers=auth).json()["recent"][0]["next"] is None


def test_failed_job_points_back_to_its_own_screen(client, auth):
    """실패했는데 '다음 단계로 가라'고 안내하면 안 된다."""
    jobs.record("generate", status="failed", error="LLM 호출이 모두 실패했습니다")

    row = client.get("/api/admin/jobs", headers=auth).json()["recent"][0]

    assert row["next"] == {"label": "QA 생성 화면으로", "tab": "generate"}
    # 실패 사유가 요약 자리에 그대로 보여야 원인을 찾는다.
    assert "LLM 호출" in row["summary"]


def test_stopped_job_has_no_next_step(client, auth):
    jobs.record("generate", status="stopped", summary="중지됨 (5건)", counts={"drafts": 5})

    assert client.get("/api/admin/jobs", headers=auth).json()["recent"][0]["next"] is None


# ─────────────────────────────────────────────────────────── 이력


def test_recent_is_newest_first_and_capped(client, auth):
    for n in range(7):
        jobs.record("index", summary=f"{n}번째", counts={"docs": 1})

    rows = client.get("/api/admin/jobs", headers=auth).json()["recent"]

    assert len(rows) == 5                    # 화면에 5건
    assert rows[0]["summary"] == "6번째"      # 최신이 위
    # 다음 단계 버튼은 화면이 맨 윗줄에만 붙이지만, 서버는 각 줄의 next 를 그대로 준다.
    assert all(r["title"] == "문서 색인" for r in rows)


def test_upload_batches_collapse_into_one_row(client, auth):
    """폴더 업로드는 화면이 몇 건씩 나눠 보낸다. 요청마다 한 줄이면 폴더 하나가 열 줄이 된다."""
    for _ in range(3):
        jobs.record("upload", counts={"docs": 4, "created": 4}, merge=True,
                    summary_from_counts=lambda c: f"{c['created']}건 등록")

    rows = client.get("/api/admin/jobs", headers=auth).json()["recent"]

    assert len(rows) == 1
    # 마지막 묶음(4건)이 아니라 합계(12건)가 남아야 한다.
    assert rows[0]["summary"] == "12건 등록"


def test_one_failed_batch_marks_the_merged_row_failed(client, auth):
    jobs.record("upload", counts={"docs": 4}, merge=True)
    jobs.record("upload", status="failed", counts={"docs": 0}, merge=True)

    rows = client.get("/api/admin/jobs", headers=auth).json()["recent"]

    assert len(rows) == 1
    # 성공으로 덮으면 못 들어간 파일이 묻힌다.
    assert rows[0]["status"] == "failed"


def test_elapsed_is_human_readable(client, auth):
    jobs.record("index", started_at="2026-08-16T09:00:00", summary="완료", counts={"docs": 1})

    row = client.get("/api/admin/jobs", headers=auth).json()["recent"][0]

    assert row["elapsed"]            # 초/분/시간 중 하나로 채워진다
    assert row["finished_at"]


def test_recording_never_raises_into_the_caller(client, auth):
    """이력 기록이 실패해도 부르는 쪽은 성공이어야 한다.

    요약 문구를 만들다 틀린 필드를 읽어 30분짜리 생성 배치가 통째로 '실패'로 뒤집힌 적이 있다.
    """
    def broken(counts):
        raise KeyError("없는 항목")

    jobs.record("generate", counts={"drafts": 1}, summary_from_counts=broken)

    assert client.get("/api/admin/jobs", headers=auth).status_code == 200


def test_broken_history_file_does_not_break_the_screen(client, auth, isolated_data):
    """이력은 부가 정보다. 파일이 깨져도 화면이 열려야 한다."""
    from pathlib import Path
    Path(isolated_data.job_history_file).write_text("{ 깨진 파일", encoding="utf-8")

    body = client.get("/api/admin/jobs", headers=auth).json()

    assert body["recent"] == []


# ─────────────────────────────────────────────────────── 실제 작업이 이력을 남기는가


def test_reindex_records_a_job(client, auth):
    client.post("/api/admin/qa/reindex?include_docs=true", headers=auth)

    row = client.get("/api/admin/jobs", headers=auth).json()["recent"][0]

    assert row["key"] == "index"
    assert row["status"] == "done"


def test_folder_upload_records_a_job(client, auth, monkeypatch, isolated_data):
    monkeypatch.setattr("app.api.admin_docs.is_studio", lambda: True)
    doc = "---\ntitle: 문서\n---\n\n## 절\n\n내용입니다.\n"

    client.post(
        "/api/admin/docs/upload", headers=auth,
        files=[("files", ("api-등록.md", io.BytesIO(doc.encode()), "text/markdown")),
               ("paths", (None, "폴더/api-등록.md"))],
        data={"overwrite": "false"},
    )

    row = client.get("/api/admin/jobs", headers=auth).json()["recent"][0]

    assert row["key"] == "upload"
    assert row["summary"] == "1건 등록"
    assert row["next"] == {"label": "QA 생성하기", "tab": "generate"}
