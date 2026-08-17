# API Manager 도우미 (openapi-chat-serve)

KT OpenAPI Portal **API Manager** 사용법을 안내하는 사내 FAQ 챗봇입니다.

**답을 지어내지 않습니다.** 미리 만들어 사람이 검수해 둔 답변만 나가고, 없으면 관련 문서를
보여주거나 담당자에게 접수합니다.

```
[사전] 문서 ─[질문 모델]→ 질문 ─[답변 모델]→ 답변 ─[채점 모델]→ 점수 ─사람 검수→ qa_index.json
[실시간] 질문 ──임베딩 1회──> 가장 가까운 질문을 찾아 그 답변을 반환            20~40ms
```

운영에서는 **LLM을 부르지 않습니다.** 운영 서버(Azure AKS)에 GPU가 없어서 내린 설계이고,
이 저장소의 거의 모든 판단이 여기서 나옵니다 → [왜 이렇게 만들었나](docs/02-아키텍처.md)

임베딩도 **Ollama 없이 앱 안에서(ONNX Runtime) 돕니다.** 그래서 운영 컨테이너가 하나입니다.
사전 단계에서만 모델을 셋 쓰는데, 역할마다 잘하는 모델이 다르고 **답을 쓴 모델이 자기 답을
채점하면 점수가 후해지기** 때문입니다.

---

## 5분 만에 띄우기

```bash
cd forever-chat-serve
python -m venv .venv && .venv\Scripts\activate      # Python 3.11
pip install -r requirements.txt
copy .env.example .env                              # ADMIN_PASSWORD 를 바꾸세요
python scripts/fetch_onnx_model.py                  # 임베딩 모델 ONNX (약 565MB · MIT)

python scripts/seed_categories.py                   # 카테고리 48개 (1회용)
python scripts/seed_demo_qa.py --force              # 문서 색인 + 데모 QA 3건 ← 이게 있어야 답이 나옵니다

python -m uvicorn app.main:app --reload --port 18100
```

Windows는 **`실행.bat` 더블클릭**이 위를 대신합니다(모델도 없으면 받습니다). 종료는 `stop.bat`.

**Ollama 는 QA를 만들 때만 필요합니다**(`APP_MODE=studio`). 챗봇으로 답하고 검색하는 데는
필요 없습니다 — 임베딩이 앱 안에서 돌기 때문입니다.

| 화면 | 주소 |
| --- | --- |
| 챗봇 | http://localhost:18100/ |
| 관리자 | http://localhost:18100/admin |
| API 문서 | http://localhost:18100/docs |
| 준비 상태 | http://localhost:18100/health/ready |

