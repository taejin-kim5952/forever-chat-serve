"""QA 사전 생성(탭 ⑥) — 안전장치가 실제로 막는지 확인한다.

여기서 지키려는 것은 세 가지다.

1. **운영에서는 절대 돌지 않는다.** 운영 서버에 GPU가 없어 이 코드가 실행되면 요청이 몇 분씩
   묶인다. 화면이 탭을 감추는 것만으로는 부족해서 서버에서도 403을 낸다.
2. **AI가 만든 답변이 검수 없이 사용자에게 나가지 않는다.** 반영은 `pending` 으로만 되고,
   `pending` 은 벡터 인덱스에 올라가지 않으므로 챗봇이 찾을 수 없다.
3. **역할별로 정한 모델이 그 역할에만 쓰인다.** 질문·변형과 답변에 서로 다른 모델을 두는 것이
   설정으로만 있고 실제 호출은 한 모델로 가면, 화면에서 고른 값이 조용히 무시된다.

LLM은 부르지 않는다. `FakeLlm` 이 형식만 맞춘 응답을 돌려주므로 모델 없이도 파싱·필터·상태
전이를 검증할 수 있다(임베딩을 `FakeEmbedder` 로 바꾼 것과 같은 이유).
"""

import base64
import threading

import pytest
from fastapi.testclient import TestClient

from app.ingestion.doc_index import DocIndex
from app.main import app
from app.qa import store as qa_store
from app.qa.index import QaIndex
from app.studio import runner
from app.studio.generate import ModelRoles, generate_from_docs, generate_from_questions
from app.studio.llm import EmptyLlmResponse

DOC = """---
title: API 등록
category: API 관리 > API 등록
url: /api/spcreg/def/mvApiDefReg.do
---

이 문서는 API 등록 화면에서 무엇을 입력해야 하는지 설명합니다. 도입부는 문서 자체를 소개하는
내용이라 QA 생성 대상에서 빠집니다. 검색(related_docs)에는 그대로 쓰입니다.

## API 등록 절차

API를 등록하려면 먼저 API 그룹을 만들고, 그 안에서 API 등록 화면으로 들어갑니다.
필수 입력 항목은 API 명, Path, Method 세 가지입니다. 저장하면 검수 담당자에게 승인 요청이
전달되며, 승인 후 배포 화면에서 반영합니다.
"""

QUESTIONS = """API 등록은 어떻게 하나요?
"""

VARIANTS = """API 등록 절차 알려주세요
API 어떻게 등록해요?
API 등록 방법
"""

GROUNDED = """근거: 있음
답변: API 그룹을 먼저 만든 뒤 등록 화면([[spc-등록]] 참고)에서 진행합니다.
필수 입력 항목은 API 명, Path, Method 입니다."""

VERDICT = '{"score": 5, "reason": "발췌의 절차와 필수 항목을 그대로 옮겼습니다."}'


class FakeLlm:
    """프롬프트 종류를 보고 형식에 맞는 응답을 돌려준다.

    `gate` 를 주면 첫 호출에서 멈춘다 — '실행 중' 상태(409·중지)를 확인하는 테스트가
    타이밍에 기대지 않게 하기 위한 것이다.

    `log` 에 **(모델 이름, 호출 종류)** 를 남긴다. 역할별로 모델을 나눈 뒤로는 "무엇을
    만들었나" 만큼이나 "누가 만들었나"가 검증 대상이다.
    """

    question_response = QUESTIONS
    variant_response = VARIANTS
    answer_response = GROUNDED
    judge_response = VERDICT
    gate: threading.Event | None = None
    raises: Exception | None = None
    log: list[tuple[str, str]] = []

    def __init__(self, model=None, host=None):
        self.model = model or "fake-llm"
        self.calls: list[str] = []

    def source_budget_chars(self) -> int:
        return 4000

    def fit(self, text: str, label: str = "") -> str:
        return text

    def chat(self, prompt: str, system: str | None = None, json_format: bool = False) -> str:
        # `json_format` 은 채점처럼 기계가 읽을 응답에만 켠다. 진짜 모델에서는 이것과
        # `/no_think` 가 없으면 추론 모델이 사고 과정으로 예산을 다 써버린다.
        self.calls.append(prompt)
        if "뜻이 같은" in prompt:
            kind, response = "variant", FakeLlm.variant_response
        elif "채점하세요" in prompt:
            kind, response = "judge", FakeLlm.judge_response
        elif "[사용자 질문]" in prompt:
            kind, response = "answer", FakeLlm.answer_response
        else:
            kind, response = "question", FakeLlm.question_response
        FakeLlm.log.append((self.model, kind))

        if FakeLlm.gate is not None:
            FakeLlm.gate.wait(timeout=5)
        if FakeLlm.raises is not None:
            raise FakeLlm.raises
        return response


