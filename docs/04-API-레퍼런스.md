# 04. API 레퍼런스

전체 엔드포인트 목록입니다. 서버를 띄우면 **http://localhost:18100/docs** 에서 실제 스키마와
시험 호출도 할 수 있습니다(springdoc 아닌 FastAPI 자동 문서).

← [03. 코드 지도](03-코드-지도.md) · 다음 [05. 데이터 파일](05-데이터-파일.md)

---

## 인증 정리

| 그룹 | 인증 | 실패 시 |
| --- | --- | --- |
| `/api/*` (챗봇) | **없음** | — |
| `/health`, `/health/ready` | 없음 | — |
| `/api/admin/login`, `/logout`, `/session` | 없음 | — |
| `/api/admin/*` (나머지) | 세션 쿠키 **또는** Basic | 401 |
| `/api/studio/*` | 위 + `APP_MODE=studio` | 401 / **403** |

```bash
# 세션 방식 (화면)
curl -c cookie.txt -X POST http://localhost:18100/api/admin/login \
     -H "Content-Type: application/json" \
     -d '{"username":"admin","password":"비밀번호"}'

# Basic 방식 (스크립트·배포 절차)
curl -u admin:비밀번호 http://localhost:18100/api/admin/qa
```

**401에 `WWW-Authenticate` 를 붙이지 않습니다.** 붙이면 브라우저 기본 로그인 창이 화면 모달과
겹쳐 뜨고, 그 창으로 로그인하면 화면은 로그인 사실을 모릅니다.

로그인은 **5회 실패 시 30초 잠금**(IP 단위)이고 429로 응답합니다. `Retry-After` 헤더가 옵니다.

---

## 1. 챗봇 공개 API

### `POST /api/ask` — 질문하기

```json
{
  "question": "API 등록은 어떻게 하나요?",
  "lang": "ko",
  "user_id": null,
  "channel": "web",
  "category_id": null
}
```

| 필드 | 필수 | 설명 |
| --- | --- | --- |
| `question` | O | 빈 문자열이면 400 |
| `lang` | X | 기본 `ko` |
| `user_id` | X | 질문 이력에 남습니다 |
| `channel` | X | `web`=실사용, `auto`=내부 테스트. **통계를 나누려고 둔 값입니다** |
| `category_id` | X | 화면에서 고른 주제. 라벨은 서버가 id로 다시 찾습니다 |

응답:

```json
{
  "result_type": "answer",
  "answer": "…",
  "source_docs": [{"doc_id":"api-등록","title":"API 등록","section":"저장하기","url_or_ref":"/api/..."}],
  "related_docs": [],
  "message": null,
  "ticket_id": null,
  "similarity": 0.974,
  "matched_qa_id": "qa_xxx",
  "response_time_ms": 712,
  "log_id": "lg_xxx"
}
```

| `result_type` | 채워지는 필드 |
| --- | --- |
| `answer` | `answer`, `source_docs` |
| `related_docs` | `related_docs` (최대 `RELATED_DOCS_COUNT`, 기본 3) |
| `unresolved` | `message`, `ticket_id` |

`similarity` · `matched_qa_id` · `response_time_ms` · `log_id` 는 항상 옵니다.

### `POST /api/support` — 담당자 문의 접수

`related_docs` 말풍선의 "담당자에게 문의하기" 버튼이 부릅니다. 요청 형식은 `/api/ask` 와
같습니다.

**접수번호는 반드시 서버가 만듭니다.** 화면에서 만들면 사용자가 본 번호와 이력에 남은 번호가
달라져 담당자가 번호로 찾을 수 없습니다.

### `GET /api/categories` — 주제 목록

```json
{
  "groups": [
    {"group_id":"g1","group_name":"API 관리",
     "categories":[{"category_id":"c1","name":"API 등록","questions":["...","..."]}]}
  ],
  "quick_category_ids": ["c1","c2"]
}
```

미사용 카테고리는 빼고 정렬해서 줍니다. `quick_category_ids` 는 챗봇 첫 화면의
**자주 찾는 주제** 칩(최대 6개)입니다.

### `GET /api/docs/chunk/{chunk_id}` · `GET /api/docs/{doc_id}` — 문서 상세

