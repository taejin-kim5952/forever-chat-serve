"""AI 프로젝트 미팅 — 참가자와 회의.

여기서 지키는 것은 **경계**다.

- 회의는 LLM 을 부른다. 운영(serve)에서는 열리면 안 된다 — 이 제품의 전제다
- 참가자 **목록**은 운영에서도 열려야 한다. 거기서 막히면 화면이 메뉴를 못 그린다
- 고른 순서가 아니라 **정해 둔 순서**로 말한다. 그래야 같은 조합의 결과를 견줄 수 있다
"""

import base64

import pytest
from fastapi.testclient import TestClient

from app.core import personas as personas_mod
from app.main import app

AUTH = {"Authorization": "Basic " + base64.b64encode(b"tester:secret").decode()}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def studio(monkeypatch):
    monkeypatch.setattr("app.api.admin_personas.is_studio", lambda: True)
    monkeypatch.setattr("app.api.meeting.is_studio", lambda: True)


def save(client, personas):
    return client.put("/api/admin/personas", headers=AUTH, json={"personas": personas})


# ── 참가자 ─────────────────────────────────────────────────────────────────


def test_a_fresh_install_starts_with_default_participants(client, isolated_data):
    """빈 목록을 주지 않는다 — 처음 들어온 사람이 무엇을 만들어야 할지 모른 채 빈 화면을 본다."""
    body = client.get("/api/meeting/personas").json()

    names = [p["name"] for p in body["personas"]]
    assert "기획자" in names and "개발자" in names
    assert body["max_in_meeting"] >= 2


def test_saving_keeps_the_order_as_speaking_order(client, studio, isolated_data):
    """보낸 순서가 **발언 순서**다. 저장하고 다시 읽어도 그대로여야 한다."""
    save(client, [
        {"name": "PM"}, {"name": "기획자"}, {"name": "개발자"},
    ])

    names = [p["name"] for p in client.get("/api/admin/personas", headers=AUTH).json()["personas"]]
    assert names == ["PM", "기획자", "개발자"]


def test_korean_names_get_a_usable_id(client, studio, isolated_data):
    """한글 이름을 그대로 id 로 쓰면 주소와 쿼리에서 인코딩이 섞인다."""
    save(client, [{"name": "기획자"}])

    pid = client.get("/api/admin/personas", headers=AUTH).json()["personas"][0]["persona_id"]
    assert pid.isascii() and pid


def test_an_existing_id_is_not_regenerated(client, studio, isolated_data):
    """id 가 바뀌면 그 참가자를 고른 회의와 이어지지 않는다."""
    save(client, [{"name": "기획자"}])
    pid = client.get("/api/admin/personas", headers=AUTH).json()["personas"][0]["persona_id"]

    save(client, [{"persona_id": pid, "name": "서비스 기획자"}])

    after = client.get("/api/admin/personas", headers=AUTH).json()["personas"][0]
    assert after["persona_id"] == pid
    assert after["name"] == "서비스 기획자"


def test_a_nameless_participant_is_refused(client, studio, isolated_data):
    """이름이 비면 화면에서 누가 누군지 가를 수 없다."""
    assert save(client, [{"name": "   "}]).status_code == 400


def test_disabled_participants_do_not_show_up_in_the_picker(client, studio, isolated_data):
    """꺼 둔 참가자는 **고르는 목록에도** 나오지 않는다. 관리 화면에는 남는다."""
    save(client, [{"name": "기획자"}, {"name": "개발자", "enabled": False}])

    picker = [p["name"] for p in client.get("/api/meeting/personas").json()["personas"]]
    admin = [p["name"] for p in client.get("/api/admin/personas", headers=AUTH).json()["personas"]]

    assert picker == ["기획자"]
    assert len(admin) == 2


def test_pick_follows_the_saved_order_not_the_asked_order(client, studio, isolated_data):
    """고른 순서를 쓰면 같은 조합인데 **부른 순서에 따라 대화가 달라진다.**"""
    save(client, [{"name": "기획자"}, {"name": "개발자"}, {"name": "PM"}])
    ids = [p.persona_id for p in personas_mod.enabled()]

    chosen = personas_mod.pick([ids[2], ids[0]])

    assert [p.persona_id for p in chosen] == [ids[0], ids[2]]