@pytest.fixture(autouse=True)
def reset_fake():
    FakeLlm.log = []
    yield
    FakeLlm.question_response = QUESTIONS
    FakeLlm.variant_response = VARIANTS
    FakeLlm.answer_response = GROUNDED
    FakeLlm.judge_response = VERDICT
    FakeLlm.gate = None
    FakeLlm.raises = None
    FakeLlm.log = []


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth():
    token = base64.b64encode(b"tester:secret").decode()
    return {"Authorization": f"Basic {token}"}


@pytest.fixture
def studio(monkeypatch):
    """studio 모드 + 가짜 LLM.

    역할별 모델은 `ModelRoles.resolve()` 안에서 만들어지므로 가짜로 바꿀 자리는 여기 하나다.
    """
    monkeypatch.setattr("app.api.studio_generate.is_studio", lambda: True)
    monkeypatch.setattr("app.studio.generate.StudioLlm", FakeLlm)


@pytest.fixture
def doc(isolated_data):
    from pathlib import Path
    path = Path(isolated_data.raw_docs_dir) / "api-등록.md"
    path.write_text(DOC, encoding="utf-8")
    return path


# ─────────────────────────────────────────────────────────── 모드 게이팅


@pytest.mark.parametrize("method,path", [
    ("post", "/api/studio/generate"),
    ("get", "/api/studio/generate/progress"),
    ("post", "/api/studio/generate/stop"),
    ("get", "/api/studio/generate/result"),
    ("post", "/api/studio/generate/apply"),
    ("get", "/api/studio/generate/models"),
])
def test_serve_mode_blocks_generation(client, auth, method, path):
    body = {"json": {}} if method == "post" else {}
    response = getattr(client, method)(path, headers=auth, **body)
    assert response.status_code == 403


def test_generation_requires_auth(client):
    assert client.get("/api/studio/generate/progress").status_code == 401


# ─────────────────────────────────────────────────────────── 문서에서 생성


def test_generate_from_docs_creates_drafts(client, auth, studio, doc):
    client.post("/api/studio/generate", json={"source": "docs"}, headers=auth)
    assert runner.get_job().join(timeout=10)

    progress = client.get("/api/studio/generate/progress", headers=auth).json()
    assert progress["status"] == "done"

    drafts = client.get("/api/studio/generate/result", headers=auth).json()
    # 도입부 청크는 대상에서 빠지므로 '## API 등록 절차' 하나에서만 만들어진다.
    assert len(drafts) == 1
    assert drafts[0]["question"] == "API 등록은 어떻게 하나요?"
    # 답변은 여러 줄이다. 첫 줄만 남기면 반쪽짜리 답변이 검수로 넘어간다.
    assert "필수 입력 항목" in drafts[0]["answer"]
    # 문서끼리 참조하는 내부 표기가 말풍선에 그대로 찍히면 안 된다.
    assert "[[" not in drafts[0]["answer"]
    assert "등록 화면에서 진행합니다" in drafts[0]["answer"]
    assert drafts[0]["variants"] == ["API 등록 절차 알려주세요", "API 어떻게 등록해요?", "API 등록 방법"]
    assert drafts[0]["source_doc_ids"] == ["api-등록"]

    # 생성만으로는 QA 인덱스에 아무것도 들어가지 않는다.
    assert qa_store.load_qa() == []