출처 배지·관련 문서 카드를 눌렀을 때 여는 모달의 내용입니다.

```json
{"doc_id":"api-등록","title":"API 등록","section":"저장하기","text":"…","url_or_ref":"…"}
```

배지는 청크가 아니라 **문서 단위**라 `/api/docs/{doc_id}` 는 문서 첫 청크를 보여줍니다.
없으면 404.

---

## 1-1. 프로젝트 (한 설치가 여러 도메인을 담을 때)

한 서버가 'API Link' · 'API Manager' · 'MCP' 를 함께 서비스합니다. 프로젝트의 실체는
**팩 폴더 하나**(`packs/<id>/` + `var/<id>/`)이고, 문서·카테고리·QA·질문 이력이 전부
그 안에서 갈립니다.

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| GET | `/api/projects` | 챗봇 선택기용 — 사용 중인 것만 |
| GET | `/api/admin/projects` | 관리자 목록 — 중지한 것까지, 문서·QA 건수 포함 |
| POST | `/api/admin/projects` | 만들기 (**studio**) |
| PUT | `/api/admin/projects/{project_id}` | 이름·설명·사용 여부·순서 (**studio**) |
| DELETE | `/api/admin/projects/{project_id}?confirm=<id>` | 지우기 — **되돌릴 수 없음** (**studio**) |

### 어느 요청이 어느 프로젝트를 보는가

```
?project=mcp-manager    쿼리  (스크립트·테스트가 쓰는 길)
X-Project: mcp-manager  헤더  (화면이 쓰는 길)
```

`app/api/project_context.py` 가 들어오는 자리에서 **한 번** 정하고, 경로를 읽는 11개 파일은
그대로 둡니다 — 전부 `get_settings()` 를 거치므로 그 함수가 지금 프로젝트의 설정을 돌려주면
나머지 코드는 바뀐 줄도 모릅니다. 엔드포인트마다 인자를 넘기게 고치면 한 군데만 빠뜨려도
**다른 프로젝트의 파일을 조용히 읽습니다.**

없는 프로젝트를 주면 **400** 입니다. 조용히 기본 프로젝트로 떨어뜨리지 않습니다 — 오타 하나로
남의 문서를 지우거나 QA를 승인하는 일이 생깁니다. 아무것도 안 주면 목록의 첫 프로젝트를 보고,
프로젝트가 하나도 없으면(= `PACK_DIR` 로 띄운 단일 설치) 예전과 똑같이 동작합니다.

---

## 2. 상태 확인

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| GET | `/health` | `{"status":"ok"}` — 프로세스가 살아 있는지 |
| GET | `/health/ready` | **답할 준비가 됐는지** |

```json
{"mode":"serve","ollama":"ok","embed_model":"ok","qa_serving":3,"status":"ok"}
```

`embed_model` 이 `ok` 이고 `qa_serving > 0` 일 때만 `status: ok` 입니다. 아니면 `degraded` —
화면은 뜨는데 모든 질문이 `unresolved` 가 되는 상태입니다.

컨테이너 헬스체크와 로드밸런서가 부르므로 인증을 걸지 않습니다.

---

## 3. 관리자 · 인증

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| POST | `/api/admin/login` | `{username, password}` → `{username, expires_at}` + 쿠키 |
| POST | `/api/admin/logout` | 쿠키 삭제. **인증을 요구하지 않습니다** (만료된 상태에서 눌러도 지워져야 함) |
| GET | `/api/admin/session` | `{authenticated, username, mode}` — 인증 없이 부를 수 있습니다 |

`GET /session` 은 화면이 켜질 때 로그인 모달을 띄울지 정하는 데 씁니다. 로그인 전에도 `mode`
를 알아야 studio 전용 탭을 미리 정리할 수 있습니다.

쿠키는 `admin_session`, 기본 유효기간 480분, `httponly` + `samesite=lax` 입니다.

---

## 4. 관리자 · QA (탭 ④)

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| GET | `/api/admin/qa` | 목록 (필터·페이징) |
| GET | `/api/admin/qa/{qa_id}` | 1건 |
| POST | `/api/admin/qa` | 저장 (신규/수정) |
| POST | `/api/admin/qa/bulk` | 일괄 처리 |
| POST | `/api/admin/qa/reindex` | 재색인 |

