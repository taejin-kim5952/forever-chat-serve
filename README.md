# API Manager 도우미 (openapi-chat-serve)

KT OpenAPI Portal "API Manager" 사용법을 안내하는 사내 챗봇.

## 이전 버전과 무엇이 다른가

이전(`openapi-chat`)은 질문이 올 때마다 LLM이 답변을 **생성**했다. 운영 서버에 GPU가 없어
답변 1건에 1~3분이 걸렸고, 운영에 올릴 수 없었다.

```
이전:  질문 → 문서 검색 → LLM이 그 자리에서 답변 생성           1~3분
지금:  [사전] 문서 → LLM이 답변을 만들고 사람이 검수 (스튜디오)
       [실시간] 질문 → 의미가 가장 가까운 질문을 찾아 그 답변을 반환   0.6~0.9초
```

운영에서는 **LLM을 부르지 않는다.** 남는 AI 모델은 임베딩(인코더) 하나뿐이고, 그건 CPU에서
1초 안에 끝난다. 실측: 위 표의 시간은 이 저장소에서 잰 값이다.

### 두 가지 모드

| 모드 | 설치 위치 | 하는 일 |
| --- | --- | --- |
| `serve` | 운영 서버 | 검색·응답 + 질문 이력/분석 + QA 조회. LLM 없음 |
| `studio` | 사내 작업용 PC | 위 전부 + QA 사전 생성·품질 평가·문서 편집 |

`APP_MODE` 로 정하고, 관리자 화면은 `<body data-mode>` 를 읽어 동작하지 않는 탭을 감춘다.

## 응답 세 가지

`POST /api/ask` 는 `result_type` 으로 셋 중 하나를 돌려준다.

| result_type | 조건 | 화면 |
| --- | --- | --- |
| `answer` | QA 유사도 ≥ `QA_MATCH_THRESHOLD`(0.90) | 검수된 답변 + 출처 |
| `related_docs` | 답변은 없고 문서 유사도 ≥ `RELATED_DOCS_FLOOR`(0.55) | 관련 문서 카드 최대 3 |
| `unresolved` | 둘 다 못 넘김 | 접수번호 안내 |

**답을 지어내지 않는다.** 미리 검수해 둔 답변만 나가고, 없으면 차선책(문서)이나 접수로 간다.

## 구조

```
app/
  api/          FastAPI 라우터 (챗봇 공개 API + /api/admin/* 인증 필요)
  core/         설정·인증·로깅·카테고리·질문 이력
  ingestion/    문서 청킹 → 임베딩 → 문서 벡터 색인
  qa/           QA 저장소(store) + 벡터 색인(index)
  pipeline/     retrieve.py — 질문 하나가 지나가는 전체 경로
  static/       퍼블 산출물을 이식한 화면
data/
  qa_index.json          ← 사용자에게 나가는 답변 전부. 이 파일이 원본이다
  categories.json        질문 주제
  raw_docs/*.md          원본 문서
  chroma/                벡터 저장소 (위 파일들에서 파생 — 언제든 재생성 가능)
  question_log.jsonl     질문 이력
```

`data/chroma/` 는 **파생물**이다. 지워도 `POST /api/admin/qa/reindex` 로 다시 만든다.
배포할 때 옮겨야 하는 것은 `qa_index.json` · `categories.json` · `raw_docs/` 셋이다.

## 실행

```bash
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # ADMIN_PASSWORD 를 반드시 바꿀 것

ollama pull bge-m3

python scripts/seed_categories.py     # 퍼블 더미 → 카테고리 48개
python scripts/seed_demo_qa.py        # 문서 색인 + 데모 QA 3건

python -m uvicorn app.main:app --reload --port 18100
```

- 챗봇 `http://localhost:18100/`
- 관리자 `http://localhost:18100/admin` (Basic 인증)
- 상태 `http://localhost:18100/health/ready`

## 테스트

```bash
python -m pytest -q
```

Ollama 없이 돈다 — 임베딩을 결정적인 가짜로 바꾼다(`tests/conftest.py`). 모든 테스트는
임시 디렉터리에서 돌아 `data/` 를 건드리지 않는다.

## 임베딩 모델을 바꿀 때

차원이 달라지므로(bge-m3 1024 ↔ embeddinggemma 768) 옛 벡터를 그대로 두면 검색이 조용히
망가진다. 컬렉션 메타데이터에 색인에 쓴 모델을 적어두고 다를 때 예외를 내지만, 바꾼 뒤에는
**반드시 재색인**해야 한다.

```bash
# .env 의 OLLAMA_EMBED_MODEL 을 바꾼 뒤
curl -u admin:비밀번호 -X POST "http://localhost:18100/api/admin/qa/reindex?include_docs=true"
```

모델별 태스크 접두어는 `app/ingestion/embedder.py` 에 표로 있다.

## 아직 없는 것

- QA 사전 생성 파이프라인(studio 탭 ⑥) — LLM으로 문서에서 QA 초안 생성
- 품질 평가(studio 탭 ⑦) — 검색 적중률 측정
- 질문 분석/군집(탭 ②)
- 관리자 화면 — 퍼블 요청서(`docs/퍼블요청/02_관리자화면_퍼블요청서.md`) 전달 완료, 산출물 대기

## 참고

- 퍼블 요청서: `docs/퍼블요청/`
- git 커밋은 개발 담당자가 직접 수행한다.
