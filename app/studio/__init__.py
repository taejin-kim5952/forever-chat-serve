"""스튜디오 전용 기능 — 사내 작업 PC(`APP_MODE=studio`)에서만 도는 코드.

운영(serve)에는 GPU가 없어 LLM을 올리지 않는다. 이 패키지의 모듈은 운영에서 import 되더라도
**호출되지 않아야** 하며, 라우터가 `_require_studio()` 로 먼저 막는다
(`app/api/studio_generate.py`).

여기서 만든 결과물은 전부 `pending` 으로 들어간다. 사람이 검수해 `approved` 로 바꾸기 전에는
벡터 인덱스에 올라가지 않는다(`app/qa/store.py` 의 `SERVING_STATUSES`).
"""
