# openapi-chat 챗봇 화면 — 퍼블 산출물 / 데이터 매핑

## 파일

| 파일 | 내용 |
| --- | --- |
| `chat.html` | 전체 페이지 + 상태별 마크업 `<template>` |
| `chat.css` | `--qr-*` 토큰 재사용 스타일, 타이핑 keyframes |
| `chat.js` | jQuery 목업 동작 (더미 응답) — `askApi()` 만 실제 `POST /ask` 로 교체 |

## 위젯 이식 단위

`<section class="chat_block" id="chatBlock">` 하나가 대화 영역 + 입력창 전체입니다.
헤더(`.chat_head`)·모달·devbar와 완전히 분리되어 있고, 폭/높이는 부모 요소에 100% 의존하므로
`quickApiReg.html` 등에 그대로 옮겨 넣을 수 있습니다. CSS는 `.chat_head`·`.chat_devbar`
블록만 제외하면 됩니다.

## 클래스 접두어

새 클래스는 모두 `chat_` 접두어. 버튼(`.qr_pill*`)과 모달(`.qr_modal*`)은 기존 클래스 그대로.
신규 색상 토큰은 3개(`--chat-bot-bg`, `--chat-page-bg`, `--chat-max`)만 추가했습니다.

## 상태별 템플릿 ↔ API 응답 매핑

| 템플릿 | 조건 | 요소 → 필드 |
| --- | --- | --- |
| `#tpl_user` | 사용자 입력 | `.chat_bubble[data-bind=question]` → 입력 텍스트 |
| `#tpl_bot` | `answered_by` = `cache` / `intent` / `rag` | `.chat_bubble[data-bind=answer]` → `answer`<br>`.chat_sources[data-bind=source_docs]` → `source_docs[]`<br>루트 `data-answered-by` → `answered_by`<br>루트 `data-confidence` → `confidence` (숫자 노출 X, 속성으로만)<br>`.chat_meta` → 고정 문구 "AI가 생성한 답변입니다" |
| `#tpl_src` | `source_docs[]` 반복 | `.chat_src_title` → `title`, `href`/`data-ref` → `url_or_ref`<br>`url_or_ref` 없으면 `<a>` 대신 `<span class="chat_src chat_src_plain">` |
| `#tpl_fallback` | `answered_by` = `fallback` | `.chat_fb_msg[data-bind=message]` → `message`<br>`.chat_ticket[data-bind=ticket_id]` → `ticket_id` |
| `#tpl_typing` | 요청 전송 ~ 응답 수신 | 없음 (CSS 애니메이션 `@keyframes chat_blink`) |
| `#tpl_error` | HTTP 실패 / 타임아웃 | `.chat_err_desc[data-bind=error_message]` → 에러 메시지(선택)<br>`[data-retry][data-question]` → 재시도할 질문 문자열 |

## 대기 중 비활성

`#chatCompose` 에 `.is_waiting` 클래스를 붙이고 `#chatInput`, `#chatSend`, `#chatCatTrigger`(본버튼·해제), `#chatCatQBtn`, `.chat_q_item`, `.chat_cat_quick_chip` 에
`disabled` 를 설정합니다 (`setWaiting(true|false)`).

## 출처 문서 상세 모달

`#srcModal` (`.qr_modal_backdrop` + `.qr_modal`). 배지 클릭 시 `is_open` 클래스 토글,
배경 클릭·`[data-modal-close]`·ESC 로 닫힘. `url_or_ref` 가 없으면 "문서로 이동" 버튼은 숨김.

## 카테고리 선택 UI (2차 rev.2) — 검색 가능한 팝오버 방식

카테고리는 가변·다수(2단계: 대분류 → 카테고리)라는 전제로 설계했습니다. 상시 노출은 입력창 위
**트리거 1줄**뿐이고, 탐색은 팝오버 + 검색으로 처리합니다. 더미 데이터는 5개 대분류 / **48개 카테고리**
(`chat.js` 상단 `CATEGORY_GROUPS`)로, 개수가 늘어도 팝오버 크기는 고정(`max-height: 320px`)입니다.
대분류·카테고리·추천질문은 모두 이 배열을 순회해 렌더합니다. 인트로 칩 대상은 `QUICK_CATEGORY_IDS`
(최대 6개, 개발에서 주입).

