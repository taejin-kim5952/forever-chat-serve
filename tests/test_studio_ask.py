"""챗봇의 `AI 답변` 스위치 — studio 전용 경로.

이 기능은 이 제품의 전제("답을 지어내지 않는다 · 운영에서 LLM을 부르지 않는다")에 가장
가까이 붙어 있다. 그래서 여기서 지키는 것은 기능이 아니라 **경계**다.

- 운영(serve)에서는 열리지 않는다. 운영 파드에는 GPU가 없고, 그것이 이 저장소가 갈라져
  나온 이유다
- 근거를 못 찾으면 답하지 않는다. 생성 경로와 **같은 함수**(`grounded_answer`)를 쓴다
- 검수된 답변과 섞이지 않는다 — QA 인덱스를 보지 않고 문서만 본다
- LLM 이 죽어 있어도 화면은 돌아간다. 참고 자료라도 보여주는 편이 오류 화면보다 낫다
- 질문 이력에 남기지 않는다. 검수자의 시험 질문이 실사용 통계를 흐리면 안 된다
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.runtime_config import RuntimeConfig, save_runtime_config
from app.main import app
from app.pipeline.retrieve import get_retriever

GROUNDED = "근거: 있음\n답변: API 그룹을 먼저 만든 뒤 등록 화면에서 진행합니다."
NOT_GROUNDED = "근거: 없음\n답변:"

DOC = """---
title: API 등록
---

# API 등록

## 등록 절차