막히면 → [시작하기 · 문제 해결](docs/01-시작하기.md#문제-해결)

---

## 문서 지도

### 처음 오셨다면 이 순서로

| # | 문서 | 무엇이 있나 |
| --- | --- | --- |
| 1 | [시작하기](docs/01-시작하기.md) | 설치 · 실행 · 첫 질문 확인 · 자주 막히는 곳 |
| 2 | [아키텍처](docs/02-아키텍처.md) | 왜 이 구조인가 · 질문 하나가 지나가는 경로 · 두 가지 모드 |
| 3 | [코드 지도](docs/03-코드-지도.md) | 파일별 역할 · 읽는 순서 · 새 기능을 어디에 붙일까 |

### 작업하면서 찾아볼 것

| 문서 | 언제 보나 |
| --- | --- |
| [API 레퍼런스](docs/04-API-레퍼런스.md) | 엔드포인트 전체 목록과 요청·응답 |
| [데이터 파일](docs/05-데이터-파일.md) | `data/` 각 파일이 무엇이고 배포할 때 무엇을 옮기나 |
| [설정](docs/06-설정.md) | `.env` 전 항목 · 재시작 없이 바뀌는 값은 무엇인가 |
| [테스트](docs/07-테스트.md) | 테스트 작성 규칙 · Ollama 없이 도는 이유 · 격리 장치 |
| [QA 생성과 검수](docs/08-QA-생성과-검수.md) | 답변을 만들고 승인해 서비스에 내보내기까지 |
| [화면](docs/09-화면.md) | 챗봇 · 관리자 · 검수 화면과 퍼블 산출물 이식 규칙 |
| [함정](docs/10-함정.md) | **고치기 전에 읽으세요.** 실제로 밟은 지뢰 모음 |
| [배포](docs/11-배포.md) | Docker 이미지 만들기 · 개발 서버 반입 절차 · 측정값 |

### 그 밖에

| 문서 | 내용 |
| --- | --- |
| [이어서작업할내용.md](이어서작업할내용.md) | 인수인계 문서. 설계 결정의 **근거와 이력** |
| [docs/퍼블요청/](docs/퍼블요청/) | 퍼블리싱 요청서 원본과 매핑 문서 |
| [참고/이전프로젝트/](참고/이전프로젝트/) | 1차 PoC(`openapi-chat`)에서 가져올 코드. **실행되지 않습니다** |

---

## 한눈에 보는 구조

```
app/
  api/          FastAPI 라우터  (공개 /api/* · 관리자 /api/admin/* · 스튜디오 /api/studio/*)
  core/         설정 · 인증 · 세션 · 로깅 · 카테고리 · 질문 이력 · 작업 이력 · 원자적 JSON 쓰기
  ingestion/    문서 청킹 → 임베딩(ONNX) → 문서 벡터 색인 · 폴더 업로드
  qa/           QA 저장소(store) + QA 벡터 색인(index)
  pipeline/     retrieve.py  질문 하나가 지나가는 전체 경로  ★ 여기부터 읽으세요
                analytics.py 비슷한 질문 묶기 (LLM 없이) · status.py 진행 현황 집계
  studio/       QA 생성 · 채점(judge) · 품질 평가   ← LLM을 부르는 유일한 곳 (studio 전용)
  static/       퍼블 산출물 이식본 (chat.* · admin.*)
data/
  qa_index.json     ★ 사용자에게 나가는 답변 전부. 가장 중요한 파일
  categories.json     질문 주제 (대분류 5 / 카테고리 48)
  raw_docs/*.md       원본 문서
  chroma/             ← 위 셋에서 파생. 지워도 재색인으로 복구
models/
  bge-m3-onnx/        임베딩 모델 565MB. 저장소에 없고 fetch_onnx_model.py 로 받습니다
```

자세히 → [코드 지도](docs/03-코드-지도.md) · [데이터 파일](docs/05-데이터-파일.md)

---

## 응답 세 가지

`POST /api/ask` 는 `result_type` 으로 셋 중 하나를 돌려줍니다. **판단은 서버가 하고 화면은
그대로 그립니다** — 화면이 유사도를 보고 다시 판단하면 관리자 설정과 실제 동작이 조용히
어긋납니다.

| result_type | 조건 | 화면 |
| --- | --- | --- |
| `answer` | QA 유사도 ≥ `QA_MATCH_THRESHOLD` (0.90) | 검수된 답변 + 출처 |
| `related_docs` | 답변은 없고 문서 유사도 ≥ `RELATED_DOCS_FLOOR` (0.55) | 관련 문서 카드 최대 3건 |
| `unresolved` | 둘 다 못 넘김 | 접수번호 안내 |

임계값은 **재보고 정하는 값**입니다. 2026-08-17 측정에서는 0.90이 지나치게 보수적이었습니다
— 0.85로 낮추면 답변율이 66% → 95%로 오르는데 오매칭은 그대로 0%였습니다(인수인계 9-2).

---

## 자주 쓰는 명령

```bash
python -m pytest -q                                   # 전체 테스트 (모델 없이 동작)
python -m pytest tests/test_retrieve.py -q            # 파일 하나

python scripts/fetch_onnx_model.py                    # 임베딩 모델 받기 (처음 한 번)
python scripts/seed_categories.py                     # 카테고리 심기
python scripts/seed_demo_qa.py --force                # 문서 색인 + 데모 QA

# QA 사전 생성 (studio 전용 — .env 에 APP_MODE=studio)
python scripts/generate_qa.py --max 3 --variants 12   # 소량으로 품질 먼저 확인
python scripts/generate_qa.py --apply                 # 초안을 pending 으로 반영

# 임베딩 모델 비교 (우리 문서로 직접 잽니다. 벤치마크 순위는 세 번 뒤집혔습니다)
python scripts/compare_embedders.py

# 재색인 (임베딩 모델을 바꿨거나 data/chroma 를 지웠을 때)
curl -u admin:비밀번호 -X POST "http://localhost:18100/api/admin/qa/reindex?include_docs=true"
```

---

## 작업 규칙

- **git 커밋은 개발 담당자가 직접 합니다.** 도구가 `git add` / `git commit` 을 실행하지 않습니다
- 코드 주석은 "무엇을"이 아니라 **"왜 이렇게 했는지"**를 남깁니다. 파일 상단 독스트링에 설계
  의도가 있으니 고치기 전에 먼저 읽으세요
- 테스트는 실제 `data/` 를 절대 건드리면 안 됩니다 → [테스트](docs/07-테스트.md)
- 새 화면을 만들 때는 컨트롤러·서비스도 새로 만듭니다 (기존 엔드포인트 재사용 ✕)
- 응답·문서 문체는 한국어 `~합니다`

## 남은 일

**개발 서버 반입**과 **실사용 검증**입니다 → [배포](docs/11-배포.md)

배포 이미지는 만들어 두었고 개발 PC 에서 빌드·기동·질의까지 확인했습니다(2026-08-17).

```powershell
docker build -t openapi-chat-serve:latest .
docker save openapi-chat-serve:latest -o chat-serve.tar     # 902MB — 반입은 이 파일 하나
```

컨테이너는 **하나**입니다. 임베딩이 앱 안에서(ONNX) 돌아 Ollama 가 운영에 필요 없습니다.
개발 서버가 CentOS 7(glibc 2.17)이라 `onnxruntime` 을 호스트에 직접 설치할 수 없고,
**도커가 선택이 아니라 필수**입니다.
