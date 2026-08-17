# chat 화면 매핑 문서

산출물: `chat.html` / `chat.css` / `chat.js`
기준: `01_사용자_챗봇화면_퍼블요청서` + `보완 요청서(버튼 3종)` + `09_챗봇_주제선택_보완요청서` + `10_답변_피드백_퍼블요청서`
클래스 접두어 `chat_`, 공용 pill/모달은 `qr_` 유지.

---

## 1. 요소 ↔ 데이터 매핑

| 요소 | ID / 클래스 | data 속성 | 비고 |
| --- | --- | --- | --- |
| 대화 블록 | `#chatBlock` `.chat_block` | — | 위젯 이식 단위. 이 안쪽만 옮기면 동작 |
| 메시지 목록 | `#chatList` / `#chatListInner` | — | 스크롤 컨테이너 / 메시지 append 대상 |
| 인트로 | `#chatIntro` | — | 첫 전송 시 `hideIntro()` 로 숨김 |
| 입력 영역 | `#chatCompose` | — | 대기 중 `.is_waiting` |
| 입력창 / 전송 | `#chatInput` / `#chatSend` | — | 대기 중 `disabled` |
| 주제 트리거 | `#chatCatTrigger` (`.is_active`) | `data-category-id`, `data-category-label` | 래퍼 `.chat_cat_trigger_wrap` 도 `.is_active` |
| ㄴ 해제 버튼 | `.chat_cat_clear` | `data-category-clear` | 중첩 `<button>` 회피 — `<span role="button" tabindex="0">` |
| **인트로 펼침** | `#chatIntroCats` (`.is_open`, `.is_empty`) | — | 인트로 **안에서** 아코디언으로 펼침 |
| ㄴ 여는 버튼 | `#chatCatMore` `.chat_cat_more` | — | `aria-expanded` + 캐럿 뒤집힘 |
| ㄴ 검색 | `#chatIntroCatSearch` | — | 아래 팝오버와 같은 `.chat_cat_search` |
| ㄴ 목록 | `#chatIntroCatList` | — | `role="listbox"`, `buildCatList()` 가 그림 |
| 주제 팝오버 | `#chatCatPopover` (`.is_open`, `.is_empty`) | `data-selected-category` | `role="dialog"`, `position:absolute` |
| ㄴ 검색 | `#chatCatSearch` | — | 열릴 때 자동 포커스 |
| ㄴ 대분류 | `.chat_cat_group_head` (부모 `.chat_cat_group.is_open`) | `data-group-id` | `aria-expanded` |
| ㄴ 항목 | `.chat_cat_item` | `data-category-id` | `role="option"` + `aria-selected` |
| 추천 질문 토글/목록/항목 | `#chatCatQBtn` / `#chatCatQuestions` / `.chat_q_item` | `data-question` | 없으면 토글 `hidden` |
| 인트로 칩 영역 / 칩 | `#chatCatQuick` / `.chat_cat_quick_chip` | `data-category-id` | 최대 6개, 선택만 |
| 전체 주제 보기 | `.chat_cat_more` | — | 팝오버 열기 |
| 새 대화 | `#chatReset` | — | 헤더 우측. 대화 없음/대기 중이면 `disabled` |
| ㄴ 확인 모달 | `#chatResetModal` / `#chatResetOk` | `[data-reset-cancel]` | **접수번호가 있을 때만** 뜹니다 |
| 답변 복사 | `.chat_msg_copy` | `data-copy` | 답변 말풍선 메타 줄 우측 |
| 맨 아래로 | `#chatToBottom` (`.is_shown`, `.is_new`) | — | 입력창 바로 위 우측 |
| 안내 라이브 영역 | `#chatLive` | — | `role="status" aria-live="polite"` — 복사 결과 안내 |
| 출처 문서 모달 | `#chatDocModal` (`.qr_modal_backdrop` / `.qr_modal`) | `data-bind=doc_title/doc_section/doc_excerpt/doc_ref` | 배경·✕·ESC 닫기 |

---

## 1-A. 인트로 주제 펼침 (요청서 09 · A안)