API 를 등록하려면 먼저 API 그룹(SPC)을 만들어야 합니다. 그 다음 등록 화면에서 API 명과
Path, Method 를 입력하고 저장하면 됩니다. 저장한 뒤에는 검증 단계를 거쳐 배포를 신청합니다.
"""


class FakeLlm:
    """`app/studio/ask.py` 가 부르는 모양만 흉내 낸다."""

    response = GROUNDED
    raises: Exception | None = None
    used_model = ""

    def __init__(self, model=None, host=None):
        self.model = model or "fake-llm"
        FakeLlm.used_model = self.model

    def source_budget_chars(self) -> int:
        return 5000

    def chat(self, prompt: str, system: str | None = None, json_format: bool = False,
             think: bool = False, on_think=None) -> str:
        if FakeLlm.raises:
            raise FakeLlm.raises
        FakeLlm.thought = think
        # `추론 과정 보기` 를 켠 요청은 사고 과정을 조각마다 넘긴다. 가짜도 그 모양을 지킨다 —
        # 안 그러면 화면이 영영 기다리는 배선을 테스트가 통과시킨다.
        if on_think is not None:
            on_think("생각하는 중")
        return FakeLlm.response


@pytest.fixture(autouse=True)
def reset_fake():
    FakeLlm.response, FakeLlm.raises, FakeLlm.used_model = GROUNDED, None, ""
    FakeLlm.thought = False


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def studio(monkeypatch):
    monkeypatch.setattr("app.api.studio_ask.is_studio", lambda: True)
    monkeypatch.setattr("app.studio.ask.StudioLlm", FakeLlm)


@pytest.fixture
def docs(isolated_data):
    docs_dir = Path(isolated_data.raw_docs_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "api-등록.md").write_text(DOC, encoding="utf-8")
    get_retriever().doc_index.ingest_dir(force=True)
    return docs_dir


def ask(client, question="API 등록은 어떻게 하나요?"):
    return client.post("/api/studio/ask", json={"question": question})


# ── 경계 ─────────────────────────────────────────────────────────────────────


def test_serve_mode_refuses(client, docs):
    """운영에는 LLM 이 없다. 화면이 스위치를 감추지만 API 도 따로 막는다."""
    response = ask(client)

    assert response.status_code == 403
    assert "검수된 답변만" in response.json()["detail"]


def test_operational_path_does_not_import_studio():
    """운영 경로가 `app/studio/` 를 부르면 프로젝트의 전제가 구조에서 사라진다."""
    source = Path("app/pipeline/retrieve.py").read_text(encoding="utf-8")
    assert "app.studio" not in source

    chat_api = Path("app/api/ask.py").read_text(encoding="utf-8")
    assert "app.studio" not in chat_api, "챗봇 공개 API 가 studio 를 import 합니다"


def test_empty_question_is_refused(client, studio, docs):
    assert ask(client, "   ").status_code == 400


# ── 답변 ─────────────────────────────────────────────────────────────────────


def test_answers_from_documents_with_sources(client, studio, docs):
    """켜면 문서에서 찾아 정리하고, 근거로 삼은 문서를 함께 낸다."""
    body = ask(client).json()

    assert body["result_type"] == "ai_answer"
    assert "API 그룹" in body["answer"]
    assert body["related_docs"], "근거 문서가 비어 있으면 사람이 답을 확인할 수 없습니다"
    assert body["related_docs"][0]["doc_id"] == "api-등록"
    assert body["related_docs"][0]["chunk_id"], "청크 id 가 없으면 걸린 절을 열 수 없습니다"


def test_does_not_answer_without_grounds(client, studio, docs):
    """모델이 `근거: 없음` 을 선언하면 답을 만들지 않는다 — 지어내지 않는다는 규칙 그대로."""
    FakeLlm.response = NOT_GROUNDED

    body = ask(client).json()

    assert body["result_type"] == "related_docs"
    assert body["answer"] is None
    assert body["related_docs"], "답이 없어도 찾은 문서는 보여 준다"


def test_llm_failure_falls_back_to_documents(client, studio, docs):
    """Ollama 가 꺼져 있어도 화면은 돌아간다. 오류 화면보다 참고 자료가 낫다."""
    FakeLlm.raises = RuntimeError("connection refused")

    body = ask(client).json()

    assert body["result_type"] == "related_docs"
    assert body["related_docs"]


def test_unrelated_question_finds_nothing(client, studio, docs):
    """문서가 임계값에 못 미치면 LLM 을 부르지 않는다 — 근거 없이 부를 이유가 없다.

    임계값은 관리자 화면(탭 ⑧)의 그 값을 그대로 쓴다. 여기서 따로 정하면 설정을 내려도
    이쪽만 그대로여서 "왜 여기서는 안 걸리지"가 된다. 그래서 설정을 올려 확인한다.
    """
    save_runtime_config(RuntimeConfig(
        qa_match_threshold=0.99, related_docs_floor=0.98,
        related_docs_count=3, qa_top_k=10, doc_top_k=10,
    ))

    body = ask(client, "점심 메뉴 추천해 주세요").json()

    assert body["result_type"] == "unresolved"
    assert body["related_docs"] == []
    assert FakeLlm.used_model == "", "근거가 없는데 모델을 불렀습니다"


def test_uses_the_answer_model(client, studio, docs, isolated_data, monkeypatch):
    """역할별 모델을 쓰는 설치에서는 답변 모델이 이 자리에 맞는다."""
    monkeypatch.setattr(isolated_data, "ollama_answer_model", "big-answer-model")

    ask(client)

    assert FakeLlm.used_model == "big-answer-model"


def test_context_uses_the_whole_chunk_not_the_card_excerpt():
    """화면 카드용 발췌(200자)를 모델에 주면 문장이 끊긴 채로 답을 만들게 된다.

    근거가 있는데도 `근거: 없음` 이 나오는 흔한 원인이라, 프롬프트에는 청크 전문을 넣는다.
    """
    from app.studio.ask import build_context

    hit = {"title": "문서", "section": "절", "excerpt": "앞부분만…", "text": "앞부분만 있는 게 아니라 뒷부분까지."}

    context = build_context([hit])

    assert "뒷부분까지" in context
    assert "앞부분만…" not in context


# ── 섞이지 않는다 ────────────────────────────────────────────────────────────


def test_approved_qa_is_not_used(client, studio, docs):
    """켜면 AI 정리, 끄면 검수된 답변. 섞으면 화면을 보는 사람이 어느 쪽인지 알 수 없다."""
    from app.qa import store as qa_store
    from app.qa.index import QaIndex

    item = qa_store.upsert_item(qa_store.QaItem(
        qa_id="qa_test", question="API 등록은 어떻게 하나요?",
        answer="검수된 답변입니다.", status="approved",
    ))
    QaIndex().upsert_item(item)

    body = ask(client).json()

    assert body["result_type"] == "ai_answer"
    assert "검수된 답변입니다." not in (body["answer"] or "")


def test_nothing_is_written_to_the_question_log(client, studio, docs, isolated_data):
    """검수자의 시험 질문이 '무엇을 자주 묻는가'를 오염시키면 안 된다."""
    log = Path(isolated_data.question_log_file)
    before = log.read_text(encoding="utf-8") if log.exists() else ""

    ask(client)

    after = log.read_text(encoding="utf-8") if log.exists() else ""
    assert after == before


# ── 후보는 넓게, 카드는 AI 가 고른 것만 ──────────────────────────────────────


def test_only_the_cited_sources_are_shown(client, studio, isolated_data):
    """AI 가 쓰지 않은 문서는 참고 자료에도 내보내지 않는다.

    답에 반영되지 않은 문서가 '참고 자료'로 붙어 있으면 사람이 그것까지 근거로 읽는다.
    이 기능의 요점이 "AI 가 뺄 건 뺀다" 이므로, 뺀 결과가 화면에도 보여야 한다.
    """
    docs_dir = Path(isolated_data.raw_docs_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)
    for name in ["가", "나", "다"]:
        (docs_dir / f"문서-{name}.md").write_text(DOC.replace("API 등록", f"주제 {name}"), encoding="utf-8")
    get_retriever().doc_index.ingest_dir(force=True)
    FakeLlm.response = """근거: 있음
