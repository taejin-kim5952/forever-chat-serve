"""도메인 팩 — 이 설치가 무엇을 아는가.

코드는 엔진이고 도메인은 데이터다. 문서·카테고리·검수 QA·화면 문구를 한 묶음으로 모아
`packs/<pack_id>/` 에 두고, 엔진은 `PACK_DIR` 만 바꿔 다른 도메인으로 뜬다.

### 매니페스트가 없어도 뜬다 ★

`pack.json` 이 없으면 **지금까지와 똑같이** 동작한다. 기존 설치는 `data/` 를 팩으로 쓰고
있고 그 안에 매니페스트가 없다 — 없다고 기동을 막으면 멀쩡한 설치가 죽는다.
없을 때는 코드 기본값과 `profile.json` 이 그대로 이긴다.

### 무엇을 검사하는가

값이 **틀린** 경우만 막는다. 없는 것은 막지 않는다.

  - `engine_min_version` 이 지금 엔진보다 높으면 → 기동 중단
  - 임계값이 역전됐으면 → 기동 중단 (related_docs 구간이 사라져 조용히 나빠진다)

잘못된 팩으로 조용히 서비스되는 것보다 안 뜨는 편이 낫다. 다만 **조용히 나빠지는 것**만
막고, 취향에 가까운 값은 통과시킨다 — 검사가 까다로우면 팩을 만들다 지친다.

### 값 우선순위

    runtime_config(운영 중 조정) > pack.json > 코드 기본값

관리자가 화면에서 내린 판단을 팩 배포가 되돌리면 안 된다. 그래서 `runtime_config` 가 맨
위에 있고, 이 파일은 그 아래 한 층을 채운다.
"""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.config import get_settings
from app.core.jsonstore import read_json
from app.core.logging import get_logger, log_event

logger = get_logger("core.pack")

# 이 엔진의 판. 팩이 이보다 높은 엔진을 요구하면 기동하지 않는다.
ENGINE_VERSION = "0.2.0"

MANIFEST_NAME = "pack.json"


def _as_tuple(version: str) -> tuple[int, ...]:
    """`0.2.0` → `(0, 2, 0)`. 숫자가 아닌 부분은 0으로 본다 — 판 비교에서 터지면
    팩 하나 때문에 서버가 안 뜬다."""
    parts = []
    for chunk in str(version).split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


class PackMatching(BaseModel):
    """팩이 제안하는 임계값. 운영 중 조정(`runtime_config`)이 있으면 그쪽이 이긴다."""

    qa_match_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    related_docs_floor: float | None = Field(default=None, ge=0.0, le=1.0)
    related_docs_count: int | None = Field(default=None, ge=1, le=10)

    @model_validator(mode="after")
    def _floor_below_match(self) -> "PackMatching":
        # runtime_config 와 같은 규칙이다. 팩이 어긴 채로 배포되면 그 도메인은
        # related_docs 없이 곧장 unresolved 로 떨어진다 — 예외가 나지 않아 알아채기 어렵다.
        if self.related_docs_floor is None or self.qa_match_threshold is None:
            return self
        if self.related_docs_floor >= self.qa_match_threshold:
            raise ValueError("관련 문서 하한은 답변 매칭 임계값보다 낮아야 합니다.")
        return self


class Pack(BaseModel):
    """`pack.json` 의 내용. 없으면 빈 값으로 만들어져 아무것도 덮지 않는다."""

    # JSON 키는 계획서 규격대로 `copy` 지만, 그 이름은 BaseModel.copy 를 가려
    # pydantic 이 경고한다. 필드명만 바꾸고 별칭으로 규격을 지킨다.
    model_config = ConfigDict(populate_by_name=True)

    pack_id: str = ""
    pack_version: str = ""
    engine_min_version: str = ""
    # 프로필은 `Profile` 이 검사한다. 여기서는 실어 나르기만 한다
    profile: dict = Field(default_factory=dict)
    matching: PackMatching = Field(default_factory=PackMatching)
    # 어느 경로를 켤지. 없는 키는 켜지 않은 것으로 본다
    routes: dict = Field(default_factory=dict)
    # 화면 문구
    copy_text: dict = Field(default_factory=dict, alias="copy")

    def exists(self) -> bool:
        """매니페스트를 실제로 읽었는가. 기본 팩(`data/`)은 False 다."""
        return bool(self.pack_id)

    def route_enabled(self, name: str) -> bool:
        return bool(self.routes.get(name))

    def text(self, key: str, fallback: str) -> str:
        value = self.copy_text.get(key)
        return value if isinstance(value, str) and value.strip() else fallback


class PackError(RuntimeError):
    """팩이 잘못돼 기동할 수 없다."""


def manifest_path() -> Path:
    return Path(get_settings().pack_dir) / MANIFEST_NAME


def load_pack() -> Pack:
    """매니페스트를 읽는다. 없으면 빈 팩 — 기존 설치는 이 경로로 온다.

    형식이 깨졌거나 엔진 판이 모자라면 :class:`PackError` 를 던진다. 호출부(기동)는
    이것을 잡지 않고 그대로 죽어야 한다.
    """
    path = manifest_path()
    raw = read_json(path)
    if raw is None:
        return Pack()
    if not isinstance(raw, dict):
        raise PackError(f"{path} 가 객체가 아닙니다.")

    try:
        pack = Pack.model_validate(raw)
    except ValueError as exc:
        raise PackError(f"{path} 를 읽을 수 없습니다: {exc}") from exc

    if pack.engine_min_version:
        if _as_tuple(pack.engine_min_version) > _as_tuple(ENGINE_VERSION):
            raise PackError(
                f"팩 '{pack.pack_id}' 는 엔진 {pack.engine_min_version} 이상을 요구합니다"
                f" (지금 {ENGINE_VERSION})."
            )

    log_event(
        logger, "pack loaded",
        pack_id=pack.pack_id, pack_version=pack.pack_version, path=str(path),
    )
    return pack
