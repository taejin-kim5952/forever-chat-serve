"""AI 프로젝트 미팅 참가자 관리 — 관리자 화면.

### studio 전용

참가자는 **LLM 에게 줄 프롬프트**다. 운영에서는 회의를 열 수 없으므로 고칠 이유도 없고,
반입할 때마다 운영에서 고친 것이 덮여 사라진다.

### 통째로 저장한다

항목 하나씩 PUT/DELETE 를 두지 않고 목록 전체를 받는다. 순서가 의미를 가지기 때문이다
(발언 순서다). 하나씩 고치면 순서를 맞추는 요청이 따로 필요해지고, 그 둘이 어긋나면
화면에서 본 순서와 실제 발언 순서가 달라진다.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import require_admin
from app.core.config import is_studio
from app.core import personas as personas_mod
from app.core.logging import get_logger, log_event

logger = get_logger("api.admin_personas")

router = APIRouter(prefix="/api/admin/personas", tags=["admin-personas"],
                   dependencies=[Depends(require_admin)])


def _require_studio() -> None:
    if not is_studio():
        raise HTTPException(
            status_code=403,
            detail="운영에서는 참가자를 조회만 할 수 있습니다. 편집은 스튜디오에서 진행합니다.")


class PersonaIn(BaseModel):
    persona_id: str = ""
    name: str
    title: str = ""
    prompt: str = ""
    enabled: bool = True


class PersonaSaveRequest(BaseModel):
    personas: list[PersonaIn] = Field(default_factory=list)


class PersonaListResponse(BaseModel):
    personas: list[personas_mod.Persona] = Field(default_factory=list)
    max_in_meeting: int = personas_mod.MAX_IN_MEETING


@router.get("", response_model=PersonaListResponse)
def list_personas() -> PersonaListResponse:
    """꺼 둔 참가자까지 전부. 관리 화면은 끈 것도 보여야 다시 켤 수 있다."""
    return PersonaListResponse(personas=personas_mod.load().personas)


@router.put("", response_model=PersonaListResponse)
def save_personas(request: PersonaSaveRequest) -> PersonaListResponse:
    """목록을 통째로 바꾼다. **보낸 순서가 발언 순서**다."""
    _require_studio()

    seen: set[str] = set()
    items: list[personas_mod.Persona] = []
    for i, p in enumerate(request.personas):
        name = p.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="참가자 이름을 입력해 주세요.")
        # id 는 화면이 비워 보낼 수 있다(새로 더한 줄). 이름에서 만들되 **이미 있는 것은
        # 그대로 둔다** — id 가 바뀌면 그 참가자를 고른 회의 기록과 이어지지 않는다.
        pid = (p.persona_id or _slug(name) or f"p{i + 1}").strip()
        if pid in seen:
            raise HTTPException(status_code=400, detail=f"참가자 id 가 겹칩니다: {pid}")
        seen.add(pid)
        items.append(personas_mod.Persona(
            persona_id=pid, name=name, title=p.title.strip(),
            prompt=p.prompt.strip(), enabled=p.enabled, sort=i))

    personas_mod.save(personas_mod.PersonaStore(personas=items))
    log_event(logger, "personas updated", count=len(items))
    return PersonaListResponse(personas=personas_mod.load().personas)


def _slug(text: str) -> str:
    """한글 이름도 받으므로 **영문만 남기고, 남는 게 없으면 빈 문자열**을 돌려준다.

    빈 문자열이면 부르는 쪽이 `p1` 같은 번호를 붙인다. 한글을 그대로 id 로 쓰면 주소와
    쿼리에 들어갈 때 인코딩이 섞인다.
    """
    out = "".join(c if c.isascii() and (c.isalnum() or c in "-_") else "-" for c in text.lower())
    return "-".join(part for part in out.split("-") if part)[:40]