# ── 운영과 스튜디오의 경계 ─────────────────────────────────────────────────


def test_the_meeting_is_refused_in_serve_mode(client, isolated_data):
    """회의는 LLM 을 부른다. 운영에서 열리면 이 프로젝트의 전제가 깨진다."""
    response = client.get("/api/meeting/stream", params={"topic": "무엇을 먼저 할까요"})

    assert response.status_code == 403


def test_the_picker_still_opens_in_serve_mode(client, isolated_data):
    """목록까지 막으면 화면이 메뉴를 못 그리고 '왜 비어 있지' 가 된다."""
    body = client.get("/api/meeting/personas").json()

    assert body["personas"], "운영에서도 목록은 보여야 합니다"
    # 화면이 **먼저** 알아야 버튼을 잠글 수 있다. 눌러 보고 403 을 받는 것은 늦다.
    assert body["available"] is False


def test_editing_participants_is_refused_in_serve_mode(client, isolated_data):
    """참가자는 LLM 에게 줄 프롬프트다. 운영에서 고치면 반입 때마다 덮여 사라진다."""
    assert save(client, [{"name": "기획자"}]).status_code == 403


def test_a_meeting_without_participants_is_refused(client, studio, isolated_data):
    """한 명도 없으면 회의가 아니다. 빈 화면을 돌려주느니 이유를 말한다."""
    response = client.get("/api/meeting/stream",
                          params={"topic": "무엇을 먼저 할까요", "personas": ""})

    assert response.status_code == 400


# ── 운영 경로가 studio 를 끌어오지 않는가 ─────────────────────────────────


def test_the_meeting_module_is_not_imported_by_the_serving_path():
    """`app/studio/` 를 운영 경로에서 import 하면 전제가 깨진다(CLAUDE.md).

    회의 컨트롤러는 모듈 맨 위가 아니라 **함수 안에서** studio 를 불러온다.
    """
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "app" / "api" / "meeting.py").read_text(
        encoding="utf-8")
    head = source[:source.index("router = APIRouter")]

    assert "from app.studio" not in head, (
        "모듈을 읽는 것만으로 studio 가 따라옵니다 — 함수 안에서 불러오세요"
    )


# ── 회의를 끝까지 돌려 본다 ───────────────────────────────────────────────


def test_a_meeting_runs_end_to_end(client, studio, isolated_data, monkeypatch):
    """**실제로 한 바퀴 돌려 봐야** 잡히는 것들이 있다.

    2026-10-07 에 `doc_index.search` 의 반환값을 둘로 받다가(`qa_index.search` 와 헷갈려)
    회의가 열리자마자 죽었다. 그때 테스트 12개는 전부 통과하고 있었다 — 경계(403·400)와
    참가자 저장만 보고 있었고, **회의를 한 번도 끝까지 돌리지 않았기 때문**이다.

    모델만 가짜로 바꾸고 검색·스트리밍은 진짜를 쓴다.
    """
    class FakeLlm:
        model = "fake-llm"

        def __init__(self, *a, **kw):
            pass

        def source_budget_chars(self):
            return 2000

        def fit(self, text, label=""):
            # 진짜 `StudioLlm` 이 가진 것이다. 가짜가 빠뜨리면 **테스트만 통과하고 운영에서
            # 터진다** — 2026-10-07 에 그랬다.
            return text

        def chat(self, prompt, system=None, **kw):
            return "한 마디 하겠습니다."

    monkeypatch.setattr("app.studio.meeting.StudioLlm", FakeLlm)
    save(client, [{"name": "기획자"}, {"name": "개발자"}])
    ids = [p.persona_id for p in personas_mod.enabled()]

    body = client.get("/api/meeting/stream", params={
        "topic": "API Link 고도화", "personas": ",".join(ids), "rounds": "1",
    }).text

    assert "event: opened" in body
    assert body.count("event: turn") == 2, "참가자 수만큼 발언이 나와야 합니다"
    assert "event: summary" in body
    assert "event: done" in body