def test_screen_loads_existing_drafts_on_open():
    """화면을 열 때 **이미 만들어 둔 초안**을 다시 읽어야 한다.

    초안은 파일에 남는다. 그런데 화면이 생성을 끝냈을 때만 결과 표를 채우면, 페이지를 새로
    열었을 때 진행 현황에는 "초안 12건"이 뜨는데 표는 비어 있다. 실제로 그 상태에서
    "12건을 어디서 보나"를 한참 찾았다.
    """
    from pathlib import Path
    js = (Path(__file__).resolve().parents[1] / "app" / "static" / "admin.js").read_text(encoding="utf-8")

    start = js.index("function renderAll(")
    body = js[start: js.index("\n  }", start)]
    assert "loadGenResult" in body, "화면을 열 때 초안을 불러오지 않습니다"


def test_generated_drafts_survive_restart(client, auth, studio, doc):
    """서버를 다시 띄워도 초안이 남아야 한다 — 수십 분짜리 배치 결과다."""
    client.post("/api/studio/generate", json={"source": "docs"}, headers=auth)
    runner.get_job().join(timeout=10)

    runner.reset_job()   # 재시작과 같은 상태(메모리 비움)

    drafts = client.get("/api/studio/generate/result", headers=auth).json()
    assert len(drafts) == 1


def test_non_korean_items_are_dropped(studio, doc):
    FakeLlm.question_response = "How do I register an API in the portal?"

    drafts = generate_from_docs([], roles=ModelRoles.single(FakeLlm()), variant_count=0).drafts

    assert drafts == []


def test_document_without_headings_is_not_skipped_entirely(studio, isolated_data):
    """헤딩이 없는 문서는 전부 도입부처럼 보인다. 그때까지 빼면 그 문서에서 아무것도 못 만든다."""
    from pathlib import Path
    path = Path(isolated_data.raw_docs_dir) / "메모.md"
    path.write_text(
        "API 등록은 API 그룹을 만든 뒤 등록 화면에서 진행합니다. 필수 항목은 API 명, Path, "
        "Method 이며 저장하면 승인 요청이 담당자에게 전달됩니다. 승인 후 배포 화면에서 반영하면 "
        "운영 환경에서 호출할 수 있습니다. 권한그룹을 비워두면 내부 관리자만 호출할 수 있습니다.",
        encoding="utf-8",
    )

    drafts = generate_from_docs([], roles=ModelRoles.single(FakeLlm()), variant_count=0).drafts

    assert len(drafts) == 1


def test_existing_question_is_not_regenerated(studio, doc):
    qa_store.upsert_item(qa_store.QaItem(
        qa_id="qa_1", question="API 등록은 어떻게 하나요?", answer="이미 있는 답변", status="approved"))

    drafts = generate_from_docs(
        [], roles=ModelRoles.single(FakeLlm()), variant_count=0,
        existing_questions={"api등록은어떻게하나요"},
    ).drafts

    assert drafts == []


def test_variants_exclude_the_question_itself(studio, doc):
    FakeLlm.variant_response = "API 등록은 어떻게 하나요?\nAPI 등록 방법\nAPI 등록 방법\n"

    drafts = generate_from_docs([], roles=ModelRoles.single(FakeLlm()), variant_count=5).drafts

    # 대표 질문과 같은 문구, 중복 변형은 벡터만 늘리고 중복 적중을 만든다.
    assert drafts[0].variants == ["API 등록 방법"]


def test_stop_keeps_what_was_made(studio, doc):
    stop = {"value": False}

    def should_stop() -> bool:
        # 첫 청크를 마친 뒤부터 중지 요청이 있는 상태로 만든다.
        was = stop["value"]
        stop["value"] = True
        return was

    drafts = generate_from_docs(
        [], roles=ModelRoles.single(FakeLlm()), variant_count=0, should_stop=should_stop).drafts

    assert len(drafts) == 1


