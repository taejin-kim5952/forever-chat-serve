"""챗봇 답변을 **흘려보내는** 길 — 화면이 글자가 차오르는 모습으로 그린다.

### 왜 한 번에 주지 않는가

검색만 하는 길은 0.6초라 통째로 줘도 된다. 그런데 `AI 답변` 을 켜면 모델이 답을 만드는 데
5~30초가 걸린다. 그동안 화면에 아무것도 없으면 **멈춘 것과 구분되지 않는다.** 글자가
차오르면 기다리는 시간이 같아도 "돌고 있다"가 보인다.

### 지금은 '진짜' 토큰 스트리밍이 아니다 ★

LLM 이 토큰을 내보내는 족족 흘려보내는 것이 이상적이지만, 지금 답변 생성은
`app/studio/ask.py` 가 **완성된 문장을 한 번에** 돌려준다. 그래서 이 모듈은 받은 답을
조각내어 보낸다 — 화면과의 계약(`thinking`·`answer`·`sources`·`done`)은 같고, 나중에
모델 쪽을 토큰 단위로 바꿀 때 **이 파일 안쪽만** 고치면 된다. 화면은 모른다.

바꾸기 전에 이 점은 알아 두어야 한다: **체감 속도는 아직 빨라지지 않는다.** 답이 다
만들어진 뒤에 흘러나오기 시작한다.

### 어느 프로젝트에서 찾는가

화면이 폴더(= 프로젝트)를 고르면 `?project=` 가 붙어 미들웨어가 컨텍스트를 세운다. 고르지
않은 '전체' 가 기본 상태이고, 그때는 `app/pipeline/scope.py` 가 **가장 가까운 것이 있는
프로젝트**를 골라 준다. 검색은 **스레드에서** 돌린다 — ContextVar 를 `await` 사이에 두고
세웠다 푸는 것을 피하고, 임베딩·파일 읽기가 이벤트 루프를 잡지 않게 한다.

### 왜 SSE 인가

한 방향으로만 흐르고(서버 → 화면), 끊기면 브라우저가 알아서 알려 주고, 프록시를 그냥
지나간다. WebSocket 은 양방향이 필요 없는 자리에 연결 관리를 하나 더 만든다.
"""

import asyncio
import json
import time
from typing import AsyncIterator

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from app.core.config import (current_project, get_settings, is_studio, project_was_requested,
                             reset_project, use_project)
from app.core.logging import get_logger, log_event
from app.core.runtime_config import load_runtime_config
from app.ingestion import doc_files
from app.models.schemas import AskRequest
from app.pipeline import scope
from app.pipeline.retrieve import get_retriever

logger = get_logger("api.chat_stream")

router = APIRouter(prefix="/api", tags=["chat"])

# 한 번에 내보내는 글자 수. 너무 잘면 이벤트가 수백 개가 되고, 너무 굵으면 뚝뚝 끊겨 보인다.
CHUNK_CHARS = 6
# 조각 사이 간격. 0 이면 한꺼번에 도착해 차오르는 모습이 안 보인다.
CHUNK_DELAY = 0.012