사용: 2
답변: 두 번째 발췌만 썼습니다."""

    body = ask(client).json()

    assert body["result_type"] == "ai_answer"
    assert len(body["related_docs"]) == 1, "AI 가 쓰지 않은 문서까지 카드로 나갔습니다"


def test_falls_back_when_the_model_cites_nothing(client, studio, docs):
    """번호를 못 읽었다고 후보 8건을 전부 카드로 내보내면 지금보다 나쁘다."""
    FakeLlm.response = """근거: 있음
답변: 번호를 안 밝혔습니다."""

    body = ask(client).json()

    assert body["result_type"] == "ai_answer"
    assert 0 < len(body["related_docs"]) <= 3


def test_the_used_line_never_leaks_into_the_answer(client, studio, docs):
    """`답변:` 라벨을 빼먹는 모델이 있어서 라벨 없는 본문도 받아 준다.

    그때 `사용: 1` 줄이 답변 첫 줄로 섞이면 안 된다.
    """
    FakeLlm.response = """근거: 있음
사용: 1
라벨 없이 본문만 왔습니다."""

    body = ask(client).json()

    assert body["answer"] == "라벨 없이 본문만 왔습니다."


def test_context_budget_is_split_across_candidates():
    """예산을 통째로 넘기면 `llm.fit()` 이 뒤를 잘라 **마지막 후보가 통째로 사라진다.**

    그러면 AI 는 보지도 못한 것을 안 골랐을 뿐인데 화면에서는 '판단해서 뺐다'로 보인다.
    """
    from app.studio.ask import MIN_SOURCE_CHARS, build_context

    hits = [{"title": f"문서{i}", "section": "절", "text": "가" * 3000} for i in range(8)]

    context = build_context(hits, budget=4000)

    assert all(f"[{i}]" in context for i in range(1, 9)), "뒤쪽 후보가 사라졌습니다"
    # 너무 잘게 나누지도 않는다 — 200자만 남은 발췌는 문장이 끊겨 없느니만 못하다.
    assert context.count("가" * MIN_SOURCE_CHARS) == 8


# ── 마크다운 다듬기 (2026-10-07) ─────────────────────────────────────────────


def test_an_empty_table_is_removed_not_shown():
    """꾸미라고 하면 모델이 **틀을 먼저 짜 놓고** 못 채운 칸에 `(내용 없음)` 을 적는다.

    `gemma4:latest` 에서 되풀이됐고 프롬프트로 금지해도 지키지 않았다. 사용자에게
    `(상세 내용 없음)` 이 든 표가 나가는 것은 답이 없는 것보다 나쁘다 — 뭔가 있는 줄 알고
    읽다가 아무것도 없다는 걸 알게 된다.
    """
    from app.studio.ask import tidy_markdown

    out = tidy_markdown(
        "화면 구성입니다.\n\n| 구분 | 세부 내용 |\n| :--- | :--- |\n"
        "| **기본 정보** | (상세 내용 없음) |\n| **연동 설정** | (내용 없음) |"
    )

    assert "|" not in out, f"빈 표가 남았습니다: {out}"
    assert "화면 구성입니다." in out, "표만 지워야 하는데 본문까지 지웠습니다"


def test_a_table_with_real_rows_is_kept():
    """채워진 줄이 하나라도 있으면 표는 남긴다 — 표 자체는 읽기 좋은 모양이다."""
    from app.studio.ask import tidy_markdown

    out = tidy_markdown("| 구분 | 내용 |\n| --- | --- |\n| 기본 정보 | 이름·설명 |\n| 연동 설정 | (없음) |")

    assert "기본 정보 | 이름·설명" in out
    assert "(없음)" not in out, "빈 줄은 빠져야 합니다"


def test_backticks_and_bold_are_not_stacked():
    """`` `**저장**` `` 로 쓰면 화면이 코드로 그려 **별표가 그대로 보인다.**"""
    from app.studio.ask import tidy_markdown

    assert tidy_markdown("`**저장**` 버튼") == "**저장** 버튼"
    assert tidy_markdown("**`신규 등록`** 을 누릅니다") == "**신규 등록** 을 누릅니다"


def test_an_empty_list_item_is_dropped():
    from app.studio.ask import tidy_markdown

    out = tidy_markdown("- **기본 정보**: (내용 없음)\n- **파라미터**: 트리로 편집합니다")

    assert out == "- **파라미터**: 트리로 편집합니다"