def test_docs_path_also_drops_ungrounded_answers(studio, doc):
    """문서에서 만든 질문이어도 답변 단계의 근거 판정을 거친다.

    질문·답변을 한 번에 만들던 때는 이 판정이 문서 경로에 없었다. 청크를 줬으니 근거가 있다고
    본 것인데, 모델이 발췌 밖의 사전 지식으로 답을 채우는 경우를 걸러내지 못했다.
    """
    FakeLlm.answer_response = "근거: 없음\n답변:"

    drafts = generate_from_docs([], roles=ModelRoles.single(FakeLlm()), variant_count=0).drafts

    assert drafts == []


# ─────────────────────────────────────────────────────────── 역할별 모델


def test_each_role_calls_its_own_model(client, auth, studio, doc):
    """질문·변형은 질문 모델이, 답변은 답변 모델이 맡는다.

    2026-08-15 실측에서 큰 모델은 답변이 정확했지만 변형 질문의 표현 폭이 좁았다. 그래서 역할을
    나눴는데, 화면에서 고른 값이 실제 호출로 이어지지 않으면 그 판단이 통째로 무의미해진다.
    """
    client.post("/api/studio/generate", headers=auth, json={
        "source": "docs", "question_model": "q-model", "answer_model": "a-model", "variant_count": 3,
    })
    assert runner.get_job().join(timeout=10)

    by_kind = {}
    for model, kind in FakeLlm.log:
        by_kind.setdefault(kind, set()).add(model)

    assert by_kind["question"] == {"q-model"}
    assert by_kind["variant"] == {"q-model"}
    assert by_kind["answer"] == {"a-model"}

    progress = client.get("/api/studio/generate/progress", headers=auth).json()
    assert progress["question_model"] == "q-model"
    assert progress["answer_model"] == "a-model"
    # 화면 한 줄 표시. 역할이 갈렸다는 것이 진행 상황에서 바로 보여야 한다.
    assert "q-model" in progress["model"] and "a-model" in progress["model"]


def test_single_model_field_still_applies_to_both_roles(client, auth, studio, doc):
    """역할을 나누기 전 화면이 보내던 `model` 필드. 두 역할 모두에 적용한다."""
    client.post("/api/studio/generate",
                json={"source": "docs", "model": "one-model", "variant_count": 0}, headers=auth)
    assert runner.get_job().join(timeout=10)

    assert {model for model, _ in FakeLlm.log} == {"one-model"}
    progress = client.get("/api/studio/generate/progress", headers=auth).json()
    # 같은 모델이면 "질문 A · 답변 A" 로 늘어놓지 않는다.
    assert progress["model"] == "one-model"


def test_role_models_fall_back_to_settings(client, auth, studio, doc, monkeypatch, isolated_data):
    """화면이 아무것도 안 고르면 `.env` 의 역할별 값을 쓴다."""
    monkeypatch.setattr(isolated_data, "ollama_question_model", "env-question")
    monkeypatch.setattr(isolated_data, "ollama_answer_model", "env-answer")

    client.post("/api/studio/generate", json={"source": "docs", "variant_count": 0}, headers=auth)
    assert runner.get_job().join(timeout=10)

    assert {model for model, _ in FakeLlm.log} == {"env-question", "env-answer"}


def test_model_list_excludes_embedding_models(client, auth, studio, monkeypatch):
    """임베딩 전용 모델은 생성에 못 쓴다. 고를 수 있게 두면 고르는 순간 배치가 통째로 실패한다."""
    monkeypatch.setattr("app.api.studio_generate.installed_models",
                        lambda: ["gemma4:12b", "gemma4:latest"])

    body = client.get("/api/studio/generate/models", headers=auth).json()

    assert body["models"] == ["gemma4:12b", "gemma4:latest"]
    assert body["question_default"] and body["answer_default"]


# ─────────────────────────────────────────────────────────── 채점(judge)