def _event(name: str, payload: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _flow(text: str, name: str) -> AsyncIterator[str]:
    """글자를 조각내어 흘려보낸다."""
    for at in range(0, len(text), CHUNK_CHARS):
        yield _event(name, {"text": text[at: at + CHUNK_CHARS]})
        await asyncio.sleep(CHUNK_DELAY)


@router.get("/models")
def list_models() -> list[dict]:
    """고를 수 있는 답변 모델. **운영에서는 빈 목록**이다 — LLM 이 없다.

    화면은 빈 목록을 'AI 답변을 쓸 수 없음'으로 읽고 스위치를 잠근다. 404 나 500 으로
    돌려주지 않는 이유는, 그것이 '고장'과 '원래 없음'을 구분하지 못하게 만들기 때문이다.
    """
    if not is_studio():
        return []

    from app.core.config import get_settings
    from app.studio.llm import installed_models

    default = (get_settings().ollama_answer_model or "").strip()
    try:
        names = installed_models()
    except Exception as exc:  # noqa: BLE001 - LLM 서버가 꺼져 있어도 화면은 떠야 한다
        log_event(logger, "model list unavailable", error=str(exc))
        return []

    if default and default not in names:
        names = [default, *names]
    return [{"name": n, "label": n, "default": n == default} for n in names]


@router.get("/chat/stream")
async def chat_stream(
    request: Request,
    question: str = Query(...),
    topic: str = Query(""),
    ai: bool = Query(False),
    reasoning: bool = Query(False),
    model: str = Query(""),
) -> StreamingResponse:
    """질문 하나를 받아 `thinking` · `answer` · `sources` · `done` 을 흘려보낸다.

    `ai=false` 는 **검수된 답변만** 내보내는 평소 경로다(`/api/ask` 와 같은 판단을 쓴다).
    `ai=true` 는 문서를 읽어 AI 가 정리한다 — studio 에서만 열린다.
    """
    started = time.perf_counter()

    async def stream() -> AsyncIterator[str]:
        try:
            async for chunk in _answer(request, question, topic, ai, reasoning, model, started):
                yield chunk
        except Exception as exc:  # noqa: BLE001 - 끊긴 연결·모델 오류로 화면이 멈추면 안 된다
            log_event(logger, "chat stream failed", error=str(exc))
            yield _event("error", {"message": "답변을 가져오지 못했습니다."})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        # 프록시가 버퍼링하면 글자가 끝에 몰려서 한 번에 도착한다 — 차오르는 모습이 사라진다.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _answer(request: Request, question: str, topic: str, ai: bool,
                  reasoning: bool, model: str, started: float) -> AsyncIterator[str]:
    question = question.strip()
    if not question:
        yield _event("error", {"message": "질문을 입력해 주세요."})
        return

    if not ai:
        async for chunk in _verified(request, question, topic, started):
            yield chunk
        return

    if not is_studio():
        yield _event("error", {"message": "운영에서는 검수된 답변만 나갑니다."})
        return

    # 화면이 꺼진 기능을 요청해도 서버가 막는다. 설정을 내려 둔 설치에서 주소만 고쳐
    # 켜지면, 관리자가 끈 이유(느림·불안정)가 조용히 무시된다.
    reasoning = reasoning and get_settings().ai_reasoning

    async for chunk in _composed(question, reasoning, model, started):
        yield chunk


def _sources(docs: list[tuple[str, str, str]]) -> list[dict]:
    """참고 자료 카드 하나하나. **지금 프로젝트 컨텍스트 안에서** 불러야 한다.

    원본 파일이 함께 올라와 있으면 그 종류와 크기를 실어 보낸다 — 화면이 아이콘을 고르고
    내려받기 버튼을 그리는 데 쓴다. 원본이 없으면 종류는 `md` 다. 근거는 언제나 `.md` 이고
    내려받는 것만 원본이라는 규칙이 여기서 한 번 드러난다(`app/ingestion/doc_files.py`).
    """
    project = current_project()
    out = []
    seen: set[str] = set()
    for doc_id, title, chunk_id in docs:
        # 같은 문서의 절이 여럿 걸리면 카드가 똑같은 모양으로 두 번 나온다. 카드는 문서를
        # 열고 원본을 내려주는 단위라 **문서 하나에 하나**다. 먼저 온 것(= 더 가까운 것)을 남긴다.
        if doc_id in seen:
            continue
        seen.add(doc_id)
        originals = doc_files.find_all(doc_id)
        primary = originals[0] if originals else None
        out.append({
            "doc_id": doc_id,
            "title": title,
            "chunk_id": chunk_id,
            "project": project,
            "file_kind": doc_files.kind_of(primary.suffix) if primary else "md",
            "file_name": primary.name if primary else f"{doc_id}.md",
            "file_bytes": primary.stat().st_size if primary else 0,
            # 묶인 원본 전부. 카드에는 대표 하나만 걸고, 나머지는 원문 모달에서 받는다.
            "files": [{"name": p.name, "kind": doc_files.kind_of(p.suffix),
                       "bytes": p.stat().st_size} for p in originals],
        })
    return out


