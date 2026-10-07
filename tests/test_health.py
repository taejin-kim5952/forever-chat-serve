"""준비 상태 — `/health/ready` 가 **답할 수 있나**를 정직하게 말해야 한다.

컨테이너 HEALTHCHECK 가 이 값을 본다(`Dockerfile`). 그래서 여기가 틀리면 **도커가 거짓말을
한다** — 21ms 에 제대로 답하는 서버가 `unhealthy` 로 표시되거나, 반대로 아무 질문에도 답하지
못하는 서버가 `healthy` 로 보인다. 둘 다 오류를 내지 않아서 사람이 눈으로 찾아야 한다.

2026-10-07 에 앞쪽이 실제로 일어났다. 프로젝트(packs)를 넣으면서 이 엔드포인트만 그 사실을
배우지 못해, 자료를 전부 `packs/` 에 둔 서버가 `qa_serving: 0 · degraded` 를 냈다.
"""

import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core import projects
from app.core.config import reset_project, use_project
from app.main import app
from app.qa import store as qa_store

AUTH = {"Authorization": "Basic " + base64.b64encode(b"tester:secret").decode()}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def model_present(isolated_data):
    """모델 파일이 **있는** 상태로 만든다.

    테스트의 임베더는 결정적 가짜(`FakeEmbedder`)라 파일을 읽지 않는다. 그런데 이
    엔드포인트는 **파일이 있는지**만 본다 — 모델 쪽을 비워 두면 무엇을 재도 `degraded` 가
    나와서 QA 세는 쪽을 검증할 수 없다. 내용은 보지 않으므로 빈 파일로 충분하다.
    """
    from app.ingestion.embedder import MODEL_FILE, TOKENIZER_FILE
    model_dir = Path(isolated_data.embed_onnx_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    for name in (MODEL_FILE, TOKENIZER_FILE):
        (model_dir / name).write_bytes(b"")
    return model_dir


def approve_one(project_id: str | None, qa_id: str) -> None:
    """그 프로젝트에 **내보낼 수 있는** QA 한 건을 둔다."""
    token = use_project(project_id) if project_id else None
    try:
        qa_store.upsert_item(qa_store.QaItem(
            qa_id=qa_id, question=f"{qa_id} 는 어떻게 하나요?", answer="답변",
            status="approved"))
    finally:
        if token is not None:
            reset_project(token)


def test_ready_counts_approved_qa_across_every_project(client, isolated_data, model_present):
    """프로젝트에 있는 QA 를 **세어야** 한다.

    이것이 이 파일의 이유다. 기본 팩(`data/`)만 세면, 자료를 전부 `packs/` 에 둔 설치가
    `qa_serving: 0` 을 내고 Dockerfile 의 HEALTHCHECK 가 컨테이너를 **unhealthy** 로
    표시한다. 그 서버는 멀쩡히 답하고 있다.
    """
    projects.create_project("api-manager", "API Manager")
    projects.create_project("mcp-manager", "MCP Manager")
    approve_one("api-manager", "qa_api_1")
    approve_one("api-manager", "qa_api_2")
    approve_one("mcp-manager", "qa_mcp_1")

    body = client.get("/health/ready").json()

    assert body["qa_serving"] == 3, "프로젝트를 가로질러 세야 합니다"
    assert body["status"] == "ok"


def test_a_single_pack_install_still_counts_its_own_qa(client, isolated_data, model_present):
    """프로젝트를 안 쓰는 설치는 **예전과 똑같이** 동작해야 한다 — 기본 팩을 센다."""
    approve_one(None, "qa_1")

    body = client.get("/health/ready").json()

    assert body["qa_serving"] == 1
    assert body["status"] == "ok"


def test_an_install_with_no_approved_qa_is_degraded(client, isolated_data, model_present):
    """프로젝트는 있는데 승인된 QA 가 하나도 없으면 **답할 수 없다.**

    문서만 올리고 검수를 안 한 상태가 여기다. 화면은 멀쩡히 뜨고 자료 목록도 보이므로,
    상태를 정직하게 내지 않으면 "왜 전부 미해결인가"를 한참 찾는다.
    """
    projects.create_project("api-manager", "API Manager")

    body = client.get("/health/ready").json()

    assert body["qa_serving"] == 0
    assert body["status"] == "degraded"


def test_a_broken_pack_does_not_take_the_endpoint_down(client, isolated_data, model_present, monkeypatch):
    """팩 하나가 깨져도 **상태는 돌려줘야** 한다.

    헬스체크가 500 을 내면 도커는 컨테이너를 unhealthy 로 본다. 자료 하나가 상한 것과
    서버가 죽은 것은 다르다 — 나머지 프로젝트로 답할 수 있으면 답해야 한다.
    """
    projects.create_project("good", "멀쩡한 쪽")
    projects.create_project("bad", "깨진 쪽")
    approve_one("good", "qa_good")

    real = qa_store.serving_items

    def explode(*args, **kwargs):
        from app.core.config import current_project
        if current_project() == "bad":
            raise OSError("팩이 깨졌습니다")
        return real(*args, **kwargs)

    monkeypatch.setattr(qa_store, "serving_items", explode)

    body = client.get("/health/ready").json()

    assert body["qa_serving"] == 1
    assert body["status"] == "ok"


def test_ready_reports_a_missing_embedding_model_by_name(client, isolated_data, monkeypatch):
    """모델이 없으면 **어느 파일이** 없는지 적는다.

    이 설치의 모델은 이미지에 없을 수도 있고(볼륨으로 붙인다) 있을 수도 있다
    (`WITH_MODEL=true`). 어느 쪽이든 "없다"만 알려주면 볼륨을 잘못 붙인 것인지 모델을
    안 받은 것인지 구분할 수 없다. `embed_model_dir` 을 함께 내는 이유도 같다.
    """
    monkeypatch.setattr(isolated_data, "embed_onnx_dir", str(Path(isolated_data.embed_onnx_dir).parent / "없는-폴더"))
    approve_one(None, "qa_1")

    body = client.get("/health/ready").json()

    assert body["embed_model"].startswith("missing: ")
    assert "model.onnx" in body["embed_model"]
    assert body["embed_model_dir"].endswith("없는-폴더")
    assert body["status"] == "degraded", "모델이 없으면 QA 가 있어도 답할 수 없습니다"
