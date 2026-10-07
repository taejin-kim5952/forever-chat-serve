"""프로젝트 — 한 설치가 담는 여러 도메인 (API Link · API Manager · MCP …).

### 프로젝트는 팩이다

새 개념을 만들지 않았다. 이미 있던 **도메인 팩**(`packs/<id>/`)이 곧 프로젝트다.
`pack.json` 에 이름·설명이 있고, 문서·카테고리·QA 가 그 폴더 안에 모여 있다. 달라진 것은
"한 프로세스가 팩 하나"에서 "**한 프로세스가 팩 여럿**"으로 바뀐 것뿐이다.

    packs/api-manager/   pack.json · profile · categories.json · qa_index.json · raw_docs/
    var/api-manager/     chroma · 질문이력 · 로그          ← 돌면서 쌓이는 것

그래서 반입(폐쇄망에 폴더 복사)·형상관리·되돌리기가 전부 지금 방식 그대로다. 프로젝트를
지운다는 것은 폴더 하나를 들어내는 것이고, 다른 프로젝트는 아무 영향을 받지 않는다.

### 어떤 요청이 어느 프로젝트를 보는가

들어오는 자리에서 **한 번** 정하고(`app/api/project_context.py`), 읽는 자리(11개 파일)는
그대로 둔다. 전부 `get_settings()` 를 거치므로, 그 함수가 지금 프로젝트의 설정을 돌려주면
나머지 코드는 바뀐 줄도 모른다.

### 기존 단일 설치는 그대로 돈다

`PACK_DIR` 를 지정해 띄운 설치(지금 운영)는 프로젝트 목록이 **비어 있고**, 요청도 프로젝트를
고르지 않는다. 그러면 `get_settings()` 가 예전과 같은 값을 돌려준다 — 화면의 선택기도
프로젝트가 하나 이하면 나타나지 않는다.
"""

import json
import re
import shutil
from pathlib import Path

from pydantic import BaseModel, Field

from app.core.config import get_settings, settings_for
from app.core.jsonstore import read_json, write_json_atomic
from app.core.logging import get_logger, log_event

logger = get_logger("core.projects")

# 프로젝트 id 는 **폴더 이름이자 URL 조각**이다. 한글이나 공백을 허용하면 폐쇄망 복사와
# 프록시 경로에서 깨진다 — 문서 ID(한글 허용)와 다루는 쪽이 다르다.
_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")

MANIFEST = "pack.json"


class Project(BaseModel):
    """화면이 보는 프로젝트 한 건."""

    project_id: str
    name: str
    description: str = ""
    enabled: bool = True
    sort: int = 0
    # `knowledge` = 묻고 답하는 지식 자료 · `library` = 받아 쓰는 양식·템플릿(자료실).
    # 담는 것이 다를 뿐 올리고 내려주는 구조는 같아서, 저장소를 나누지 않고 표시만 둔다.
    role: str = "knowledge"
    # 화면이 "자료를 넣어야 한다"를 바로 알아채는 숫자. 목록을 그릴 때만 센다.
    doc_count: int = 0
    qa_count: int = 0


def _dump(payload: dict) -> str:
    """사람이 diff 로 보는 파일이다. 한글을 이스케이프하지 않고 들여쓴다."""
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _root() -> Path:
    return Path(get_settings().projects_dir)


def validate_id(project_id: str) -> str:
    text = (project_id or "").strip().lower()
    if not _ID.match(text):
        raise ValueError(
            "프로젝트 ID는 영문 소문자·숫자·`-`·`_` 만 쓸 수 있고 40자까지입니다 (예: api-link)."
        )
    return text


def exists(project_id: str) -> bool:
    try:
        return (_root() / validate_id(project_id) / MANIFEST).exists()
    except ValueError:
        return False


def _read(project_dir: Path) -> Project | None:
    """팩 하나를 프로젝트로 읽는다. 매니페스트가 깨져 있으면 **목록에서 빼지 않고** id 로 띄운다.

    조용히 사라지면 "내 프로젝트가 왜 안 보이지"로 한참 헤맨다. 이름이 비어 보이는 편이
    사라지는 것보다 낫다.
    """
    data = read_json(project_dir / MANIFEST)
    if data is None:
        return None
    # 이름은 두 곳에 있을 수 있다. `profile.json`(별도 파일)이 있으면 그쪽이 이긴다 —
    # 화면(탭 ⑧ 납품처 프로필)에서 고치면 거기에 저장되므로, 매니페스트만 보면 **화면에서
    # 바꾼 이름이 프로젝트 목록에 반영되지 않는다.**
    profile = (data.get("profile") or {}) if isinstance(data, dict) else {}
    saved = read_json(project_dir / "profile.json")
    if isinstance(saved, dict):
        profile = {**profile, **{k: v for k, v in saved.items() if v}}
    docs = project_dir / "raw_docs"
    qa = read_json(project_dir / "qa_index.json", default={}) or {}
    items = qa.get("items", qa if isinstance(qa, list) else [])
    return Project(
        project_id=project_dir.name,
        name=profile.get("service_name") or project_dir.name,
        description=profile.get("service_desc") or "",
        enabled=bool(data.get("enabled", True)) if isinstance(data, dict) else True,
        sort=int(data.get("sort", 0) or 0) if isinstance(data, dict) else 0,
        doc_count=len(list(docs.rglob("*.md"))) if docs.is_dir() else 0,
        qa_count=len(items),
        role=(data.get("role") or "knowledge") if isinstance(data, dict) else "knowledge",
    )