def _lookup(question: str, topic: str, principal) -> tuple[object, list[dict], str]:
    """검수된 답변 경로를 **고른 프로젝트 안에서** 한 번에 끝낸다(스레드에서 호출).

    어느 프로젝트에서 답했는지도 함께 돌려준다 — 화면이 뒤이어 보내는 피드백·문의가
    **같은 팩에 쌓여야** 담당자가 번호로 찾을 수 있다.
    """
    with scope.chosen(question) as vector:
        response = get_retriever().ask(
            AskRequest(question=question, category_id=topic or None), principal, vector
        )
        if response.result_type in ("answer", "live_answer"):
            docs = [(d.doc_id, d.title, "") for d in response.source_docs]
        elif response.result_type == "related_docs":
            docs = [(d.doc_id, d.title, d.chunk_id) for d in response.related_docs]
        else:
            docs = []
        return response, _sources(docs), current_project()


async def _verified(request: Request, question: str, topic: str,
                    started: float) -> AsyncIterator[str]:
    """평소 경로 — 미리 검수해 둔 QA. **운영 파이프라인을 그대로 쓴다.**

    여기서 따로 검색하면 화면이 보는 답과 `/api/ask` 가 주는 답이 갈린다.
    """
    from app.api.ask import _principal

    # 자격은 요청에서 뽑아 넘긴다 — 스레드 안에서 Request 를 건드리지 않는다.
    response, sources, project = await asyncio.to_thread(_lookup, question, topic, _principal(request))

    if response.result_type in ("answer", "live_answer") and response.answer:
        async for chunk in _flow(response.answer, "answer"):
            yield chunk
        yield _event("sources", {"docs": sources})
    elif response.result_type == "related_docs":
        # 답은 없고 문서만 찾은 경우. 화면이 빈 답변을 그리지 않도록 **문구를 함께** 보낸다.
        async for chunk in _flow(
            "이 질문에 딱 맞는 답변이 아직 준비되지 않았습니다. 아래 자료를 확인해 주세요.", "answer"
        ):
            yield chunk
        yield _event("sources", {"docs": sources})
    else:
        async for chunk in _flow(
            response.message or "답변을 찾지 못해 담당자에게 전달했습니다.", "answer"
        ):
            yield chunk

    yield _event("done", {
        "mode": "verified",
        "project": project,
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "ticket_id": response.ticket_id or "",
        "log_id": response.log_id or "",
    })


def _candidates(question: str) -> tuple[str, list[dict], bool]:
    """AI 가 읽을 후보 청크를 고른다(스레드에서 호출). `(프로젝트 id, 후보, 전체검색인가)`.

    '전체 검색' 은 **요청이 프로젝트를 지목하지 않은 것**이다. 그때 사용자는 어느 자료에서
    답이 왔는지 모르므로, 답변이 그것을 한 번 밝혀야 한다. 범위를 세우기 **전에** 봐야
    한다 — `scope.chosen` 이 들어가면 그 안에서는 늘 프로젝트가 서 있다.
    """
    across = not project_was_requested()
    config = load_runtime_config()
    with scope.chosen(question) as vector:
        index = get_retriever().doc_index
        hits = (index.search_by_vector(vector, config.doc_top_k) if vector is not None
                else index.search(question, config.doc_top_k))
        related = [h for h in hits if h["similarity"] >= config.related_docs_floor]
        return current_project(), related[: get_settings().ai_answer_source_count], across