**저장 요청**

```json
{
  "qa_id": null,
  "question": "API 등록은 어떻게 하나요?",
  "answer": "…",
  "variants": ["등록하는 방법 알려줘", "API 등록 절차"],
  "category_id": "c1",
  "source_doc_ids": ["api-등록"],
  "status": "pending",
  "note": "",
  "created_by": "human"
}
```

`qa_id` 가 없으면 신규입니다. `status` 는 `pending` · `approved` · `hold` · `disabled` 중
하나이고 **`approved` 만 벡터 인덱스에 올라갑니다.**

**일괄 처리**

```json
{"qa_ids":["qa_a","qa_b"], "action":"approve", "category_id":null}
```

`action`: `approve` · `hold` · `pending` · `disable` · `delete` · `set_category`
(마지막은 `category_id` 필요). 응답은 `{"changed":2,"reindexed":2}`.

**재색인**

```bash
curl -u admin:비밀번호 -X POST \
  "http://localhost:18100/api/admin/qa/reindex?include_docs=true"
```

`include_docs=true` 면 문서 인덱스까지 다시 만듭니다. 응답은
`{"items":..,"vectors":..,"docs":{...}}`.

임베딩 모델을 바꿨거나 `data/chroma/` 를 지웠을 때 씁니다.

---

## 5. 관리자 · 문서 (탭 ⑤, studio 전용)

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| GET | `/api/admin/docs` | 목록 — `doc_id`, `title`, `category`, `updated`, `chunk_count`, `linked_qa_count` |
| GET | `/api/admin/docs/{doc_id}` | 원문 마크다운 |
| POST | `/api/admin/docs` | 새 문서 |
| PUT | `/api/admin/docs/{doc_id}` | 수정 |
| DELETE | `/api/admin/docs/{doc_id}` | 삭제 |
| POST | `/api/admin/docs/bulk-delete` | 여러 건 삭제 — 목록에서 체크한 것 |

`bulk-delete` 는 `{"doc_ids": [...]}` 를 받고 **건마다 결과**(`deleted` / `failed` + 사유)를
돌려줍니다. 한 건이 실패해도 나머지는 지웁니다 — 열 건을 골랐는데 중간에서 멈추면 무엇이
지워졌는지 알 수 없기 때문입니다. `DELETE` 가 아니라 `POST` 인 이유는 목록을 본문에 실어야
하는데 `DELETE` 의 본문은 중간 프록시가 버리기도 해서입니다(QA 일괄 작업과 같은 모양).

serve 모드에서는 **403**입니다. 문서 편집은 스튜디오에서 하고 결과 파일을 배포한다는
전제입니다.

저장하면 해당 문서만 다시 청킹·색인합니다.

---

## 6. 관리자 · 질문 이력 (탭 ①)

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| GET | `/api/admin/questions` | 페이징 조회 (기간·result_type·채널 필터) |
| GET | `/api/admin/questions/export` | CSV 내보내기 |

원본은 `data/question_log.jsonl` 입니다.

---

## 7. 관리자 · 설정 (탭 ③⑧)

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| GET | `/api/admin/mode` | 현재 모드 |
| GET | `/api/admin/settings` | 임계값 등 런타임 설정 |
| PUT | `/api/admin/settings` | 저장 — **재시작 없이 반영** |
| POST | `/api/admin/settings/reset` | 기본값으로 |
| GET | `/api/admin/categories` | 카테고리 전체 (미사용 포함) |
| PUT | `/api/admin/categories` | 카테고리 저장 |
| POST | `/api/admin/categories/import/preview` | JSON 가져오기 — **계산만**, 저장하지 않음 |
| POST | `/api/admin/categories/import` | JSON 가져오기 — 반영 |

`PUT /settings` 는 **`related_docs_floor < qa_match_threshold` 를 서버가 강제합니다.**
역전되면 `related_docs` 구간이 사라져 전부 `unresolved` 로 떨어지기 때문입니다.

`PUT /categories` 는 `quick_category_ids` 도 함께 받습니다. 최대 6개이고 존재하지 않는
카테고리 ID면 422입니다.

