"""질문 하나를 **어느 프로젝트에서 찾을지** 정한다.

### 왜 필요한가

한 서버가 'API Link' · 'API Manager' · 'MCP' 를 함께 담는다. 화면에서 폴더(= 프로젝트)를
고르면 그 안에서만 찾으면 되지만, **고르지 않은 '전체' 가 기본 상태**다. 그때 아무 프로젝트
하나를 집으면 답이 있는 프로젝트를 비켜 가고, 사용자는 "자료를 올렸는데 모른다"를 본다.

### 어떻게 고르는가 — 가장 가까운 것이 있는 쪽

    질문 ─임베딩(1회)─┬─→ 프로젝트 A: QA 0.93 · 문서 0.61 ─→ 0.93
                      ├─→ 프로젝트 B: QA 0.42 · 문서 0.72 ─→ 0.72   → A 를 고른다
                      └─→ 프로젝트 C: (빈 팩)             ─→ 없음

QA 유사도와 문서 유사도를 **섞어서 max** 를 쓴다. 둘은 같은 모델의 코사인이지만 재는 대상이
다르다 — QA 인덱스에는 짧은 질문이 들어 있어 맞으면 0.9 를 넘고, 문서 청크는 0.6~0.7 대다.
그래서 섞으면 **검수된 답이 실제로 있는 프로젝트가 자연히 이긴다.** 그것이 우리가 원하는
순서다(답이 있으면 그 답, 없으면 자료 카드).

### 왜 결과를 합치지 않고 프로젝트 하나를 고르는가

합치려면 답변 선택·질문 이력·접수번호 생성이 모두 프로젝트를 가로질러야 한다. 이력과
접수번호는 **그 프로젝트의 파일에 남아야** 담당자가 찾을 수 있다(`var/<id>/`). 한 프로젝트를
고르고 나면 그 뒤는 지금 경로가 그대로 돈다 — 고치는 자리가 이 파일 하나로 끝난다.

임베딩은 **전체에서 한 번만** 계산해 프로젝트마다 돌려 쓰고, 고른 프로젝트의 본 검색에도
그대로 넘긴다(`Retriever.ask(query_vector=...)`). 프로젝트가 세 개면 Chroma 질의가 여섯
번인데 각 수 ms 라 체감되지 않는다 — 비싼 것은 임베딩이고 그것은 한 번이다.
"""

import contextlib

from app.core import projects as projects_mod
from app.core.config import project_was_requested, reset_project, use_project
from app.core.logging import get_logger, log_event

logger = get_logger("pipeline.scope")


def pick(question: str) -> tuple[str, list[float] | None]:
    """`(고른 프로젝트 id, 질문 임베딩)`.

    프로젝트 id 가 빈 문자열이면 **지금 컨텍스트를 그대로 쓴다** — 화면이 이미 골랐거나,
    프로젝트를 쓰지 않는 단일 팩 설치다.
    """
    # 요청이 `?project=` 로 지목했으면 서버가 다시 고르지 않는다 — 고른 것과 답이 어긋난다.
    # 미들웨어가 기본값으로 채운 것은 지목이 아니다(`project_was_requested`).
    if project_was_requested():
        return "", None

    found = projects_mod.list_projects(enabled_only=True)
    if not found:
        return "", None

    from app.pipeline.retrieve import get_retriever

    vector: list[float] | None = None
    best_id, best_score = "", -1.0
    for project in found:
        token = use_project(project.project_id)
        try:
            retriever = get_retriever()
            if vector is None:
                vector, qa_hits = retriever.qa_index.search(question, 1)
            else:
                qa_hits = retriever.qa_index.search_by_vector(vector, 1)
            doc_hits = retriever.doc_index.search_by_vector(vector, 1)
        except Exception as exc:  # noqa: BLE001 - 팩 하나가 깨져도 나머지는 답해야 한다
            log_event(logger, "project probe failed", project=project.project_id, error=str(exc))
            continue
        finally:
            reset_project(token)

        score = max(
            [h["similarity"] for h in qa_hits] + [h["similarity"] for h in doc_hits],
            default=-1.0,
        )
        if score > best_score:
            best_id, best_score = project.project_id, score

    # 어느 쪽에도 걸리는 것이 없으면(전부 빈 팩) 첫 프로젝트에서 평소 경로를 타게 한다.
    # 여기서 포기하면 '답을 못 찾았습니다' 가 아니라 아무 일도 일어나지 않는다.
    return (best_id or found[0].project_id), vector


@contextlib.contextmanager
def chosen(question: str):
    """고른 프로젝트를 컨텍스트에 세우고 질문 임베딩을 넘긴다.

    **동기 함수다.** `await` 를 사이에 두고 ContextVar 를 세웠다 풀면 재개되는 컨텍스트가
    달라질 수 있다. 호출부는 이 블록 전체를 `asyncio.to_thread` 안에서 돌린다 — 스레드는
    컨텍스트 사본을 받으므로 세운 값이 바깥으로 새지 않는다.
    """
    project_id, vector = pick(question)
    token = use_project(project_id) if project_id else None
    try:
        yield vector
    finally:
        if token is not None:
            reset_project(token)
