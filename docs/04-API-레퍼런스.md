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

`PUT /settings` 는 **`related_docs_floor < qa_match_threshold` 를 서버가 강제합니다.**
역전되면 `related_docs` 구간이 사라져 전부 `unresolved` 로 떨어지기 때문입니다.

`PUT /categories` 는 `quick_category_ids` 도 함께 받습니다. 최대 6개이고 존재하지 않는
카테고리 ID면 422입니다.

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
| `/` | `app/static/chat.html` |
| `/admin` | `app/static/admin.html` — `<body data-mode>` 와 브랜드(`data-brand`)를 서버가 치환 |
| `/static/*` | 정적 리소스 |
| `/docs` | FastAPI 자동 API 문서 |

`admin.html` 이 없으면 안내 페이지를 대신 내려줍니다 — 페이지를 못 받으면 로그인할 화면도
못 받기 때문입니다.