def list_projects(enabled_only: bool = False) -> list[Project]:
    root = _root()
    if not root.is_dir():
        return []
    found = [p for p in (_read(d) for d in sorted(root.iterdir()) if d.is_dir()) if p]
    if enabled_only:
        found = [p for p in found if p.enabled]
    return sorted(found, key=lambda p: (p.sort, p.project_id))


def get_project(project_id: str) -> Project | None:
    try:
        return _read(_root() / validate_id(project_id))
    except ValueError:
        return None


def default_project() -> str:
    """프로젝트를 고르지 않은 요청이 볼 곳. 없으면 빈 문자열(= 단일 팩 설치)."""
    live = list_projects(enabled_only=True)
    return live[0].project_id if live else ""


def create_project(project_id: str, name: str, description: str = "",
                   role: str = "knowledge") -> Project:
    """빈 프로젝트를 만든다. **뼈대뿐이다** — 문서와 카테고리는 사람이 채운다.

    `scripts/pack_new.py` 와 같은 모양을 만든다. 거기서 만든 팩을 화면이 못 읽거나 그 반대면
    "스크립트로 만든 건 되는데 화면으로 만든 건 안 된다"가 되므로 파일 구성을 맞춘다.
    """
    pid = validate_id(project_id)
    target = _root() / pid
    if (target / MANIFEST).exists():
        raise ValueError(f"이미 있는 프로젝트입니다: {pid}")

    label = (name or "").strip() or pid
    (target / "raw_docs").mkdir(parents=True, exist_ok=True)
    manifest = _manifest(pid, label, description)
    manifest["role"] = role if role in ("knowledge", "library") else "knowledge"
    write_json_atomic(target / MANIFEST, _dump(manifest))
    # 빈 카테고리 파일을 함께 만든다. 없으면 화면이 "카테고리 없음"과 "파일이 없음"을
    # 구분하지 못하고, 첫 저장에서 경로를 만들다 실패한다.
    write_json_atomic(target / "categories.json", _dump({"groups": [], "quick_category_ids": []}))
    # 운영 산출물 자리도 미리 만든다 — 비루트로 도는 컨테이너에서 나중에 만들려다 막힌다.
    Path(settings_for(pid).var_dir).mkdir(parents=True, exist_ok=True)

    log_event(logger, "project created", project_id=pid, name=label)
    created = _read(target)
    assert created is not None
    return created


def update_project(project_id: str, name: str | None = None, description: str | None = None,
                   enabled: bool | None = None, sort: int | None = None,
                   role: str | None = None) -> Project:
    pid = validate_id(project_id)
    path = _root() / pid / MANIFEST
    data = read_json(path)
    if data is None:
        raise ValueError(f"없는 프로젝트입니다: {pid}")

    profile = dict(data.get("profile") or {})
    if name is not None and name.strip():
        profile["service_name"] = name.strip()
    if description is not None:
        profile["service_desc"] = description.strip()
    data["profile"] = profile
    if enabled is not None:
        data["enabled"] = bool(enabled)
    if sort is not None:
        data["sort"] = int(sort)
    if role in ("knowledge", "library"):
        data["role"] = role

    write_json_atomic(path, _dump(data))
    log_event(logger, "project updated", project_id=pid)
    updated = _read(_root() / pid)
    assert updated is not None
    return updated


def delete_project(project_id: str) -> None:
    """프로젝트를 통째로 지운다. **문서·QA·질문 이력이 함께 사라진다.**

    되돌리기가 없다. 화면이 이름을 받아 적게 하고 서버가 한 번 더 확인한다
    (`app/api/admin_projects.py`).
    """
    pid = validate_id(project_id)
    pack_dir = _root() / pid
    if not (pack_dir / MANIFEST).exists():
        raise ValueError(f"없는 프로젝트입니다: {pid}")

    var_dir = Path(settings_for(pid).var_dir)
    shutil.rmtree(pack_dir, ignore_errors=True)
    shutil.rmtree(var_dir, ignore_errors=True)
    log_event(logger, "project deleted", project_id=pid)


def _manifest(project_id: str, name: str, description: str) -> dict:
    from app.core.pack import ENGINE_VERSION

    return {
        "pack_id": project_id,
        "pack_version": "0.1.0",
        "engine_min_version": ENGINE_VERSION,
        "enabled": True,
        "sort": 0,
        "profile": {
            "service_name": name,
            "service_desc": description,
            "domain_intro": description or name,
            "language": "ko",
        },
        "matching": {},
        "routes": {"related_docs": True, "unresolved_ticket": True},
    }
