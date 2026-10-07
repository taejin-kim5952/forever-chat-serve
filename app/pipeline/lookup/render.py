"""조회 결과를 문장으로 만든다 (개발계획서 §4.3 · §4.5).

**LLM 을 부르지 않는다.** 팩의 템플릿에 값을 끼워 넣을 뿐이다.

### 화이트리스트로 거른다 ★

템플릿이 쓸 수 있는 값을 **미리 정해 둔 것만** 통과시킨다. 사이트 응답을 통째로 넘기면
언젠가 토큰·키가 섞인 필드가 새로 생겨 답변에 그대로 실린다 — 그때는 아무도 모른다.
모르는 필드는 출력하지 않는 쪽이 기본값이어야 한다.

### 값이 모자라면 렌더하지 않는다

`{status_label}` 자리에 빈 문자열이 들어간 문장은 틀린 답이다. 차라리 라이브를 포기하고
문서 검색으로 내려가는 편이 낫다.
"""

from datetime import datetime

from app.core.logging import get_logger, log_event

logger = get_logger("pipeline.lookup.render")


class Whitelist:
    """템플릿에 넘길 값을 고른다.

    :param fields: `템플릿 이름 → 응답 키` 또는 `이름 → (키, 변환)`
    """

    def __init__(self, fields: dict) -> None:
        self.fields = fields

    def values(self, data: dict) -> dict[str, str]:
        out: dict[str, str] = {}
        for name, spec in self.fields.items():
            key, convert = (spec, None) if isinstance(spec, str) else spec
            raw = data.get(key)
            if raw is None:
                continue
            out[name] = convert(raw) if convert else str(raw)
        return out


def join(values: object, empty: str = "없음") -> str:
    """목록을 사람이 읽는 한 줄로. 답변에 `['a', 'b']` 가 그대로 나가지 않게 한다."""
    if not isinstance(values, (list, tuple)):
        return str(values)
    items = [str(v) for v in values if str(v).strip()]
    return " · ".join(items) if items else empty


def bullet(values: object, empty: str = "") -> str:
    """여러 줄로. 사유처럼 항목마다 줄을 나눠야 읽히는 것에 쓴다."""
    if not isinstance(values, (list, tuple)):
        return str(values)
    items = [f"- {v}" for v in values if str(v).strip()]
    return "\n".join(items) if items else empty


def render(template: str, values: dict[str, str], *, required: list[str] | None = None) -> str | None:
    """템플릿에 값을 끼운다. 필수 값이 없거나 모르는 이름이 있으면 None.

    조용히 빈 칸으로 채우지 않는 이유는, 빈 칸이 들어간 문장이 **틀린 답**이기 때문이다.
    """
    for name in required or []:
        if not values.get(name):
            log_event(logger, "live answer skipped — missing value", field=name)
            return None
    try:
        return template.format(**values).strip()
    except (KeyError, IndexError, ValueError) as exc:
        # 팩의 템플릿이 잘못된 것이다. 답변 하나 때문에 챗봇이 죽지는 않게 한다.
        log_event(logger, "live answer template error", error=str(exc))
        return None


def now_label(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M")