`전체 주제 보기` 를 누르면 **누른 자리 바로 아래**에서 아코디언으로 펼칩니다. 아래 입력창 위 팝오버(`#chatCatPopover`)로 열리던 것을 바꾼 것입니다 — 400px 떨어진 곳에 열려 아무 일도 안 일어난 것처럼 보였습니다.

위치 계산이 없습니다. 스크롤·창 크기 변경에 어긋나지 않습니다.

### 목록은 한 벌의 코드로 그립니다

`buildCatList($list, query)` 하나가 인트로 목록과 아래 팝오버 목록을 **모두** 그립니다(`buildPopover(query)` 는 이 함수를 부르는 얇은 껍데기입니다). 마크업·클래스·조작이 두 곳에서 같습니다 — 한쪽만 고쳐지는 사고가 나지 않습니다.

id만 다릅니다(문서 내 유일해야 하므로): `#chatCatList` ↔ `#chatIntroCatList`, `#chatCatSearch` ↔ `#chatIntroCatSearch`. **개발이 잡고 있는 이름(`#chatCatList` `#chatCatSearch` `#chatCatPopover` `#chatCatTrigger` `.chat_cat_item[data-category-id]` `.chat_cat_group[data-group-id]` `.chat_cat_quick_chip`)은 그대로입니다.**

### 상태 규칙

| 상황 | 동작 |
| --- | --- |
| `전체 주제 보기` 클릭 | 펼침 + 캐럿 뒤집힘 + `aria-expanded="true"` + 검색칸 포커스 |
| 다시 클릭 · 바깥 클릭 · `ESC` | 닫힘 (`ESC` 는 포커스를 버튼으로 되돌립니다) |
| 주제 선택 | 펼침을 닫고 **입력창에 포커스**. 아래 트리거도 함께 선택 상태(`setCategory()` 공용) |
| 첫 질문 전송 | `hideIntro()` 가 펼침을 먼저 닫습니다 |
| 아래 팝오버가 열려 있을 때 | 서로 닫습니다 — 한 번에 하나만 |

아래 `＃ 주제 선택` 팝오버는 **그대로**입니다. 대화가 시작되면 인트로가 사라지고 그때부터 아래 버튼만 씁니다.

### 처음 열면 첫 대분류가 펼쳐집니다

`buildCatList()` 는 **검색어가 없을 때 첫 대분류를 `.is_open` 으로** 그립니다(인트로·아래 팝오버 모두). 주제가 48개인데 대분류 5줄만 보이면 "목록이 비었다"로 읽힙니다.

대분류 줄(`.chat_cat_group_head`)은 기본 배경을 옅게 깔고 hover에서 teal 틴트로 바뀝니다 — 눌러도 되는 줄로 보이게 했습니다. `cursor:pointer` 는 그대로입니다.

검색어를 넣으면 전부 펼쳐지는 동작은 그대로 두었습니다.

### 키보드 (아래 팝오버와 동일)

검색칸에서 `↓` 로 목록 진입 → `↑↓` 이동 → `Enter` 선택 → `Esc` 닫고 버튼으로 복귀. 목록은 `role="listbox"`, 항목은 `role="option"` + `aria-selected`. 캐럿(`▾`/`▴`)만으로 상태를 알리지 않고 `aria-expanded` 를 함께 줍니다.

### 주제가 하나도 없을 때

`updateCatVisibility()` — `CATEGORY_GROUPS` 가 비면 `자주 찾는 주제` 소제목 · 칩 · `전체 주제 보기` · 아래 트리거를 함께 `hidden` 합니다. 인트로에는 제목과 안내문만 남아 어색하지 않습니다. **목업 바가 아니라 제품 코드에 있습니다.**

주제 목록·개수는 서버(`/api/categories`)에서 옵니다 — 대분류 5개 · 주제 48개는 더미일 뿐이고, `(12)` 같은 개수도 스크립트가 채웁니다. 이름이 길면 `.chat_cat_group_name` · `.chat_cat_item` 의 줄임표가 받습니다.

---

## 1-B. 답변 피드백 👍 / 👎 (요청서 10 A)

사용자는 **판정자가 아니라 신고자**입니다. 눌러도 답변은 그대로 나가고, 관리자 화면에 표시만 붙습니다.