def test_a_meeting_opens_even_with_no_matching_documents(client, studio, isolated_data,
                                                         monkeypatch):
    """자료가 없어도 **열리고**, 자료가 없다고 알려 준다.

    자료가 없다고 회의가 안 열리면 새 프로젝트에서는 쓸 수가 없다. 대신 참가자들에게
    '아는 척하지 마라' 고 일러 두고, 화면에도 그렇게 적는다.
    """
    class FakeLlm:
        model = "fake-llm"

        def __init__(self, *a, **kw):
            pass

        def source_budget_chars(self):
            return 2000

        def fit(self, text, label=""):
            # 진짜 `StudioLlm` 이 가진 것이다. 가짜가 빠뜨리면 **테스트만 통과하고 운영에서
            # 터진다** — 2026-10-07 에 그랬다.
            return text

        def chat(self, prompt, system=None, **kw):
            return "자료가 없어 말하기 어렵습니다."

    monkeypatch.setattr("app.studio.meeting.StudioLlm", FakeLlm)
    save(client, [{"name": "기획자"}])
    ids = [p.persona_id for p in personas_mod.enabled()]

    body = client.get("/api/meeting/stream", params={
        "topic": "자료에 없는 주제", "personas": ",".join(ids),
    }).text

    assert "event: opened" in body
    assert "event: turn" in body


# ── 참가자마다 다른 모델 ───────────────────────────────────────────────────


def test_each_participant_can_use_a_different_model(client, studio, isolated_data, monkeypatch):
    """기획자는 qwen, 개발자는 gemma 처럼 **역할마다 다른 모델**을 쓸 수 있어야 한다.

    역할마다 잘하는 모델이 다르다. 비워 두면 설치 기본 모델을 쓴다.
    """
    used = []

    class FakeLlm:
        def __init__(self, model=None):
            self.model = model or "기본모델"

        def source_budget_chars(self):
            return 2000

        def fit(self, text, label=""):
            # 진짜 `StudioLlm` 이 가진 것이다. 가짜가 빠뜨리면 **테스트만 통과하고 운영에서
            # 터진다** — 2026-10-07 에 그랬다.
            return text

        def chat(self, prompt, system=None, **kw):
            used.append(self.model)
            return "한 마디."

    monkeypatch.setattr("app.studio.meeting.StudioLlm", FakeLlm)
    save(client, [
        {"name": "기획자", "model": "qwen3.5:4b"},
        {"name": "개발자", "model": "gemma4:latest"},
        {"name": "PM"},                               # 비우면 기본
    ])
    ids = [p.persona_id for p in personas_mod.enabled()]

    client.get("/api/meeting/stream", params={"topic": "고도화", "personas": ",".join(ids)})

    # 발언 3번 + 정리 1번. 정리는 **기본 모델**이 한다 — 한 참가자의 모델로 하면 그 사람
    # 말투로 정리된다.
    assert used[:3] == ["qwen3.5:4b", "gemma4:latest", "기본모델"]
    assert used[3] == "기본모델"


def test_the_turn_says_which_model_spoke(client, studio, isolated_data, monkeypatch):
    """모델을 섞으면 답의 성격이 달라진다. **어느 모델이 말했는지** 화면이 알아야 한다."""
    class FakeLlm:
        def __init__(self, model=None):
            self.model = model or "기본모델"

        def source_budget_chars(self):
            return 2000

        def fit(self, text, label=""):
            # 진짜 `StudioLlm` 이 가진 것이다. 가짜가 빠뜨리면 **테스트만 통과하고 운영에서
            # 터진다** — 2026-10-07 에 그랬다.
            return text

        def chat(self, prompt, system=None, **kw):
            return "한 마디."

    monkeypatch.setattr("app.studio.meeting.StudioLlm", FakeLlm)
    save(client, [{"name": "기획자", "model": "qwen3.5:4b"}])
    ids = [p.persona_id for p in personas_mod.enabled()]

    body = client.get("/api/meeting/stream",
                      params={"topic": "고도화", "personas": ",".join(ids)}).text

    assert "qwen3.5:4b" in body