| 요소 | ID / 클래스 | data 속성 |
| --- | --- | --- |
| 주제 선택 트리거 | `#chatCatTrigger` (선택 시 `.is_active`) | `data-category-id`, `data-category-label` |
| 트리거 라벨 | `.chat_cat_trigger_label` (ellipsis + `title`) | `data-bind="category_label"` |
| 트리거 내 해제 버튼 | `.chat_cat_clear` (선택 시에만 노출) | `data-category-clear` |
| 팝오버 | `#chatCatPopover` (열림 `.is_open`, 결과없음 `.is_empty`) | `data-selected-category` |
| 검색 입력 | `#chatCatSearch` | — |
| 대분류 헤더 | `.chat_cat_group_head` (펼침 `.is_open`) | `data-group-id` |
| 대분류 개수 뱃지 | `.chat_cat_group_count` | — |
| 카테고리 목록 | `.chat_cat_list` (`role="listbox"`, 펼침 `.is_open`) | — |
| 카테고리 항목 | `.chat_cat_item` (`role="option"`, 선택 `.is_selected`, 키보드 포커스 `.is_focus`) | `data-category-id`, `data-category-label`, `data-group-id` |
| 검색 결과 없음 | `.chat_cat_noresult` | — |
| 추천 질문 토글 | `#chatCatQBtn` (노출 `.is_visible`, 열림 `.is_open`) | `data-question-count` |
| 추천 질문 목록 | `#chatCatQuestions` (열림 `.is_open`) | — |
| 추천 질문 1건 | `.chat_q_item` (2줄 말줄임) | `data-question` |
| 인트로 빠른 선택 영역 | `#chatCatQuick` / 칩 컨테이너 `#chatCatQuickChips` | — |
| 인트로 칩 1개 | `.chat_cat_quick_chip` (선택 `.is_selected`) | `data-category-id`, `data-category-label` |
| 전체 주제 보기 | `.chat_cat_more` | — |
| 말풍선 카테고리 배지 | `.chat_msg_cat` (`#tpl_user` 내) | `data-bind="category_label"` |

템플릿: `#tpl_cat_group`, `#tpl_cat_item`, `#tpl_cat_quick_chip`, `#tpl_cat_question`.
`#tpl_cat_card` + `.chat_cat_card*` CSS는 **rev.1 산출물 보존**(관리자 화면 재활용용)으로 남겨뒀고,
현재 화면에서는 렌더하지 않습니다.

### 구조 참고 — 트리거

`#chatCatTrigger` 는 중첩 `<button>` 을 피하기 위해 **겉은 `div`**, 내부에 본버튼
(`.chat_cat_trigger_main`, `aria-expanded`/`aria-controls` 보유)과 해제버튼(`.chat_cat_clear`)을 둡니다.
해제 클릭은 `stopPropagation()` 으로 팝오버 열림과 분리됩니다.

### 동작

| 행동 | 결과 |
| --- | --- |
| 트리거 클릭 | `openPopover()` — 검색창 자동 포커스, 전체 접힘 후 선택된 대분류만 펼침 + 해당 항목으로 스크롤 |
| 트리거 `✕` | `clearCategory()` 만 (팝오버 열리지 않음), 추천 질문 버튼 숨김 |
| 검색어 입력 | `filterList()` — 부분일치(대소문자 무시) 필터 + 해당 대분류 자동 펼침 + `<mark>` 하이라이트, 0건이면 `.is_empty` |
| 대분류 헤더 클릭 | 그 그룹만 토글 (다른 그룹 상태 유지) |
| 항목 클릭 | `selectCategory(id)` → 팝오버 닫힘 → 트리거 반영 → 추천 질문 버튼 노출 |
| 인트로 칩 클릭 | 선택만 (전송 아님) |
| `전체 주제 보기` | 팝오버 열림 |
| `추천 질문 N ▾` | `#chatCatQuestions` 토글 (max-height 160px + 스크롤, 180ms) |
| 추천 질문 클릭 | 즉시 전송 + 목록 접힘 |
| 전송 후 | 카테고리 선택 **유지** |
| `대화 초기화` | 선택 해제 + 팝오버 닫힘 + `#chatIntro` 복원 |
| 답변 대기 중 | 트리거·해제·추천질문·인트로 칩 `disabled`, 팝오버 강제 닫힘 |
| 팝오버 열린 채 입력창 클릭/바깥 클릭/ESC | 팝오버 닫힘 |
| 키보드 | 검색창 `↓` 목록 진입, `↑`/`↓` 이동(`.is_focus` + 자동 스크롤), `Enter` 선택, `ESC` 닫기 |

`askApi(question, categoryId, done)` — 실제 연동 시 `POST /ask` 바디에
`category_id: categoryId || null` 을 함께 담으면 됩니다. 추천 질문이 없는 카테고리를 고르면
입력창 `placeholder` 가 `"<카테고리명>에 대해 궁금한 점을 입력하세요"` 로 바뀝니다.

### 스타일

신규 색상 토큰 추가 **없음**. 선택 강조는 틸 계열(`--qr-teal`, `--qr-teal-bg`)만, `--qr-accent`(빨강)는
전송 버튼 전용. 팝오버는 `position: absolute; bottom: calc(100% + 8px)` 로 떠 있어 입력창 높이나
대화 영역 레이아웃을 밀지 않습니다. 팝오버·추천질문 스크롤바는 `.chat_list` 와 같은 얇은 커스텀 스타일.

## 퍼블 확인용 devbar

`[data-dev-only="true"]` 요소(상단 회색 바)는 미선택·팝오버 열림·검색 결과 없음·선택됨·대기중 등의 상태를 즉시 렌더해 보기 위한 목업 도구입니다.
개발 이식 시 해당 마크업과 `chat.css` 의 `.chat_devbar` 블록, `chat.js` 하단 목업 핸들러를 삭제하세요.