`<template id="tpl_answer">` 의 `.chat_meta` 줄, `복사` 버튼 옆입니다. **`tpl_answer` 에만** 있습니다 — `tpl_related` · 접수번호 · 오류 · 로딩 말풍선에는 없습니다(검수된 답변에 대한 평가라서). `.chat_meta` 에 `flex-wrap:wrap` 을 줘서 좁아지면 줄바꿈만 됩니다.

| 요소 | 이름 |
| --- | --- |
| 묶음 | `.chat_fb` |
| 👍 / 👎 | `.chat_fb_up` · `.chat_fb_down` (`.chat_fb_btn[data-fb]`, `aria-pressed`, 선택 시 `.is_on`) |
| 이유 영역 | `.chat_fb_reasons` (열림 `.is_open`) |
| 이유 버튼 | `.chat_fb_reason[data-reason]` — `mismatch` · `wrong` · `thin` |
| 건너뛰기 | `.chat_fb_skip` |
| 완료 문구 | `.chat_fb_done` (`.is_shown`, 2초 뒤 사라짐) |

아이콘은 **이모지 그대로**입니다. 기본은 회색조(`filter:grayscale(1)`)이고 hover·선택에서 색이 돌아옵니다 — 자원을 늘리지 않았습니다. 라벨은 `aria-label`(`도움이 됐어요` / `도움이 안 됐어요`)로만 줍니다.

### 상태 규칙

| 상황 | 동작 |
| --- | --- |
| 👍 | 바로 `감사합니다`. **이유를 묻지 않습니다** |
| 👎 | `.chat_fb_reasons` 가 말풍선 **안에서 인라인으로** 펼쳐집니다 (모달 아님) |
| 이유 선택 | 접히고 `의견 감사합니다` |
| `건너뛰기` | 접기만 합니다 — **👎는 이미 기록돼 있습니다** |
| 같은 버튼 재클릭 | 취소 |
| 👍 ↔ 👎 | 서로 바꿀 수 있습니다 (마지막에 고른 것만 유효) |
| 저장 실패 | 조용히 **직전 상태로 되돌립니다**. 토스트도 띄우지 않습니다 — 피드백 때문에 답변 읽기가 방해받으면 안 됩니다 |

저장은 자동입니다. `저장` 버튼이 없습니다. **개발 교체 지점**: `sendFeedback(payload, ok, fail)` 안을 `POST /api/feedback` 으로 바꾸시면 됩니다(현재는 260ms 지연 더미).

### 넣지 않은 것

**집계를 보여주지 않습니다** — `이 답변이 도움이 됐다고 답한 분 12명` 같은 표시는 없습니다. 다른 사람의 판단이 보이면 따라 누르고, 그러면 신고 내용이 왜곡됩니다. `신고가 접수되었습니다` 같은 무거운 문구도 쓰지 않았습니다.

## 2. 템플릿

| 템플릿 | 상태 | 바인딩 |
| --- | --- | --- |
| `#tpl_user` | 사용자 질문 | `[data-bind=question]` · 주제 배지 `.chat_msg_cat` (미선택 시 **엘리먼트 제거**) |
| `#tpl_answer` | `answer` | `[data-bind=answer]` (마크다운 HTML 주입), `[data-bind=source_docs]`, `.chat_verified`, `.chat_meta` · 출처 없으면 `.chat_src` 제거 |
| `#tpl_related` | `related_docs` | `[data-bind=related_docs]`, `[data-ask-support]` |
| `#tpl_related_item` | 문서 카드 | `.chat_rel_title_txt` / `.chat_rel_section` / `.chat_rel_excerpt` (3줄 클램프) / `[data-doc-open]` |
| `#tpl_src` | 출처 배지 | `.chat_src_title`, `data-ref` — 없으면 `.is_plain` (링크 아닌 배지) |
| `#tpl_unresolved` | `unresolved` | `[data-bind=message]`, `[data-bind=ticket_id]` + `.chat_ticket_copy` |
| `#tpl_loading` | 로딩 | 점 3개 애니메이션(`.chat_dots`), 래퍼 `.chat_msg_loading` 으로 제거 |
| `#tpl_error` | 오류 | `[data-retry][data-question]` |

문서 카드/출처 배지의 `data-doc-id` 로 모달 내용을 조회합니다(현재는 `DOC_FIXTURES`).

## 3. 상태 목록