def _compose(project_id: str, question: str, candidates: list[dict],
             model: str, on_think=None, across: bool = False) -> tuple[str, str, list[dict]]:
    """모델을 불러 답을 만든다(스레드에서 호출). 프로젝트를 다시 세우는 것은 원본 파일을
    찾는 자리가 프로젝트마다 다르기 때문이다.

    :param on_think: 주면 모델의 **사고 과정**을 조각마다 넘긴다(`추론 과정 보기`).
    """
    from app.studio import ask as studio_ask

    token = use_project(project_id) if project_id else None
    try:
        answer, used_model, used = studio_ask.compose(question, candidates, model or None,
                                                      on_think=on_think, across=across)
        if not answer:
            used = candidates[: load_runtime_config().related_docs_count]
            answer = "자료에서 이 질문에 답할 근거를 찾지 못했습니다. 아래 자료를 확인해 주세요."
        docs = [(h["doc_id"], h["title"], h.get("chunk_id", "")) for h in used]
        return answer, used_model, _sources(docs)
    finally:
        if token is not None:
            reset_project(token)


async def _think_along(project_id: str, question: str, candidates: list[dict],
                       model: str, across: bool = False) -> AsyncIterator[tuple]:
    """모델을 돌리면서 **사고 과정을 그때그때** 내보낸다.

    모델 호출은 스레드에서 돌고(이벤트 루프를 수십 초 잡으면 안 된다), 생각 조각은 큐를
    거쳐 이쪽으로 건너온다. 다 끝나면 `("result", …)` 하나를 마지막으로 낸다.
    """
    loop = asyncio.get_running_loop()
    pipe: asyncio.Queue = asyncio.Queue()
    done = object()

    def on_think(text: str) -> None:
        loop.call_soon_threadsafe(pipe.put_nowait, text)

    async def run():
        try:
            return await asyncio.to_thread(_compose, project_id, question, candidates, model,
                                           on_think, across)
        finally:
            pipe.put_nowait(done)

    task = asyncio.create_task(run())
    while True:
        item = await pipe.get()
        if item is done:
            break
        yield ("thinking", item)
    yield ("result", await task)


async def _composed(question: str, reasoning: bool, model: str,
                    started: float) -> AsyncIterator[str]:
    """`AI 답변` — 문서를 읽어 그 자리에서 정리한다 (studio 전용).

    모델을 부르는 동안은 **아무것도 흘려보낼 것이 없다.** 그래서 추론을 켰을 때만 '무엇을
    하는 중인지' 한 줄을 먼저 보낸다 — 진짜 사고 과정이 아니라 **진행 상황**이다. 모델이
    사고 과정을 내보내게 하려면 `/no_think` 를 풀어야 하는데, 그러면 형식 이탈이 늘고
    출력 예산을 거기에 다 쓴다(인수인계 문서의 `qwen3:4b` 사례).
    """
    project_id, candidates, across = await asyncio.to_thread(_candidates, question)

    if not candidates:
        async for chunk in _flow("관련 있는 자료를 찾지 못했습니다. 자료를 먼저 등록해 주세요.", "answer"):
            yield chunk
        yield _event("done", {"mode": "ai", "project": project_id,
                              "elapsed_ms": int((time.perf_counter() - started) * 1000)})
        return

    if reasoning:
        # 모델이 생각을 시작하기 전까지 몇 초가 빈다. 그동안 **사실인 것 하나**를 먼저
        # 보여 준다 — 무엇을 근거로 삼을지는 이미 정해졌고, 사용자가 가장 궁금해하는 것이다.
        found = ", ".join(f"[{i}] {h['title']}" for i, h in enumerate(candidates[:3], 1))
        async for chunk in _flow(f"자료 {len(candidates)}건을 찾았습니다: {found}\n\n", "thinking"):
            yield chunk

        answer = used_model = None
        async for kind, payload in _think_along(project_id, question, candidates, model, across):
            if kind == "thinking":
                yield _event("thinking", {"text": payload})
            else:
                answer, used_model, sources = payload
    else:
        # 모델 호출은 수 초가 걸리고 그동안 이벤트 루프를 잡고 있으면 안 된다.
        answer, used_model, sources = await asyncio.to_thread(
            _compose, project_id, question, candidates, model, None, across
        )

    async for chunk in _flow(answer, "answer"):
        yield chunk
    yield _event("sources", {"docs": sources})
    yield _event("done", {
        "mode": "ai",
        "model": used_model,
        "project": project_id,
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
    })