`/categories/import` 은 파일 내용을 **텍스트 한 덩어리**(`content`)로 받습니다 — 화면의
파일 선택과 붙여넣기가 같은 칸으로 모이기 때문입니다. `mode` 는 `merge`(기본, 지우지
않음) 또는 `replace`(파일에 없는 것은 삭제)이고, 미리보기와 반영이 **같은 판단**
(`app/core/category_import.py` 의 `_plan`)을 씁니다 — 다르면 확인 절차가 의미를 잃습니다.
형식 오류는 400 이고 `detail` 에 **어디를 고쳐야 하는지**가 한국어로 들어갑니다.
규격은 관리자 화면의 `카테고리등록규격` 모달과 같은 내용이며, 예시가 실제로 통과하는지는
`test_admin_screen.py` 가 지킵니다.

---

## 7-0. 관리자 · 납품처 프로필

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| GET | `/api/admin/profile` | 조직명·서비스명·소개·도메인 소개·언어 |
| PUT | `/api/admin/profile` | 저장 (설정 → 납품처 하위 탭) |

파일이 없으면 기본값이 옵니다. 저장하면 화면은 **즉시** 반영되고, `/docs` 제목만 기동 시
한 번 정해지므로 재시작해야 바뀝니다 → [05. 데이터 파일](05-데이터-파일.md)

---

## 7-1. 관리자 · 진행 현황

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| GET | `/api/admin/pipeline/status` | 파이프라인 6칸 + 지금 할 일 + 흐름 요약 |

**한 번에 내려줍니다.** 칸마다 부르면 화면 하나에 요청이 여섯 번이고, 요청 사이에 QA가
승인되면 칸끼리 앞뒤가 안 맞는 화면이 나옵니다.

**막힌 곳은 서버가 정합니다.** `todo.kind`(`docs` `review` `apply` `generate` `quality`
`clear`) 와 각 칸의 `state`(`ok` `warn` `todo` `off`) 를 서버가 지정하고 화면은 그대로
그립니다 — 화면이 숫자를 보고 다시 판단하면 기준이 두 곳에 생깁니다
(`result_type` 과 같은 원칙, [02. 아키텍처](02-아키텍처.md)).

`todo` 는 **한 칸에만** 붙습니다. `warn` 은 여러 칸에 붙을 수 있습니다.
serve 모드에서 studio 전용 칸(초안·품질)은 `off` 입니다.

응답 예시 → [퍼블요청/05 부록](퍼블요청/05_관리자_진행현황_및_메뉴개편_퍼블요청서.md)

---

## 8. 관리자 · 질문 분석 (탭 ②)

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| GET | `/api/admin/analytics` | 최근 분석 결과 |
| GET | `/api/admin/analytics/progress` | 진행률 |
| POST | `/api/admin/analytics/run` | 분석 시작 |
| POST | `/api/admin/analytics/override` | 군집의 상태·주제를 사람이 지정 |

`override` 의 `kind`가 `status` 일 때 값은
`new` · `reviewed` · `generated` · `applied` · `excluded` 중 하나여야 합니다.

사람이 지정한 값은 따로 보관돼 **다시 분석해도 남습니다.**

**LLM을 쓰지 않습니다** — 답변할 때 저장해 둔 질문 임베딩을 재사용하므로 운영에서도
돌아갑니다.

---

## 8-1. 스튜디오 · AI 답변 (챗봇의 `AI 답변` 스위치, studio 전용)

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| POST | `/api/studio/ask` | 문서에서 찾아 AI가 정리 + 참고 자료 |

챗봇 화면의 스위치를 켜면 `POST /api/ask` 대신 이곳으로 갑니다.

```
스위치 끔 → /api/ask         검수된 QA 에서만 (운영과 같은 경로)
스위치 켬 → /api/studio/ask  문서 검색 → grounded_answer → 참고 자료와 함께
```

`{"question": "...", "category_id": null}` 를 받고 `result_type` 은 셋입니다.

| `result_type` | 언제 | 무엇이 들어 있나 |
| --- | --- | --- |
| `ai_answer` | 근거를 찾아 답을 만듦 | `answer` + `related_docs` + `model` |
| `related_docs` | 문서는 찾았지만 **답을 못 만듦** | `related_docs` 만 |
| `unresolved` | 문서가 임계값에 못 미침 | `message` |