| result_type | 화면 |
| --- | --- |
| `answer` | 일반 봇 말풍선 + 출처 박스 + 검수/AI 메타 |
| `related_docs` | **점선 테두리 + ⓘ** 말풍선, 문서 카드 최대 3, 문의 버튼 |
| `unresolved` | 회색 말풍선 + 접수번호(복사) |
| `loading` | 점 3개, `#chatCompose.is_waiting` + 입력/전송/주제 `disabled` |
| `error` | 붉은 톤 말풍선 + `[다시 시도]`(원 질문 재전송) |

## 4. 데이터 상수

`chat.js` 상단:
- `CATEGORY_GROUPS` — 대분류 **5개** / 카테고리 **48개** (팝오버 스크롤 부하 확인용). 일부 카테고리에 `questions` 배열
- `QUICK_CATEGORY_IDS` — 인트로 칩 6개
- `DOC_FIXTURES`, `MOCK_ANSWER` — 목업용. 개발에서 삭제

## 5. 신규 토큰 (4개) 및 사유

`quickApiReg.css` `:root` 에 대응 값이 없어 추가했습니다. 기존 토큰이 있다면 그 값으로 교체만 하면 됩니다.

| 토큰 | 값 | 사유 |
| --- | --- | --- |
| `--chat-bg` | `#f7f7f8` | 대화 블록 밖 페이지 바닥. 위젯 이식 시 사용되지 않음 |
| `--chat-surface` | `#fff` | 블록 표면 |
| `--chat-soft` | `#f2f2f4` | 봇 말풍선 / 주제 배지 배경. `--qr-line`(#ddd)은 면으로 쓰면 너무 진함 |
| `--chat-line-soft` | `#ececee` | 말풍선 **내부** 카드 경계선. `--qr-line` 은 말풍선 안에서 과하게 강함 |

그 외 색은 모두 기존 토큰. 부분적으로 파생값 2개만 리터럴로 사용했습니다 — teal hover `#25848a`, teal 텍스트 `#1f6d72`(teal-bg 위 대비 확보용), 에러 말풍선 배경 `#fdf3f3`/`#f0d3d4`(danger 파생).

## 6. 확인용 목업 바

`[data-dev-only]` — 마크업(`chat.html` 상단 주석 블록), CSS(`chat.css` 맨 아래 블록), JS(`chat.js` 맨 아래 블록) 3곳이 각각 주석으로 분리돼 있어 그대로 삭제하면 됩니다.
버튼: answer / related_docs / unresolved / 로딩 / 오류 / 주제 미선택 / 주제 선택 / 팝오버 열기 / 검색 결과 없음 / 추천질문 펼침 / 대기중 토글 / 초기화

## 7. 입력창 더미 분기 (개발 교체 지점)

`submit()` 안의 `setTimeout` 블록:
- `오류테스트` 포함 → `error`
- `문서` 또는 `모르` 포함 → `related_docs`
- 그 외 → `answer`


---

## 8. 보완 버튼 3종

### A. 새 대화 `#chatReset`

목업 바에 있던 초기화 로직을 **제품 버튼으로 승격**했습니다(`doReset()`). 목업 바의 `초기화` 버튼은 이제 이 함수를 부르기만 합니다 — 이식 때 목업 바를 지워도 기능은 남습니다.

| 상태 | 조건 |
| --- | --- |
| `disabled` | 말풍선이 하나도 없을 때(인트로), 또는 답변 대기 중(`.is_waiting`) |
| 활성 | 그 외 |

동작: 말풍선 전부 제거 → `#chatIntro` 복귀 → 주제 해제 → 팝오버·추천 질문 닫기 → `#chatToBottom` 숨김.
상태 갱신은 `updateReset()` 하나로 모읍니다(메시지 추가·삭제·대기 전환 시 호출).

**확인 모달은 붙이지 않았습니다.** 단 하나의 예외 — 대화 안에 `.chat_ticket`(접수번호)이 있으면 `#chatResetModal` 을 띄웁니다.
문구 `접수번호가 포함된 대화입니다. 지우면 번호를 다시 볼 수 없습니다.` / 버튼 `[취소]` `[새 대화 시작]`.

### B. 답변 복사 `.chat_msg_copy`

- **`.chat_ticket_copy` 와 동작을 공유합니다** — 두 버튼 모두 `copyText()` + `flashCopy()` 를 씁니다(클릭 → `복사됨` → 1.5초 후 원래 라벨). 접수번호 복사 쪽도 이 헬퍼로 통일했습니다.
- 위치는 하단 메타 줄 우측(`margin-left:auto`). **`#tpl_answer` 에만** 있습니다 — 로딩·오류·관련 문서·인트로에는 없습니다.
- 복사 내용은 `bubbleText()` 가 **화면에 보이는 글자 그대로** 뽑습니다: 마크다운 기호 없음, 문단 사이 빈 줄, 목록은 `1. ` / `- ` 로 복원, **출처·검수 문구는 제외**.
- 실패해도 멈추지 않습니다 — `document.execCommand('copy')` 를 `try/catch` 로 감싸고 실패 시 `#chatLive` 에 `복사하지 못했습니다` 만 남깁니다(구버전 브라우저 대비, 비동기 Clipboard API 미사용).
- 접근성: `aria-label="답변 복사"`, 결과는 `#chatLive`(`aria-live="polite"`)로 안내.

### C. 맨 아래로 `#chatToBottom`

| 상태 | 클래스 | 조건 |
| --- | --- | --- |
| 숨김 | (없음) | 하단에서 `BOTTOM_GAP`(160px) 이내이거나 대화가 비었을 때 |
| 노출 | `.is_shown` | 160px 넘게 위로 올라갔을 때. 페이드 180ms |
| 새 답변 | `.is_new` | 위로 올려본 상태에서 답변이 도착했을 때 붉은 점. 맨 아래로 가면 해제 |

- 위치는 `.chat_compose` 기준 `position:absolute` — 입력창 바로 위 우측(`right:24px`)이라 주제 트리거·입력창을 가리지 않습니다.
- **자동 스크롤 규칙은 그대로입니다.** `afterAppend(isBotAnswer)` 가 말풍선을 붙이기 **직전의** 위치를 보고 판단합니다 — 하단에 있었으면 `scrollBottom()`, 위를 읽던 중이었으면 스크롤하지 않고 `.is_new` 만 붙입니다.
- 접근성: `aria-label="맨 아래로"`, 실제 `<button>` 이라 키보드 포커스·Enter 가능.

---

## 9. 자원 경로 규약

| 항목 | 적용 |
| --- | --- |
| jQuery | `/static/vendor/jquery-3.7.1.min.js` — CDN 참조 없음 |
| 폰트 | CDN `<link>` 제거. `font-family` 폴백(`Pretendard` → `NanumGothic` → `sans-serif`)만 사용 |
| CSS · JS | `/static/chat.css` · `/static/chat.js` (절대경로) |

`chat.html` 안의 `[data-dev-only]` `<script>` 3줄은 **로컬 미리보기 폴백**입니다(절대경로가 안 잡히는 파일 열기 환경에서만 상대경로로 다시 시도). 폐쇄망에서는 조용히 실패하며, 이식 시 `data-dev-only` 태그를 지우면 됩니다.
프로젝트의 `static/chat.css`·`static/chat.js` 는 미리보기용 사본입니다 — 이식에는 루트의 원본을 쓰시면 됩니다.

---

## 10. 목업 바 추가 버튼

`새 대화 활성` / `새 대화 비활성` / `접수번호 포함 대화`(→ `새 대화` 누르면 확인 모달) / `복사됨 표시` / `맨아래로 노출` / `맨아래로 새답변` / `맨아래로 숨김`.

`피드백 기본` / `👍 누름` / `👎 누름(이유)` / `이유 고른 뒤` / `저장 실패`(직전 상태로 되돌아가는지).

`인트로 펼침` / `인트로 닫힘` / `주제 0건`(버튼·소제목이 숨는 상태) / `인트로에서 주제 고름`(→ 아래 트리거가 선택 상태로 바뀌는 모습).

> 제품 기능은 목업 바 밖에 있습니다. 목업 바는 상태를 **만들어 보여주기만** 합니다.
> `updateCatVisibility()`(주제 0건 처리)도 제품 코드에 있고, 목업 바는 `CATEGORY_GROUPS` 를 비워 그 상태를 만들 뿐입니다.
