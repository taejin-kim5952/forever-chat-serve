"""AI 프로젝트 미팅 — 참가자 목록과 회의 진행.

### 왜 `chat_stream.py` 를 쓰지 않는가

새 화면에는 컨트롤러·서비스를 새로 만든다(CLAUDE.md). 챗봇 답변과 회의는 지금은 비슷해
보이지만, 한쪽을 고칠 때 다른 쪽이 조용히 따라 바뀌는 자리를 만들지 않는다.

### studio 전용

LLM 을 부르므로 운영에서는 403 이다. 참가자 **목록 조회**는 막지 않는다 — 운영에서도 화면이
메뉴를 그릴 수는 있어야 하고, 거기서 막히면 "왜 비어 있지"가 된다.
"""

import json
import time
from typing import AsyncIterator

import anyio
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.config import current_project, is_studio
from app.core.logging import get_logger, log_event
from app.core import personas as personas_mod

logger = get_logger("api.meeting")

router = APIRouter(prefix="/api/meeting", tags=["meeting"])


class PersonaOut(BaseModel):
    persona_id: str
    name: str
    title: str = ""


class PersonaListResponse(BaseModel):
    personas: list[PersonaOut] = Field(default_factory=list)
    # 화면이 "몇 명까지 고를 수 있나"를 서버에 물어본다. 숫자를 화면에 박아 두면 서버가
    # 상한을 바꿨을 때 고른 뒤에야 거절당한다.
    max_in_meeting: int = personas_mod.MAX_IN_MEETING
    # 운영에서는 회의를 열 수 없다. 화면이 먼저 알아야 버튼을 잠글 수 있다.
    available: bool = True


@router.get("/personas", response_model=PersonaListResponse)
def list_personas() -> PersonaListResponse:
    """고를 수 있는 참가자. **운영에서도 열린다**(목록만)."""
    return PersonaListResponse(
        personas=[PersonaOut(persona_id=p.persona_id, name=p.name, title=p.title)
                  for p in personas_mod.enabled()],
        available=is_studio(),
    )


def _event(name: str, payload: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _sources(topic: str, limit: int) -> list[dict]:
    """주제로 이 프로젝트의 자료를 한 번 찾는다. **참가자 전원이 같은 발췌를 본다.**

    사람의 회의에서 같은 자료를 펴 놓고 이야기하는 것과 같다. 참가자마다 따로 찾으면 서로
    다른 것을 보고 말해 대화가 엇갈린다.
    """
    from app.core.runtime_config import load_runtime_config
    from app.pipeline.retrieve import get_retriever

    config = load_runtime_config()
    retriever = get_retriever()
    _, hits = retriever.doc_index.search(topic, limit)
    return [h for h in hits if h["similarity"] >= config.related_docs_floor]


@router.get("/stream")
async def stream(
    topic: str = Query(..., min_length=2, max_length=300),
    personas: str = Query("", description="참가자 id 를 쉼표로"),
    rounds: int = Query(1, ge=1, le=3),
    model: str = Query(""),
) -> StreamingResponse:
    """회의를 열고 발언이 끝날 때마다 하나씩 흘려보낸다.

    참가자 넷이면 한 바퀴에 수십 초가 걸린다. 다 끝난 뒤에 한 번에 주면 화면은 그동안 멈춘
    것과 구분되지 않는다.
    """
    if not is_studio():
        raise HTTPException(
            status_code=403,
            detail="운영에서는 회의를 열 수 없습니다. 스튜디오에서 진행합니다.")

    chosen = personas_mod.pick([p for p in personas.split(",") if p.strip()])
    if not chosen:
        raise HTTPException(status_code=400, detail="참가자를 한 명 이상 골라 주세요.")

    project = current_project()
    started = time.perf_counter()

    async def events() -> AsyncIterator[str]:
        from app.studio import meeting as meeting_mod

        # 검색과 모델 호출은 **스레드에서** 돌린다 — 임베딩과 HTTP 가 이벤트 루프를 잡으면
        # 같은 서버의 다른 요청이 함께 멈춘다.
        hits = await anyio.to_thread.run_sync(_sources, topic, 8)
        yield _event("opened", {
            "project": project,
            "personas": [{"persona_id": p.persona_id, "name": p.name, "title": p.title}
                         for p in chosen],
            "sources": [{"doc_id": h["doc_id"], "title": h.get("title", h["doc_id"])}
                        for h in hits],
            "rounds": rounds,
        })

        # 제너레이터를 스레드에서 한 칸씩 당긴다. 통째로 돌리면 회의가 다 끝난 뒤에야
        # 첫 발언이 나간다 — 흘려보내는 뜻이 없어진다.
        turns = meeting_mod.run(topic, chosen, hits, rounds=rounds, model=model or None)

        def _next():
            return next(turns, None)

        while True:
            item = await anyio.to_thread.run_sync(_next)
            if item is None:
                break
            kind, payload = item
            yield _event(kind, payload)

        log_event(logger, "meeting finished", project=project, personas=len(chosen),
                  rounds=rounds, elapsed_ms=int((time.perf_counter() - started) * 1000))
        yield _event("done", {"elapsed_ms": int((time.perf_counter() - started) * 1000)})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