**관리자 인증이 없습니다.** 챗봇 화면에는 로그인이 없기 때문이고, 대신 `APP_MODE=studio`
에서만 열립니다(운영은 403). studio 는 사내 작업 PC라는 전제가 그 안전장치입니다.

### 찾는 것은 임베딩, 고르는 것은 AI

```
질문 ─임베딩─→ 후보 8건 ──→ AI ─→ 실제로 쓴 발췌만 인용 ─→ 답변 + 그 발췌들
               (0.03초)        (질문과 관계없는 것은 뺀다)
```

후보 수는 `AI_ANSWER_SOURCE_COUNT`(기본 8)이고 **화면 카드 수(`related_docs_count`, 3)와
일부러 다릅니다.** 3건만 주면 4번째로 걸린 문서에 답이 있어도 AI 는 본 적이 없게 됩니다.
`related_docs` 에 나가는 것은 AI 가 `사용:` 줄로 밝힌 발췌뿐이고, 번호를 못 읽었으면 유사도
상위 3건으로 떨어집니다 — 후보 8건을 전부 카드로 내보내면 무관한 카드가 여덟 장 뜹니다.

2026-09-01 에 반대로도 해 봤습니다. 문서 목차(제목 171개)를 통째로 주고 AI 에게 읽을 절을
고르게 했더니 **3건 중 2건을 헛짚고 9.4초**가 걸렸습니다(임베딩은 0.03초). 제목만 보고 찍기
때문입니다. 문서 전체(api-manager 10만 자)는 컨텍스트 예산(5,668자)의 19배라 애초에 못 넣습니다.

지키는 것 셋 — ① QA 인덱스를 보지 않습니다(켜면 AI 정리, 끄면 검수된 답변. 섞으면 화면을
보는 사람이 어느 쪽인지 알 수 없습니다) ② 근거가 없으면 답하지 않습니다(생성 경로와 **같은**
근거 판정) ③ **질문 이력에 남기지 않습니다** — 검수자의 시험 질문이 '무엇을 자주 묻는가'를
오염시키면 안 됩니다. LLM 이 죽어 있어도 `related_docs` 로 떨어질 뿐 오류가 아닙니다.

---

## 9. 스튜디오 · QA 생성 (탭 ⑥, studio 전용)

수십 분이 걸리는 작업이라 시작·폴링·중지가 나뉘어 있습니다.

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| POST | `/api/studio/generate` | 시작 — **이미 실행 중이면 409** |
| POST | `/api/studio/generate/variants` | 변형 질문만 추가 생성 |
| GET | `/api/studio/generate/progress` | 진행률 |
| POST | `/api/studio/generate/stop` | 중지 — 그때까지 만든 초안은 남습니다 |
| GET | `/api/studio/generate/result` | 초안 목록 (아직 QA 인덱스에 없음) |
| POST | `/api/studio/generate/apply` | 선택 항목을 **`pending`** 으로 반영 |

- serve 모드에서는 전 구간 **403**
- 반영은 **언제나 `pending`** 입니다. 승인은 사람이 검수 화면에서 합니다
- 근거를 못 찾은 질문은 **답을 만들지 않고 버립니다**

---

## 10. 스튜디오 · 품질 평가 (탭 ⑦, studio 전용)

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| POST | `/api/studio/eval` | 평가 시작 |
| GET | `/api/studio/eval/progress` | 진행률 |
| POST | `/api/studio/eval/stop` | 중지 |
| GET | `/api/studio/eval/result` | 결과 |

재는 것: 적중률(Top-1/Top-3) · **오매칭률** · 미검색 + 임계값별 표(0.75~0.95).

→ [08. QA 생성과 검수](08-QA-생성과-검수.md#품질-평가)

---

## 11. 화면 라우트

| 경로 | 파일 |
| --- | --- |
| `/` | `app/static/drive.html` |
| `/admin` | `app/static/admin.html` — `<body data-mode>` 와 브랜드(`data-brand`)를 서버가 치환 |
| `/static/*` | 정적 리소스 |
| `/docs` | FastAPI 자동 API 문서 |

`admin.html` 이 없으면 안내 페이지를 대신 내려줍니다 — 페이지를 못 받으면 로그인할 화면도
못 받기 때문입니다.
