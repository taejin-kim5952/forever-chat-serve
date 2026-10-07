"""관리자 — 프로젝트 만들기·고치기·지우기.

한 설치가 여러 도메인을 담는다('API Link' · 'API Manager' · 'MCP'). 그 단위가 프로젝트이고,
실체는 팩 폴더 하나다(`app/core/projects.py`).

### 이 경로만 프로젝트에 묶이지 않는다

다른 관리자 API는 전부 "지금 고른 프로젝트"의 자료를 다룬다(`app/api/project_context.py`).
여기는 프로젝트 자체를 다루므로 그 바깥에 있다 — 프로젝트가 **하나도 없는** 새 설치에서도
목록과 만들기가 되어야 한다.

### 만들기·지우기는 studio 전용

운영은 만들어진 팩을 **복사받는 쪽**이다(폐쇄망 반입). 운영에서 빈 프로젝트를 만들 수 있게
하면 "문서가 없는 프로젝트"가 사용자 화면의 선택지로 뜬다. 문서 편집을 studio 로 묶어 둔
것과 같은 이유다. 목록 조회는 양쪽 다 된다 — 운영에서도 무엇이 올라와 있는지는 봐야 한다.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core import projects
from app.core.auth import require_admin
from app.core.config import is_studio
from app.core.logging import get_logger

logger = get_logger("api.admin_projects")

router = APIRouter(prefix="/api/admin/projects", tags=["admin-projects"],
                   dependencies=[Depends(require_admin)])


class ProjectCreateRequest(BaseModel):
    project_id: str
    name: str = ""
    description: str = ""
    # `knowledge` = 묻고 답하는 지식 자료 · `library` = 받아 쓰는 양식(자료실).
    role: str = "knowledge"


class ProjectUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    enabled: bool | None = None
    sort: int | None = None
    role: str | None = None
    # 사용자 화면 입력칸의 '자주 하는 질문'. `None` 은 '건드리지 않음' 이고, 빈 목록은
    # '전부 지움' 이다 — 둘을 섞으면 지우는 방법이 없어진다.
    questions: list[str] | None = None


class ProjectListResponse(BaseModel):
    items: list[projects.Project] = Field(default_factory=list)
    # 프로젝트를 고르지 않은 요청이 보게 될 곳. 화면이 처음 띄울 프로젝트이기도 하다.
    default_project: str = ""


def _require_studio() -> None:
    if not is_studio():
        raise HTTPException(
            status_code=403,
            detail="운영에서는 프로젝트를 만들거나 지울 수 없습니다. 스튜디오에서 만든 폴더를 반입합니다.",
        )


@router.get("", response_model=ProjectListResponse)
def list_projects() -> ProjectListResponse:
    """관리자는 사용 중지한 것까지 본다 — 그래야 다시 켤 수 있다."""
    return ProjectListResponse(
        items=projects.list_projects(), default_project=projects.default_project()
    )


@router.post("", response_model=projects.Project, status_code=201)
def create_project(request: ProjectCreateRequest) -> projects.Project:
    _require_studio()
    try:
        return projects.create_project(request.project_id, request.name, request.description,
                                       role=request.role)
    except ValueError as exc:
        # 형식 오류·중복은 사람이 고칠 수 있다. 메시지를 그대로 화면에 보낸다.
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{project_id}", response_model=projects.Project)
def update_project(project_id: str, request: ProjectUpdateRequest) -> projects.Project:
    _require_studio()
    try:
        return projects.update_project(
            project_id, name=request.name, description=request.description,
            enabled=request.enabled, sort=request.sort,
            # `role` 은 요청 모델에만 있고 넘기지 않고 있었다 — 화면에서 용도를 바꿔도
            # 저장되지 않았고, 오류도 나지 않았다(2026-10-07).
            role=request.role, questions=request.questions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{project_id}")
def delete_project(
    project_id: str,
    confirm: str = Query("", description="지울 프로젝트 ID를 그대로 다시 적는다"),
) -> dict:
    """프로젝트를 통째로 지운다 — **문서·QA·질문 이력이 함께 사라지고 되돌릴 수 없다.**

    그래서 화면의 확인 창만 믿지 않고 **ID를 다시 받아 맞춰 본다.** 화면 없이 부르는 길
    (`curl`)이 있고, 되돌리기가 없는 작업은 경로가 하나뿐이어도 두 번 물어야 한다.
    """
    _require_studio()
    if confirm != project_id:
        raise HTTPException(
            status_code=400,
            detail="지우려면 프로젝트 ID를 confirm 에 그대로 적어 주세요.",
        )
    try:
        projects.delete_project(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"project_id": project_id, "status": "deleted"}