def test_no_judge_model_means_no_score(client, auth, studio, doc):
    """채점 모델을 안 정하면 채점하지 않는다.

    답변 모델로 자기 답을 채점하면 점수가 후해진다. 있으나 마나 한 점수가 붙는 것보다
    아예 없는 편이 낫다 — 숫자가 있으면 검수자가 그것을 믿는다.
    """
    client.post("/api/studio/generate", json={"source": "docs", "variant_count": 0}, headers=auth)
    assert runner.get_job().join(timeout=10)

    drafts = client.get("/api/studio/generate/result", headers=auth).json()
    assert drafts[0]["score"] == 0
    assert not any(kind == "judge" for _, kind in FakeLlm.log)


def test_judge_scores_with_its_own_model(client, auth, studio, doc):
    client.post("/api/studio/generate", headers=auth, json={
        "source": "docs", "answer_model": "a-model", "judge_model": "j-model", "variant_count": 0,
    })
    assert runner.get_job().join(timeout=10)

    assert ("j-model", "judge") in FakeLlm.log
    # 답을 쓴 모델이 자기 답을 채점하면 안 된다.
    assert ("a-model", "judge") not in FakeLlm.log

    draft = client.get("/api/studio/generate/result", headers=auth).json()[0]
    assert draft["score"] == 5
    assert draft["judge_model"] == "j-model"
    assert "발췌" in draft["judge_reason"]


def test_unreadable_verdict_is_not_a_zero_score_draft_loss(client, auth, studio, doc):
    """판정 형식을 못 읽었다고 초안을 버리지 않는다. 1차는 이때 1점(최악)을 줬다."""
    FakeLlm.judge_response = "음… 5점 정도로 보입니다."

    client.post("/api/studio/generate", headers=auth,
                json={"source": "docs", "judge_model": "j-model", "variant_count": 0})
    assert runner.get_job().join(timeout=10)

    drafts = client.get("/api/studio/generate/result", headers=auth).json()
    assert len(drafts) == 1                 # 초안은 남는다
    assert drafts[0]["score"] == 0          # 점수는 '모름'
    assert "읽지 못했습니다" in drafts[0]["judge_reason"]


def test_judge_asks_for_json_and_disables_thinking(studio, doc, monkeypatch):
    """채점 호출은 **JSON 강제 + 추론 끄기**로 나가야 한다.

    추론 모델은 사고 과정을 본문에 쏟아내 출력 예산을 다 쓴다. 실제로 `qwen3:4b` 가 영어
    사고 과정 4,071자를 뱉고 JSON 에 도달하지 못해, 멀쩡한 답변이 '판정 실패'로 걸러졌다.
    `think=False` 만으로는 막지 못했다.
    """
    seen: dict = {}

    class RecordingLlm(FakeLlm):
        def chat(self, prompt, system=None, json_format=False):
            if "채점하세요" in prompt:
                seen["json_format"] = json_format
                seen["prompt"] = prompt
            return super().chat(prompt, system, json_format)

    generate_from_docs(
        [], roles=ModelRoles.single(FakeLlm(), judge=RecordingLlm("qwen3:4b")), variant_count=0)

    assert seen.get("json_format") is True, "채점은 JSON 강제로 불러야 합니다"


def test_no_think_switch_is_added_for_reasoning_models():
    """`/no_think` 는 프롬프트로만 확실히 꺼진다 — 모델 이름으로 판단한다."""
    from app.studio.llm import _needs_no_think

    assert _needs_no_think("qwen3:4b")
    assert not _needs_no_think("gemma4:12b")


def test_judge_failure_does_not_fail_the_batch(studio, doc):
    """채점은 부가 정보다. 판정 모델이 죽었다고 수십 분짜리 배치를 버리면 안 된다."""
    class DeadJudge(FakeLlm):
        def chat(self, prompt, system=None):
            raise RuntimeError("판정 모델 연결 실패")

    drafts = generate_from_docs(
        [], roles=ModelRoles.single(FakeLlm(), judge=DeadJudge("j-model")), variant_count=0).drafts

    assert len(drafts) == 1
    assert drafts[0].score == 0