def test_the_model_survives_a_save(client, studio, isolated_data):
    """저장하고 다시 읽어도 고른 모델이 남아 있어야 한다."""
    save(client, [{"name": "기획자", "model": "qwen3.5:4b"}])

    saved = client.get("/api/admin/personas", headers=AUTH).json()["personas"][0]
    assert saved["model"] == "qwen3.5:4b"


# ── 컨텍스트 창을 넘기지 않는가 ───────────────────────────────────────────


def test_a_long_turn_is_cut_on_the_server(client, studio, isolated_data, monkeypatch):
    """700자는 **프롬프트의 부탁**일 뿐이다. 작은 모델은 지키지 않는다.

    실제로 2,000자가 넘는 발언이 나왔다(2026-10-07). 발언이 길면 그만큼 다음 사람의
    프롬프트가 길어지고, 컨텍스트 창을 넘기면 **오류가 아니라 조용히 잘린다.**
    """
    from app.studio import meeting as meeting_mod

    class Chatty:
        model = "fake"

        def __init__(self, *a, **kw):
            pass

        def source_budget_chars(self):
            return 9968

        def fit(self, text, label=""):
            return text

        def chat(self, prompt, system=None, **kw):
            return "가" * 4000

    monkeypatch.setattr("app.studio.meeting.StudioLlm", Chatty)
    save(client, [{"name": "기획자"}])
    ids = [p.persona_id for p in personas_mod.enabled()]

    turns = [p for k, p in meeting_mod.run("주제", personas_mod.pick(ids), [], rounds=1)
             if k == "turn"]

    assert len(turns[0]["text"]) <= meeting_mod.MAX_TURN_CHARS + 20
    assert "줄였습니다" in turns[0]["text"], "잘랐으면 잘렸다고 적어야 합니다"


def test_old_turns_drop_out_when_the_history_gets_long(monkeypatch):
    """이력이 예산을 넘으면 **오래된 것부터** 뺀다.

    뒤에서부터 채우는 이유: 바로 앞사람의 말을 보는 것이 가장 중요하다. 앞쪽을 남기고 뒤를
    자르면 "앞사람 말을 되풀이하지 마세요" 가 지켜질 수 없다.
    """
    from app.studio.meeting import _history

    turns = [{"name": f"사람{i}", "text": "가" * 300} for i in range(10)]

    text = _history(turns, budget=700)

    assert "사람9" in text, "가장 최근 발언이 남아야 합니다"
    assert "사람0" not in text
    assert "줄였습니다" in text, "뺐으면 뺐다고 적어야 합니다"


def test_the_sources_and_history_split_the_budget(client, studio, isolated_data, monkeypatch):
    """발췌가 예산을 다 먹으면 이력이 통째로 사라진다. 몫을 미리 나눠 둔다."""
    from app.studio import meeting as meeting_mod

    seen = {}

    class Spy:
        model = "fake"

        def __init__(self, *a, **kw):
            pass

        def source_budget_chars(self):
            return 10000

        def fit(self, text, label=""):
            seen["prompt"] = text
            return text

        def chat(self, prompt, system=None, **kw):
            return "한 마디."

    monkeypatch.setattr("app.studio.meeting.StudioLlm", Spy)
    hits = [{"doc_id": f"d{i}", "title": f"문서{i}", "section_title": "절",
             "text": "나" * 3000, "similarity": 0.8} for i in range(8)]
    save(client, [{"name": "기획자"}])

    list(meeting_mod.run("주제", personas_mod.pick(
        [p.persona_id for p in personas_mod.enabled()]), hits, rounds=1))

    # 발췌 몫(45%)을 넘지 않아야 이력과 고정 문구가 들어갈 자리가 남는다.
    assert len(seen["prompt"]) < 10000, "프롬프트가 예산을 넘었습니다"