def test_low_score_drafts_are_left_out_of_apply(client, auth, studio, doc):
    """점수 미달은 반영에서 빠지되 초안 목록에는 남는다 — 왜 빠졌는지 보여야 고칠 수 있다."""
    FakeLlm.judge_response = '{"score": 2, "reason": "발췌에 없는 내용이 섞였습니다."}'
    client.post("/api/studio/generate", headers=auth,
                json={"source": "docs", "judge_model": "j-model", "variant_count": 0})
    assert runner.get_job().join(timeout=10)

    result = client.post("/api/studio/generate/apply", json={}, headers=auth).json()

    assert (result["saved"], result["low_score"], result["min_score"]) == (0, 1, 4)
    assert qa_store.load_qa() == []
    assert len(client.get("/api/studio/generate/result", headers=auth).json()) == 1


def test_apply_min_score_can_be_relaxed_per_request(client, auth, studio, doc):
    FakeLlm.judge_response = '{"score": 3, "reason": "일부가 모호합니다."}'
    client.post("/api/studio/generate", headers=auth,
                json={"source": "docs", "judge_model": "j-model", "variant_count": 0})
    assert runner.get_job().join(timeout=10)

    result = client.post("/api/studio/generate/apply", json={"min_score": 3}, headers=auth).json()

    assert result["saved"] == 1
    assert qa_store.load_qa()[0].status == "pending"   # 채점이 승인을 대신하지는 않는다


def test_unjudged_batch_is_not_blocked_by_the_score_filter(client, auth, studio, doc):
    """채점을 안 한 배치는 전부 0점이다. 그것까지 걸러내면 판정 모델이 없는 사람은
    아무것도 반영하지 못한다."""
    client.post("/api/studio/generate", json={"source": "docs", "variant_count": 0}, headers=auth)
    assert runner.get_job().join(timeout=10)

    result = client.post("/api/studio/generate/apply", json={}, headers=auth).json()

    assert result["saved"] == 1
    assert result["low_score"] == 0
    assert result["min_score"] == 0   # 화면이 '채점 기준 없음'으로 표시할 수 있게


# ─────────────────────────────────────────────────────────── 질문에서 생성


def test_question_without_grounding_is_dropped(studio, doc):
    """근거가 없으면 답을 지어내지 않는다 — 문서 공백을 덮으면 안 된다."""
    DocIndex().ingest_file(doc, force=True)
    FakeLlm.answer_response = "근거: 없음\n답변:"

    drafts = generate_from_questions(
        ["API 호출 요금은 얼마인가요?"], roles=ModelRoles.single(FakeLlm()), variant_count=0).drafts

    assert drafts == []


def test_question_with_grounding_becomes_draft(studio, doc):
    DocIndex().ingest_file(doc, force=True)

    drafts = generate_from_questions(
        ["API 등록 절차가 궁금합니다"], roles=ModelRoles.single(FakeLlm()), variant_count=0).drafts

    assert len(drafts) == 1
    assert drafts[0].answer.startswith("API 그룹을 먼저")
    assert drafts[0].source_doc_ids == ["api-등록"]


def test_category_target_uses_registered_questions(client, auth, studio, doc):
    from app.core.categories import Category, CategoryGroup, CategoryStore, save_categories
    DocIndex().ingest_file(doc, force=True)
    save_categories(CategoryStore(groups=[CategoryGroup(
        group_id="api", group_name="API 관리",
        categories=[Category(category_id="api_reg", name="API 등록 절차", group_id="api",
                             questions=["API 등록은 어떻게 하나요?"])],
    )]))

    client.post("/api/studio/generate",
                json={"source": "category", "category_id": "api_reg", "variant_count": 0},
                headers=auth)
    assert runner.get_job().join(timeout=10)

    drafts = client.get("/api/studio/generate/result", headers=auth).json()
    assert [d["question"] for d in drafts] == ["API 등록은 어떻게 하나요?"]
    assert drafts[0]["category_id"] == "api_reg"


def test_category_without_questions_is_rejected(client, auth, studio):
    from app.core.categories import Category, CategoryGroup, CategoryStore, save_categories
    save_categories(CategoryStore(groups=[CategoryGroup(
        group_id="api", group_name="API 관리",
        categories=[Category(category_id="empty", name="빈 주제", group_id="api")],
    )]))

    response = client.post("/api/studio/generate",
                           json={"source": "category", "category_id": "empty"}, headers=auth)

    assert response.status_code == 400


# ─────────────────────────────────────────────────────────── 반영(apply)


def test_apply_saves_as_pending_and_stays_out_of_index(client, auth, studio, doc):
    client.post("/api/studio/generate", json={"source": "docs"}, headers=auth)
    runner.get_job().join(timeout=10)

    result = client.post("/api/studio/generate/apply", json={}, headers=auth).json()

    assert result["saved"] == 1
    saved = qa_store.load_qa()[0]
    assert saved.status == "pending"
    assert saved.created_by == "ai"
    assert saved.variants
    # 검수 전 답변이 챗봇 검색에 걸리면 이 프로젝트의 유일한 품질 보증이 무너진다.
    assert QaIndex().count() == 0
    assert qa_store.serving_items() == []


def test_apply_twice_does_not_duplicate(client, auth, studio, doc):
    client.post("/api/studio/generate", json={"source": "docs"}, headers=auth)
    runner.get_job().join(timeout=10)

    client.post("/api/studio/generate/apply", json={}, headers=auth)
    second = client.post("/api/studio/generate/apply", json={}, headers=auth).json()

    assert second["saved"] == 0
    assert second["skipped"] == 1
    assert len(qa_store.load_qa()) == 1


def test_apply_only_selected_drafts(client, auth, studio, doc):
    client.post("/api/studio/generate", json={"source": "docs"}, headers=auth)
    runner.get_job().join(timeout=10)

    result = client.post("/api/studio/generate/apply",
                         json={"draft_ids": ["없는-초안"]}, headers=auth).json()

    assert result["saved"] == 0
    assert qa_store.load_qa() == []
    # 고르지 않은 초안에 반영 표시가 붙으면 검수자가 다시 넣을 수 없게 된다.
    drafts = client.get("/api/studio/generate/result", headers=auth).json()
    assert drafts[0]["applied_qa_id"] is None


# ─────────────────────────────────────────────────────────── 실행 상태


def test_second_run_is_rejected_while_running(client, auth, studio, doc):
    FakeLlm.gate = threading.Event()
    client.post("/api/studio/generate", json={"source": "docs"}, headers=auth)
    try:
        response = client.post("/api/studio/generate", json={"source": "docs"}, headers=auth)
        assert response.status_code == 409
    finally:
        FakeLlm.gate.set()
    runner.get_job().join(timeout=10)


def test_stop_marks_job_stopped(client, auth, studio, doc):
    FakeLlm.gate = threading.Event()
    client.post("/api/studio/generate", json={"source": "docs"}, headers=auth)

    stopped = client.post("/api/studio/generate/stop", headers=auth).json()
    assert "중지" in stopped["stage"]
    FakeLlm.gate.set()
    assert runner.get_job().join(timeout=10)

    assert client.get("/api/studio/generate/progress", headers=auth).json()["status"] == "stopped"


def test_empty_llm_response_fails_the_job(client, auth, studio, doc):
    """추론 모델이 content 를 비우는 경우. '완료, 0건' 으로 끝나면 원인을 못 찾는다."""
    FakeLlm.raises = EmptyLlmResponse("빈 응답입니다. OLLAMA_THINK=false 를 확인하세요.")

    client.post("/api/studio/generate", json={"source": "docs"}, headers=auth)
    runner.get_job().join(timeout=10)

    progress = client.get("/api/studio/generate/progress", headers=auth).json()
    assert progress["status"] == "failed"
    # 화면에 그대로 뜨는 문구다. 여기에 원인 힌트가 없으면 검수자가 프롬프트부터 고치기 시작한다.
    assert "OLLAMA_THINK" in progress["error"]
