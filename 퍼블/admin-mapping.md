# admin 화면 매핑 문서

산출물: `admin.html` / `admin.css` / `admin.js`
기준: `02_관리자화면_퍼블요청서.md` + `03_로그인모달_퍼블요청서` + `05_진행현황·메뉴개편_퍼블요청서` + `06_작업현황판·누락분_퍼블요청서` + `07_진행현황_도움말_퍼블요청서` + `10_답변_피드백_퍼블요청서`

> **요청서 02의 3번(별도 로그인 페이지)은 03으로 대체되었습니다.** `login.html` 은 만들지 않았습니다 — 로그인은 관리자 화면 위에 덮이는 모달 `#authModal` 하나입니다(§2).
클래스 접두어 `admin_`, 버튼·모달은 `qr_*` 재사용. 챗봇 산출물(`chat.*`)과 동일 토큰 세트.

---

## 1. 모드 (serve / studio) ★

- 서버가 `<body data-mode="serve">` 또는 `"studio"` 를 내려줍니다.
- `admin.js` 의 `applyMode(mode)` 가 **DOM 속성 + 배지 + 숨김 처리**를 모두 담당합니다.
- 헤더 배지: `#adminModeBadge` — `.is_serve`(운영, teal) / `.is_studio`(스튜디오, 보라)

### 모드별로 숨겨지는 요소

| 대상 | 마크업 | serve | studio |
| --- | --- | --- | --- |
| 탭 ⑥ QA 생성 · ⑦ 품질 평가 | `.admin_tab[data-studio-only]` | `hidden` | 표시 |
| 패널 전체 | `#panel_generate` `#panel_eval` | 탭이 숨겨져 진입 불가 | 표시 |
| QA 일괄 작업 메뉴 | `#qaBulkBtn` 래퍼 `[data-studio-only]` | `hidden` | 표시 |
| QA 목록 체크박스 열 | `#qaTable th.admin_col_check[data-studio-only]` + 행 `<td>` | 미출력 | 출력 |
| QA 검수 모달 편집 UI | `#qaSaveBtn` `#qaApproveBtn` `#qaDiscardBtn` `#qaVariantAdd` `#qaVariantGen` `#qaSourceAdd` | `hidden` + 전체 입력 `disabled` | 표시 |
| 변형 질문 자동 생성 | `#qaVariantGen` | `hidden` | 표시 |
| 문서 추가·수정·삭제 | `#docNewBtn` `#docSaveBtn` `#docDeleteBtn`, 행 작업 버튼 | `hidden` / `보기` 버튼으로 대체 | `수정` 버튼 |
| 분석 일괄작업 `QA 바로 생성` | `.admin_menu_item[data-act="gen"][data-studio-only]` | `hidden` | 표시 |
| 설정 · 생성 설정 카드 | `.admin_card[data-studio-only]` | `hidden` | 표시 |
| serve 안내 문구 | `[data-serve-only]` (QA·문서 탭 상단) | 표시 | `hidden` |

> 규칙: **`[data-studio-only]` = studio에서만 보임 / `[data-serve-only]` = serve에서만 보임.**
> 새 요소를 추가할 때 이 속성만 붙이면 됩니다. `applyMode` 가 일괄 처리합니다.
> serve 모드에서 studio 전용 탭이 열려 있으면 자동으로 `질문 이력` 탭으로 되돌립니다.

---

## 2. 로그인 모달 `#authModal` (요청서 03) ★

**02의 3번 별도 페이지를 대체합니다.** 세션이 만료돼도 편집 중이던 내용을 잃지 않도록, 이동이 아니라 현재 화면 위에 덮습니다.

### 일반 모달과 다른 점

| 항목 | 이 모달 |
| --- | --- |
| ESC | 닫히지 않습니다 — 전역 ESC 핸들러가 `#authModal` 을 먼저 걸러냅니다 |
| 배경 클릭 | 닫히지 않습니다 — 배경 클릭 핸들러에서 제외 |
| ✕ 닫기 버튼 | **없습니다** (`[data-modal-close]` 요소를 두지 않았습니다) |
| 겹침 | `z-index:400` — 열려 있던 QA 검수 모달(200) 위에 덮입니다 |
| 포커스 | 모달 안에서 순환합니다(Tab / Shift+Tab). 열 때의 포커스를 기억해 닫을 때 되돌립니다 |

### 두 상황, 한 모달

`#authModal[data-auth-reason]` 값만 바꿉니다. **안내 문구 한 줄만 달라지고, 만료 시 배경 내용은 지우지 않습니다.**

| 값 | 노출되는 문구 | 마크업 |
| --- | --- | --- |
| `initial` | 계정 정보를 입력해 주세요. | `.admin_auth_desc_initial` |
| `expired` | 잠시 사용이 없어 연결이 만료되었습니다. / 다시 로그인하시면 하던 작업을 이어서 하실 수 있습니다. | `.admin_auth_desc_expired` |

호출: `openAuth('initial' | 'expired')` / 인증 성공 시 `closeAuth()`. `expired` 로 들어와 성공하면 토스트 문구도 "이어서 작업하세요" 로 달라집니다.

### 상태 5가지 — `.admin_auth_form` 의 클래스

| 상태 | 클래스 | 화면 |
| --- | --- | --- |
| 기본 | (없음) | 제출 버튼이 흐림(`:not(.is_typing)`) |
| 입력 중 | `.is_typing` | 아이디·비밀번호가 **둘 다** 채워졌을 때만 부여 → 제출 버튼 활성 |
| 시도 중 | `.is_busy` | 입력·토글·버튼 `disabled`, `.qr_spinner` 표시, 버튼 문구 `확인 중…` |
| 실패 | `.is_error` | `#authMsg` 노출 + 입력 테두리 danger |
| 연속 실패 잠금 | `.is_locked` | `AUTH_MAX_TRY`(5)회 실패 시. `AUTH_LOCK_SEC`(30)초 카운트다운, 전부 `disabled`, 메시지는 중립 톤. 0초에 자동 해제 |

### 오류 문구 · 입력 보존

- 문구는 **항상 한 문장**입니다: `아이디 또는 비밀번호가 올바르지 않습니다.`
  아이디 존재 여부를 구분해 알려주지 않습니다(계정 열거 방지). 잠금 문구만 예외로 남은 시간을 표시합니다.
- 실패해도 **아이디는 남기고 비밀번호만 지웁니다.** 비밀번호 표시 토글도 `보기` 상태로 되돌립니다.
- `#authMsg` 는 `role="alert" aria-live="assertive"` — 스크린리더가 즉시 읽습니다.

### 접근성

| 항목 | 구현 |
| --- | --- |
| Caps Lock 안내 | `.is_caps` — `getModifierState('CapsLock')` 로 keydown/keyup 판정, blur 시 해제 |
| 비밀번호 표시 | `#authPwToggle` — `aria-pressed`, `aria-controls="authPw"`, 문구 `보기`↔`숨기기` |
| autocomplete | `#authId` = `username`, `#authPw` = `current-password` (브라우저·암호 관리자 정상 동작) |
| 그 외 | `autocapitalize="off"` `spellcheck="false"`, `role="dialog" aria-modal="true"`, `aria-labelledby`/`aria-describedby`, 열 때 빈 칸으로 자동 포커스, Enter 제출 |

### 저장 금지 ★

**아이디·비밀번호는 화면 어디에도 저장하지 않습니다** — `localStorage` · `sessionStorage` · 전역 변수 · `data-*` 속성 모두 사용하지 않았습니다. 입력값은 DOM 필드에만 있고, `closeAuth()` 가 두 칸을 모두 비웁니다. **인증 판단은 서버가 합니다** — `admin.js` `$authForm.on('submit')` 안의 `setTimeout` 블록이 개발 교체 지점이며, 목업은 `admin` / `admin` 입니다(브라우저 쪽 판정 로직은 이 블록에만 있습니다).

---

## 3. 공통 컴포넌트 · 상태

| 컴포넌트 | 클래스 / ID | 상태 클래스 |
| --- | --- | --- |
| 저장 상태 | `.admin_save_state[data-save-state="키"]` | `.is_busy` / `.is_ok` / `.is_err` (기본은 숨김) — `saveState(key, state, txt)` |
| 변경됨 | `.admin_dirty` | 부모 카드/모달에 `.is_dirty` 일 때만 노출 |
| 테이블 | `.admin_table_wrap` > `.admin_table` | 헤더 `sticky`, 행 `:hover`, 정렬 `.admin_th_sort.is_asc/.is_desc`, 흐린 행 `tr.is_muted`, 펼침 `tr.is_open` + `tr.admin_subrow` |
| 빈 상태 | `.admin_empty[data-empty="키"]` | `.is_shown` |
| 인라인 검색 | `.admin_search[data-search="키"]` | `.is_filled`(✕ 노출) / `.is_noresult` |
| 필터 칩 | `.admin_chip` | `.is_active` / `disabled` |
| 토글 | `.admin_switch` | `input:checked` / `input:disabled` |
| 필 태그 | `.admin_tag` + `.admin_tag_x` | `.is_warn`(미사용 경고) / `.is_drag` |
| 진행바 | `.admin_progress` | `.is_shown` / `.is_indeterminate` / `.is_err` — `progress($p, {pct, text, indeterminate, error})` |
| 확인 모달 | `#confirmModal` | `.admin_confirm_danger`(위험) — `askConfirm(msg, sub, danger, cb)` |
| 와이드 모달 | `.qr_modal_wide` (1000px) / `.qr_modal_sm` (400px) | `#qaModal` `#docModal` |
| 로딩 | `.admin_loading[data-loading]` + `.admin_skel` | `.is_shown` |
| 토스트 | `.admin_toast` / `#adminToasts` | `.is_ok` / `.is_err`, 3초 후 제거 — `toast(msg, kind)` |
| 드롭다운 | `.admin_menu_wrap` > `.admin_menu` | `.is_open`, 항목 `.admin_menu_item[disabled]` / `.is_danger` |
| 페이지네이션 | `.admin_pager[data-pager="키"]` | 자동 생성. `[data-page]` / `[data-page-size]` (20·50·100) |
| 카테고리 팝오버 | `.admin_cat_popover` (`#tpl_cat_popover` 로 생성) | `.is_open` / `.is_empty`, `[data-open-dir="up|down"]` |

### 카테고리 팝오버 공용화

`.admin_cat_pop_wrap[data-cat-picker="이름"]` 안에 `[data-cat-trigger]` 버튼만 두면 팝오버는 **템플릿에서 자동 생성**됩니다.
옵션은 `admin.js` 의 `CAT_PICKER_OPTS` 에서 이름별로 지정합니다.

| 이름 | 쓰이는 곳 | 특수 항목 | 여는 방향 | 다중 |
| --- | --- | --- | --- | --- |
| `hist` | ① 필터 | 전체 · 미분류 | down | — |
| `an` | ② 필터 | 전체 · 미분류 | down | — |
| `qa` | ④ 필터 | 전체 · 미분류 | down | — |
| `qaModal` | ④ 검수 모달 주제 | 없음 | down | — |
| `gen` | ⑥ 생성 대상 | 없음 | down | — |
| `quick` | ③ 자주 찾는 주제 추가 | 없음 | up | ✅ (선택 항목에 `.is_picked` ✓) |

챗봇의 `#chatCatPopover` 와 동일한 구조(검색 + 대분류 아코디언 + 스크롤 + 하이라이트)입니다.

### 결과 유형 색 (화면 전체 고정)

| 유형 | 클래스 | 색 |
| --- | --- | --- |
| `answer` | `.admin_rt.is_answer` | `--qr-teal` 계열 |
| `related_docs` | `.admin_rt.is_related` | `#e0a53c` / `--ad-warn-bg` |
| `unresolved` | `.admin_rt.is_unresolved` | `--qr-danger` 계열 |

차트 세그먼트(`.admin_stack_seg`, `.admin_legend_dot`)와 설정의 구간 바(`.admin_zone_seg`)도 **같은 색**을 씁니다.

### 상태 배지

- QA 4종: `.admin_st.is_wait` / `.is_done` / `.is_hold` / `.is_unused`
- 묶음 5종: `.is_new` / `.is_reviewed` / `.is_generated` / `.is_applied` / `.is_excluded`
- 평가 판정 3종: 적중 `.is_done` / 오매칭 `.is_wait` / 미검색 `.is_hold`

---

## 4. 사이드바 · 패널

가로 탭 → **좌측 사이드바** `.admin_nav` 로 바뀌었습니다. `data-tab` 키와 패널 id(`#panel_키`)는 **그대로**이고, 신규 두 개만 늘었습니다. 레이아웃은 `헤더` → `.admin_shell`(`.admin_nav` + `.admin_main`).

| 그룹 | 항목 | `data-tab` | serve | studio |
| --- | --- | --- | --- | --- |
| (단독) | 진행 현황 | `flow` | ✅ | ✅ |
| 콘텐츠 | RAG 문서 | `docs` | ✅ 읽기 | ✅ 편집 |
| 콘텐츠 | 질문 카테고리 | `categories` | ✅ | ✅ |
| 콘텐츠 | QA 생성 ✳ | `generate` | ❌ | ✅ |
| 콘텐츠 | 검수 | `review` | ✅ | ✅ |
| 콘텐츠 | QA 인덱스 | `qa` | ✅ 읽기 | ✅ 편집 |
| 운영 | 질문 이력 | `history` | ✅ | ✅ |
| 운영 | 질문 분석 | `analytics` | ✅ | ✅ |
| 품질·설정 | 품질 평가 ✳ | `eval` | ❌ | ✅ |
| 품질·설정 | 설정 | `settings` | ✅ 일부 | ✅ |

- **홈은 `flow`** 입니다. `selectTab()` 은 없는/숨겨진 키를 받으면 `flow` 로 되돌립니다. 현재 화면은 `location.hash` 에 기록됩니다.
- 그룹(`콘텐츠` `운영` `품질·설정`)은 `.admin_nav_group_label` — **클릭할 수 없는 소제목**입니다. 아코디언이 아니고, 접기 버튼도 없습니다.
- **그룹 자식이 전부 숨겨지면 그룹 라벨과 구분선까지 숨깁니다** — `syncNavGroups()` 가 `applyMode()` 안에서 `.admin_nav_group` 에 `hidden` 을 겁니다. 지금 구성에서는 비는 그룹이 없지만 항목이 늘면 자동으로 동작합니다.
- 상태: `:hover` / `.is_active`(배경 + 좌측 3px 세로 강조선 + 굵게, `aria-current="page"`) / `[data-studio-only]` 는 항목 끝 `✳`.

### 배지 `.admin_nav_badge`

`검수` 항목에만 답니다(`#navReviewBadge`). `renderNavBadge(n)`:

| 건수 | 표시 |
| --- | --- |
| 0 | `hidden` |
| 1~99 | 숫자 그대로 |
| 100+ | `99+` |

색은 주황(`--ad-warn-bg`) 한 가지. **다른 항목에는 배지를 달지 마세요.**

### 진행 현황 `#panel_flow` ★ (홈)

**여기서는 아무것도 편집하지 않습니다.** 상태를 보여주고 해당 화면으로 보내는 것이 전부입니다.

**6칸 상태판** `.admin_flow_steps` > `.admin_flow_step[data-step]` (`#tpl_flow_step` 으로 생성)

| # | 제목 | 큰 숫자 | 보조 줄 | 이동 |
| --- | --- | --- | --- | --- |
| ① | 문서 | `docs` | `미색인 N` / `모두 색인됨` | `docs` |
| ② | 초안 | `drafts` | `08-15 14:20 생성` / `생성 이력 없음` | `generate` ✳ |
| ③ | 검수 대기 | `pending` | `보류 N` / `4점 미만 N 포함` / `보류 없음` | `review` |
| ④ | 서비스 중 | `approved` | `최근 7일 +N` | `qa` |
| ⑤ | 품질 | `오매칭 N%` | `08-14 측정` / `측정 이력 없음` | `eval` ✳ |
| ⑥ | 임계값 | `0.90` | `문서 0.55` | `settings` |

**칸 상태 4가지**

| 상태 | 클래스 | 언제 | 모습 |
| --- | --- | --- | --- |
| 정상 | `.is_ok`(기본) | 할 일 없음 | 기본 |
| 주의 | `.is_warn` | 미색인 있음 · 오매칭률 5% 이상 | 경고 테두리 + `⚠` |
| 할 일 | `.is_todo` | **여기가 병목** | teal 배경 + `★` |
| 잠김 | `.is_off` | studio 전용인데 serve | 점선 + 흐림 + 버튼 `disabled` + `title="작업용 PC에서 가능합니다"` |

- **`.is_todo` 는 한 번에 한 칸에만** 붙습니다 — `flowTodo()` 가 가장 앞선 병목 하나만 고릅니다.
- serve에서 ②·⑤가 `.is_off` 입니다. **칸을 숨기지 않습니다** — 파이프라인 전체 모양이 보여야 하기 때문입니다.
- 데이터가 전부 0이어도 빈 상태로 갈아치우지 않고 `0` 을 그대로 보여줍니다.

**지금 할 일** `#flowTodo` — 한 문장 + 버튼 하나. `flowTodo()` 우선순위대로 6가지:

| 상황 | 문구 | 버튼 |
| --- | --- | --- |
| 문서 없음 | `문서가 없습니다. 먼저 문서를 넣어 주세요.` | RAG 문서 |
| 검수 대기 있음 | `검수 대기 N건. 승인해야 사용자에게 나갑니다.` | 검수 화면 열기 |
| 대기 없고 초안 있음 | `초안 N건이 반영을 기다립니다.` | QA 생성 |
| 오매칭률 높음 | `검색 오매칭이 N%입니다. …` | 품질 평가 |
| 초안도 없음(studio) | `문서에서 QA를 생성할 수 있습니다.` | QA 생성 |
| 할 일 없음 | `막힌 곳이 없습니다.` | `.is_clear` — 색을 빼고 **버튼을 숨깁니다** |

**흐름 요약** `#flowSummary` — 단계 사이에서 걸러져 나간 것. 값이 0인 조각은 빼고, **생성 이력이 없으면 블록 전체(`#flowSummaryCard`)를 숨깁니다.** `flex-wrap` 이라 좁아지면 두 줄로 접히고 가로 스크롤은 생기지 않습니다.

이동 버튼은 전부 `[data-goto-tab="키"]` — 문서 전역에서 이 속성 하나면 화면이 바뀝니다.

### 도움말 `.admin_help` ★ (요청서 07)

카드 우측 상단 `?` → 말풍선. **라이브러리를 쓰지 않았습니다**(폐쇄망) — 직접 그렸습니다. 6칸 **전부**에 답니다.

| 요소 | 이름 |
| --- | --- |
| 감싸는 자리 | `.admin_help_wrap` (`position:relative`) |
| 아이콘 버튼 | `.admin_help[data-help="키"]` — `<button>` · `aria-label="설명"` · `aria-expanded` |
| 말풍선 | `.admin_help_pop` (`role="tooltip"`, 열림 `.is_open`, 왼쪽 펼침 `.is_left`) |
| 본문 | `.admin_help_txt` |

`tpl_flow_step` 안에 넣었고, 번호(`.admin_flow_no`)와 `?` 는 `.admin_flow_top` 한 줄에서 양끝으로 갈라집니다 — 숫자·버튼 위치는 그대로이고 줄바꿈이 생기지 않습니다.

#### `data-help` 키 = 서버 `steps[].key`

문구는 **순서(①②③)가 아니라 키로** 찾습니다(`renderFlow()` 가 `s.key` 를 `data-help` 에 넣습니다). 카드 순서가 바뀌어도 문구가 따라갑니다.

| 카드 | `data-help` |
| --- | --- |
| ① 문서 | `documents` |
| ② 초안 | `drafts` |
| ③ 검수 대기 | `pending` |
| ④ 서비스 중 | `approved` |
| ⑤ 품질 | `quality` |
| ⑥ 임계값 | `threshold` |

**문구는 화면 상수입니다** — `admin.js` 상단 `HELP_TEXT = { documents:'…', … }` 한곳에 모았습니다. 서버를 부르지 않고, 납품처마다 달라지지 않습니다. 줄바꿈은 문구 안의 `<br>` 입니다. 개발이 확정한 문구라 임의로 다듬지 마세요 — 숫자의 의미가 달라집니다.

#### 열고 닫기

| 상황 | 동작 |
| --- | --- |
| `?` 클릭 | 열림 |
| 다시 클릭 | 닫힘 |
| 다른 `?` 클릭 | 앞의 것이 닫히고 새 것이 열림 — **한 번에 하나만** |
| 바깥 클릭 · `ESC` | 닫힘 |
| 마우스 호버 | **열지 않습니다** |

호버로 열면 카드의 `[문서 관리]` 버튼을 누르러 가는 길에 계속 열립니다. **클릭으로만** 엽니다 — CSS에 `:hover` 로 여는 규칙이 없습니다.

`ESC` 는 도움말이 열려 있을 때 `stopPropagation()` 으로 **모달 ESC 핸들러보다 먼저** 처리하고, **포커스를 `?` 로 돌려줍니다**(`closeHelp(true)`). `renderFlow()` 가 카드를 다시 그릴 때도 먼저 닫습니다.

#### 위치

- 기본은 `?` 아래, 꼬리가 `?` 를 가리킵니다.
- **오른쪽 끝 카드(⑤·⑥)** 는 `placeHelp()` 가 `getBoundingClientRect()` 로 `.admin_main` 오른쪽 경계를 넘는지 보고 `.is_left` 를 붙여 왼쪽으로 펼칩니다. 창 크기가 바뀌면 다시 계산합니다.
- `.admin_flow_step` 에 `overflow:visible` 을 명시했습니다 — **이 자리에는 `overflow:hidden` 을 걸지 마세요.** 말풍선이 카드 안에 갇힙니다.

#### 다른 화면에서도 씁니다

카드 전용 스타일에 묶지 않았습니다. `.admin_help_wrap` + `.admin_help[data-help]` + `.admin_help_pop` 세 요소를 붙이고 `HELP_TEXT` 에 키를 추가하면 어디서든 동작합니다 — 이벤트는 `$(document)` 위임입니다. 카드에 얽힌 규칙은 `.admin_flow_step .admin_help_wrap{margin-left:auto}` 한 줄뿐입니다.

### 작업 현황판 ★ (요청서 06)

6칸 상태판이 **"어디가 막혔나"**, 작업 현황판이 **"지금 무엇이 돌고 있나"** 입니다. 같은 `#panel_flow` 안에 `6칸` → `지금 할 일` → `실행 중` → `최근 작업` → `흐름 요약` 순서로 놓았습니다.

**작업 4종** — `JOB_TITLES` / `JOB_STAGES` / `JOB_TABS` / `JOB_GO_LABELS` 에 키별로 모아 두었습니다.

| key | 이름 | 이동 탭 |
| --- | --- | --- |
| `index` | 문서 색인 | `docs` |
| `generate` | QA 생성 | `generate` |
| `evaluate` | 품질 평가 | `eval` |
| `upload` | 문서 업로드 | `docs` |

**한 번에 하나만** 돕니다. 대기열 UI는 만들지 않았고, 화면은 `JOBS.running` 하나만 그립니다.

#### 실행 중 `#flowJob`

| 요소 | 클래스 / ID |
| --- | --- |
| 제목 | `.admin_job_title` > `.admin_job_spin`(도는 점) + `.admin_job_title_txt` (`{작업 이름} 중`) |
| 우측 메타 | `.admin_job_meta` — 모델명 · `N분 경과` |
| 단계 문구 | `.admin_job_stage` — 서버 `stage` 를 **그대로** 출력 |
| 진행바 | `#flowJobProgress` (기존 `.admin_progress` 규약, `percent` + `done / total`) |
| 중지 | `#flowJobStop` — **확인 모달 없이** 바로. 지금까지 만든 것은 남습니다 |
| 이동 | `#flowJobGo` (`data-goto-tab`) |

`running` 이 `null` 이면 **블록을 통째로 `hidden`** 합니다. 빈 카드를 남기지 않습니다.

#### 상태

| 상황 | 모습 |
| --- | --- |
| 작업 없음 | `#flowJob[hidden]` + 폴링 정지 |
| 실행 중 | 진행바 + 도는 점 + `[중지]` |
| 중지 요청됨 | `#flowJob.is_stopping`, `#flowJobStop` `disabled`, `.admin_job_stopping` 노출(`중지 요청됨 — 진행 중인 항목까지 마치고 멈춥니다`) |
| 실패 | `#flowJob` 을 숨기고 최근 작업 맨 위에 `✕` 줄 + 오류 문구(`.admin_job_row.is_failed` 는 요약을 danger 색으로) |
| 폴링 실패 | 진행바를 그대로 두고 `.admin_job_offline`(`연결이 끊겼습니다. 다시 확인 중…`) 을 덧붙임 |

#### 최근 작업 `#flowJobHistory`

끝난 작업 **5건**을 `.admin_job_row`(`#tpl_job_row`) 로 한 줄씩. 하나도 없으면 `#flowJobHistoryCard` 를 숨깁니다.

- 아이콘 `.admin_job_ico` 4종: `.is_done` `✓` · `.is_stopped` `⚠` · `.is_failed` `✕` · `.is_running` `●`
- **다음 단계 버튼 `.admin_job_next` 는 맨 윗줄에만** 붙습니다(`.admin_job_row.has_next`). 없으면 `—`.
- **`next` 는 서버가 정합니다.** 화면이 작업 종류로 추측하지 않습니다(`05`의 `todo` 와 같은 원칙). `null` 이면 버튼을 감춥니다.
- **`지금 할 일` 배너와 겹치면 배너가 우선** — `renderJobHistory()` 가 `#flowTodo` 가 `.is_clear` 가 아닐 때 버튼을 숨깁니다. 화면에 지시가 둘이면 안 됩니다.

#### 다른 탭에 있어도 보입니다

- 사이드바 `.admin_nav_spin[data-nav-spin="키"]` — 돌고 있는 작업의 항목에만 도는 점. `RAG 문서` · `QA 생성` · `품질 평가` 세 곳에 있고, **검수 배지와 자리가 겹치지 않습니다**(검수 항목에는 `.admin_nav_spin` 이 없습니다).
- **폴링 2초**(`startJobPolling` / `stopJobPolling`), 실행 중인 작업이 없으면 멈춥니다.
- 진행 상태는 서버가 갖습니다 — 화면을 다시 열면 첫 폴링으로 `실행 중` 블록이 복원됩니다. 진행률을 화면 안에만 두지 않았습니다.

**개발 교체 지점**: `pollJobs()` 안의 더미 증가분을 `$.getJSON('/api/admin/jobs')` → `JOBS` 대입 → `renderJob()` 으로 바꾸시면 됩니다. 중지는 `#flowJobStop` 핸들러에서 `POST /api/admin/jobs/{key}/stop`.

### 사용자 피드백 (요청서 10 B·C)

챗봇에서 사용자가 누른 👍/👎 를 관리자 화면 **두 곳**에 같은 데이터로 보여줍니다. 사용자 클릭은 답변 상태를 절대 바꾸지 않습니다 — 내리는 것은 사람이 합니다.

#### ① 질문 이력 `#histTable` — `평가` 열

`유사도` 와 `주제` 사이, 폭 70px, `<th data-col="fb">`. 값은 셋뿐입니다.

| 값 | 표시 |
| --- | --- |
| 👍 | `.admin_fb_badge.is_up` |
| 👎 | `.admin_fb_badge.is_down` — `title` 에 고른 이유 (`내용이 틀려요`) |
| 안 누름 | `.admin_fb_none` `–` |

**대부분은 `–` 입니다.** 비어 보인다고 이상한 게 아닙니다(더미도 12행에 한 번 정도만 값을 넣었습니다). 👎 는 배지 배경으로만 눈에 띄고 **행 전체를 붉게 칠하지 않습니다** — 오류가 아니라 신고입니다.

필터 칩 `.admin_chip[data-fb="down"]` (`👎만`) 을 `data-rt` 줄 뒤에 붙였습니다. 결과 유형 칩과 **배타적**이고, 다시 누르면 `전체` 로 돌아옵니다.

#### ② 검수 — `사용자 신고` 영역

여기가 진짜 목적지입니다. 질문 이력에만 두면 담당자가 일부러 찾아 들어가야 하고, 대개 안 봅니다.

- `#revSort` 에 `<option value="fb_desc">👎 많은순</option>` 추가 (기존 4개 뒤)
- 공용 편집 컴포넌트 안, `검수 메모` 위에 `.admin_ed_feedback` (`data-ed="feedback"`)

| 부분 | `data-ed` |
| --- | --- |
| 접기 버튼 (`aria-expanded`) | `feedbackToggle` |
| `👎 3` 배지 | `feedbackCount` |
| 이유 집계 (`질문과 다른 답이에요 2 · 내용이 틀려요 1`) | `feedbackReasons` |
| 신고 목록 (최근 5건) | `feedbackItems` — `.admin_fb_item` = 일시 · **질문 원문** · 유사도 |
| `질문 이력에서 전체 보기` | `feedbackAll` (5건 초과일 때만) |

- **신고 0건이면 영역을 통째로 `hidden`** 합니다. 대부분의 QA가 여기 해당합니다.
- **접힘이 기본**입니다 — 검수 화면은 이미 세로가 깁니다.
- 실제 질문 원문이 보이는 것이 핵심입니다. 담당자는 이걸 보고 `이 표현이 안 걸리는구나` 를 알고 변형 질문을 추가합니다.
- QA 검수 모달에도 같은 컴포넌트라 자동으로 따라옵니다.

#### 넣지 않은 것

만족도 비율(`82% 도움됨`)·자동 처리 버튼(`👎 3건 이상 자동 미사용`)은 넣지 않았습니다. 대부분은 아무것도 안 누르므로 비율은 거짓말이 되고, 사용자 클릭이 답변 상태를 바꾸면 *검수한 답변만 나간다* 는 전제가 무너집니다. 읽는 방법은 하나입니다 — **어느 QA에 👎가 몰리는가**(절대 개수와 상대 비교).

### 검수 `#panel_review` ★

| | 검수 (`review`) | QA 인덱스 (`qa`) |
| --- | --- | --- |
| 무엇을 보나 | 검수 대기만 | 전체 4상태 |
| 주된 화면 | 한 건 상세 | 목록 |
| 핵심 조작 | `승인하고 다음 건` | 검색·필터·정렬·일괄 |

**편집 폼은 공용 컴포넌트입니다** → 아래 `.admin_editor` 절.

| 영역 | ID / 클래스 |
| --- | --- |
| 큐 헤더 | `.admin_rev_queue` — `#revQueueCount` · 주제 필터(`data-cat-picker="revFilter"`) · `#revSort` · `#revProgress`(`3 / 12`) + `#revBar` |
| 본문 | `#revForm` > `.admin_editor[data-editor="rev"]` |
| 하단 고정 | `.admin_rev_actions` (`position:sticky; bottom:0`) — `#revPrev` `#revHold` `#revDisable` `#revApproveNext`(주 버튼) |

- **확인 모달을 붙이지 않았습니다.** QA 인덱스에서 되돌릴 수 있는 조작입니다.
- **저장 실패는 그 자리에 머무릅니다** — 토스트 `.is_err` + `saveState('rev','err')`, `renderReview()` 를 부르지 않아 다음 건으로 넘어가지 않습니다.
- 상태: 대기 0건 `[data-empty="rev"]`(+`QA 생성으로 이동`) / 불러오는 중 `[data-loading="rev"]` / 저장 중 `#panel_review.is_busy`(버튼 비활성 + 주 버튼 스피너) / 읽기 전용 `#panel_review.is_readonly`(입력 `disabled` + 상단 사유 한 줄).
- 정렬 4종: `score_asc` `score_desc` `recent` `hit`.

### 공용 QA 편집 컴포넌트 `.admin_editor` ★

`#tpl_qa_editor` **하나를 두 곳에 마운트**합니다 — QA 검수 모달과 검수 화면. 두 벌로 만들지 않았습니다.

```js
mountEditor('qa' | 'rev')   // 템플릿 복제 + data-ed → 실제 id 부여 + 팝오버 이름 지정
fillEditor($host, item)     // 값 채우기
renderEdPreview($host)      // 0.3초 디바운스, 챗봇과 같은 렌더 규칙
```

| `data-ed` | qa 인스턴스 id | rev 인스턴스 id |
| --- | --- | --- |
| `question` | `#qaMainQuestion` | `#revQuestion` |
| `answer` | `#qaAnswerEditor` | `#revAnswer` |
| `preview` | `#qaPreview` | `#revPreview` |
| `variants` / `variantInput` | `#qaVariants` / `#qaVariantInput` | `#revVariants` / `#revVariantInput` |
| `category` | `#qaCategorySel` | `#revCategorySel` |
| `sources` | `#qaSources` | `#revSources` |
| `score` | `#qaScore` | `#revScore` |
| `note` | `#qaNote` | `#revNote` |

- **미리보기는 챗봇 말풍선과 렌더 규칙이 같습니다** — `renderMarkdown()`(굵게·코드·번호목록·불릿·문단)에 `.admin_bubble` 스타일. 검수 완료 상태일 때만 검수 메타가 붙습니다.
- 변형 질문: 입력 + **Enter 추가**, 행마다 ⊗ 제거, 중복은 `.admin_row_item.is_dup` + 승인 시 차단.
- 출처 문서(`#tpl_src_item`): 배지를 누르면 `.is_open` 으로 **근거 발췌를 접었다 폅니다.**
- 채점: `.admin_ed_score` — `.is_low`(4점 미만) / `.is_none`. **채점이 없으면 `채점 없음`** 이며 0점이라고 쓰지 않습니다.
- 검수 메모: placeholder `보류한 이유를 남기지 않으면 다음 사람이 같은 판단을 반복합니다`.

### ① 질문 이력
`#histTable` / `#histBody` — 시각 · 질문 · 결과 유형 · 매칭된 QA · 유사도 · 주제 · 채널
필터 `#histFilters`(기간 `#histPeriod`, 직접 지정 시 `#histFrom`/`#histTo` 노출, `[data-rt]` 칩, 카테고리 팝오버), 검색 `#histSearch`, `#histIncludeTest`(기본 꺼짐), `#histExport`.
행 클릭 → `#histModal`: 질문 전문 / 반환된 답변(마크다운 렌더 + 출처 + 검수 메타) / 유사도 / 접수번호, `[data-open-qa]` 로 QA 검수 모달로 이동.

### ② 질문 분석
`#anRunBtn` + `#anProgress`(4단계 진행바) / `#anLastRun`.
KPI `#anKpis` 5개 — 증감은 `.admin_kpi_delta.is_good|.is_bad|.is_neutral`. `QA 없음` 타일은 `[data-kpi="nogap"]` 클릭 시 목록 필터.
차트 `#anCharts` 3개 — 외부 라이브러리 없음: 스택바(CSS) / 추이(인라인 SVG, 전체=실선 teal, 미해결=점선 danger) / TOP5 가로 막대(`[data-topgap]` 클릭 시 카테고리 필터).
묶음 테이블 `#anTable` / `#anBody` — 펼침 `[data-expand]` → `.admin_subrow`(최대 200px 스크롤), 각 원문에 `[data-cl-exclude]`. 일괄 작업 `#anBulkBtn` + `[data-menu="an"]`.

### ③ 질문 카테고리
- 자주 찾는 주제 `#quickCard` / `#quickChips` / `#quickCount`(`4 / 6`, 6개면 `.is_full` + `+ 주제 추가` `disabled` + `#quickHint`) / `#quickSave`. 미사용 카테고리가 담기면 `.admin_notice.is_warn` 자동 삽입 + 칩에 `.is_warn`.
- 좌측 트리 `#catTree` — 대분류 아코디언(`.admin_tree_group.is_open`), `#catSearch` 하이라이트, 미사용은 흐림 + `미사용` 뱃지, `max-height:520px` 로 좌측만 스크롤.
- 우측 상세 `#catDetail` — 빈 상태 → `[data-cat-form]`. `#catGroupSel` `#catName` `#catId`(읽기전용) `#catUsed` / 추천 질문 `#catQuestions`(`#catQAdd`) / `#catDelete` `#catCancel` `#catSave`.
- 대분류 모달 `#catGroupModal` — `#catGroupName` `#catGroupId` `#catGroupUsed`, 수정 시 `#catGroupDelete` + `#catGroupWarn`(하위 개수 경고).

### ④ QA 인덱스
요약 타일 `#qaSummary` 5개(`[data-qasum]` 클릭 시 필터). 목록 `#qaTable`/`#qaBody`, 필터 `#qaFilters`, 검색 `#qaSearch`, 정렬 `#qaSort` + 헤더 정렬, 일괄 `#qaBulkBtn`.
검수 모달 `#qaModal` (`openQaModal(id, {status, readonly})`):

| 영역 | ID |
| --- | --- |
| 상태 / 주제 / 대표 질문 | `#qaStatus` / `[data-cat-picker="qaModal"]` / `#qaMainQuestion` |
| 좌: 마크다운 편집 | `#qaAnswerEditor` (고정폭, 320px+) |
| 우: 챗봇 미리보기 | `#qaPreview` — `.admin_bubble` 로 **챗봇 말풍선과 동일 스타일** 재현, 입력 후 **0.3초 디바운스** 갱신, 상태가 `검수완료`일 때만 검수 메타 표시 |
| 출처 문서 | `#qaSources` + `#qaSourceAdd` → `#docPickModal`(다중 선택) |
| 변형 질문 | `#qaVariants`(최대 240px 스크롤) + `#qaVariantAdd` / `#qaVariantGen`(studio), 중복은 `.admin_row_item.is_dup` + 승인 시 경고 |
| 하단 | `#qaDiscardBtn`(위험·확인 모달) / `#qaSaveBtn`(내용만) / `#qaApproveBtn`(저장 + `검수완료`, 강조) |

### ⑤ RAG 문서
`#docTable` / `#docBody` — 문서 ID · 제목 · 카테고리 · 수정일 · 청크 수 · 연결 QA 수 · 작업.
`#docNewBtn`(studio), 편집 모달 `#docModal`(`#docId` `#docTitle` `#docEditor`). serve는 읽기 전용 + 상단 안내.

**폴더 등록** (요청서 06 · 4번) — `#docUploadBtn`(studio) + `<input id="docUploadInput" webkitdirectory directory multiple hidden>` → `#docUploadModal`(와이드).

| 요소 | id |
| --- | --- |
| 요약 | `#docUploadSummary` — `md 파일 42건을 찾았습니다. (건너뜀 7건 — md/txt 아님)` |
| 덮어쓰기 | `#docUploadOverwrite` (진행 중 `disabled`) |
| 진행바 | `#docUploadProgress` — `42건 중 24건` |
| 결과 표 | `#docUploadBody` — 경로 · 문서 ID · 결과 · 청크 · 비고 |
| 시작 | `#docUploadStartBtn` |

**결과 배지 4종** — 기존 상태 배지 색을 그대로 씁니다: `등록` `.is_done` · `갱신` `.is_applied` · `건너뜀` `.is_hold` · `실패` `.is_excluded`.

**한 요청에 다 보내지 않습니다.** `runUpload()` 가 **3건씩** 나눠 처리하며 결과를 표에 이어 붙이고 진행바를 올립니다(문서당 청킹·임베딩이 몇 초씩 걸리고, 40건을 한 번에 보내면 타임아웃 시 무엇이 들어갔는지 알 수 없습니다). 동시에 작업 현황판에 `upload` 작업으로 올라가므로 모달을 닫아도 진행이 보입니다.

`#docUploadStartBtn` 은 진행 중 `disabled` + `등록 중…`, 끝나면 `완료`로 바뀌고 **계속 `disabled`** 입니다(같은 목록 두 번 올리기 방지).

### ⑥ QA 생성 (studio)
`#genTargetRadio`(문서 `#genDocSel` / 카테고리 팝오버 / 미커버 질문 `#genUncoveredCount`), `#genVariants` `#genNoAnswerRatio`.

**역할별 모델 3개** (요청서 06 · 3번) — 역할마다 잘하는 모델이 다르고, 답변을 쓴 모델이 자기 답을 채점하면 점수가 후해집니다.

| 필드 | id | 비고 |
| --- | --- | --- |
| 질문·변형 모델 | `#genQuestionModel` | |
| 답변 모델 | `#genAnswerModel` | |
| 채점 모델 | `#genJudgeModel` | **첫 항목이 `채점 안 함`(value="")** |
| 경고 문구 | `#genJudgeHint` (`.admin_hint`) | 아래 3상태 |

`#genJudgeHint` 상태 — `renderJudgeHint()`:

| 상황 | 문구 | 모양 |
| --- | --- | --- |
| 채점 모델 = 답변 모델 | `답변 모델과 같습니다. 자기 답에 후한 점수를 줍니다.` | `.is_warn` |
| 채점 안 함 | `채점하지 않습니다. 초안이 점수 없이 검수로 넘어갑니다.` | 보통 |
| 그 외 | 비움 | `:empty` 라 자리도 차지하지 않습니다 |

**`<option>` 은 마크업에 비워 두었습니다.** `fillModelSelects()` 가 `MODELS` / `MODEL_DEFAULT` 로 채우며, 서버 목록으로 교체하는 지점입니다. `#setGenModel` `#evalModel` 도 같은 함수가 채웁니다 — 하드코딩한 모델명은 남기지 않았습니다.
`#genRunBtn` / `#genStopBtn` / `#genProgress` — 불명 → 퍼센트 → 완료, 중지 시 `.is_err` + `중지됨`.
결과 `#genResultTable` / `#genResultBody` — 체크 선택 후 `#genApplyBtn`(확인 모달 경유). 행 클릭 시 검수 모달로 미리 확인.

### ⑦ 품질 평가 (studio)
`#evalCount` `#evalModel` `#evalRunBtn` `#evalProgress`, 요약 `#evalSummary` 4타일, 문항별 `#evalTable`/`#evalBody`.

### ⑧ 설정 — 하위 탭

`.admin_subtab[data-subtab]` + `.admin_subpanel#subpanel_*` (`selectSubtab(key)`). 하위 탭에도 `data-studio-only` 가 적용되고, serve에서 studio 하위 탭이 열려 있으면 `matching` 으로 되돌립니다.

| 하위 탭 | `data-subtab` | 패널 | serve |
| --- | --- | --- | --- |
| 매칭 | `matching` | 기존 매칭 설정 카드 | ✅ |
| 생성 ✳ | `generation` | 기존 생성 설정 카드 | ❌ |
| 납품처 | `profile` | `#profOrg` `#profName` `#profDesc` `#profDomain` `#profLang` + `#profSave` | ✅ |

`조직 이름` 옆 `#profLogoPreview` 가 로고를 실시간으로 보여주고, 저장하면 `BRAND` 를 갱신해 `applyBrand()` 가 화면 전체를 다시 씁니다. 하위 탭이 늘어나도 마크업만 추가하면 됩니다.

**매칭 하위 탭**
`#thMatch`/`#thMatchVal`, `#thRelated`/`#thRelatedVal`, `#thRelatedCount`, `#thSave` `#thResetBtn`.
구간 바 `#thZoneBar` — 3구간(`[data-zone=unresolved|related|answer]`) 폭이 값에 따라 실시간 변경, 눈금 `#thZoneA`/`#thZoneB`.
**`관련 문서 하한 ≥ 답변 매칭 임계값`** 이면 `#thCard.is_zone_invalid` → `#thZoneWarn` 노출 + `#thSave` `disabled`.

---

## 4-A. 브랜드 치환 `data-brand` ★

조직·서비스 이름을 마크업에 박지 않았습니다. 서버가 텍스트만 갈아 끼웁니다.

| 자리 | 마크업 |
| --- | --- |
| 브라우저 탭 | `<title data-brand="관리자 · {service_name}">` |
| 헤더 로고 | `<span class="qr_logo" data-brand="{organization}">` |
| 헤더 제목 | `<h1 class="admin_header_title" data-brand="{service_name} · 관리자">` |
| 로그인 모달 로고 | `<span class="qr_logo" data-brand="{organization}">` |
| 로그인 모달 제목 | `<h2 data-brand="{service_name} 관리자">` |

- **기본 텍스트는 그대로 둡니다** — 파일을 그냥 열어도 화면이 성립합니다.
- 쓸 수 있는 이름: `{organization}` `{service_name}` `{service_desc}`.
- `{organization}` 은 **4자에서 자릅니다**(`applyBrand()` 가 `slice(0,4)`). `{service_name}` 은 헤더에서 `max-width:420px` + 말줄임이라 20자를 넘겨도 레이아웃이 밀리지 않습니다.

---

## 4-B. 자원 경로

`/admin` 으로 서비스되므로 상대경로는 `/admin.css` 로 잘못 풀립니다. **CDN은 없습니다** — 폐쇄망에서 jQuery가 안 오면 화면이 통째로 죽습니다.

| 항목 | 적용 |
| --- | --- |
| jQuery | `/static/vendor/jquery-3.7.1.min.js` |
| CSS · JS | `/static/admin.css` · `/static/admin.js` |
| 폰트 | CDN `<link>` 없음. `font-family` 폴백만 사용 |

`admin.html` 의 `[data-dev-only]` `<script>` 3줄은 로컬 미리보기 폴백입니다(파일을 그냥 열었을 때만 상대경로로 재시도). 이식 시 `data-dev-only` 태그를 지우면 됩니다. 프로젝트의 `static/admin.*` 는 미리보기 사본이니 루트 원본을 쓰세요.

---

## 5. `admin:reorder` 이벤트 명세

드래그 정렬은 **화면 DOM을 이동하지 않습니다.** 드롭 시 커스텀 이벤트만 1회 발생시키므로, 서버 저장이 성공한 뒤 다시 렌더하면 됩니다(실패 시 되돌릴 필요 없음).

```js
$(document).on('admin:reorder', function(e, d){
  // d.kind     : 'group' | 'category' | 'question' | 'quick'
  // d.fromId   : 끌어온 항목의 id (없으면 index)
  // d.toId     : 놓은 대상의 id (없으면 index)
  // d.position : 'before' | 'after'
});
```

- 드롭 대상에는 마우스 위치 기준으로 `data-drop-position="before|after"` 가 부여됩니다.
  세로 목록은 대상 높이의 절반, **가로 칩(`.admin_tag`)은 너비의 절반** 기준입니다.
- 끌고 있는 요소에는 `.is_dragging`.
- 대상 판정: `[data-reorder-kind]` 컨테이너가 있으면 그 값, 없으면 `.admin_tag`→`quick`, `.admin_tree_item`→`category`, 그 외 `group`.
- `admin.js` 하단의 데모 수신부(토스트 표시)는 개발에서 **서버 저장 + 재렌더로 교체**합니다.

---

## 6. 더미 데이터 (개발에서 서버 응답으로 교체)

`admin.js` 최상단 상수:

| 상수 | 규모 |
| --- | --- |
| `CATEGORY_GROUPS` | 대분류 5 / 카테고리 48 (미사용 3건, 일부에 `questions`) |
| `QUICK_CATEGORY_IDS` | 4건 (6개 상한 확인용) |
| `DOCS` | RAG 문서 18건 |
| `QA_ITEMS` | 84건 (상태 4종 혼합, 변형 질문 5~20개) |
| `HISTORY` | 240건 (결과 유형 3종, 테스트 질문 포함) |
| `CLUSTERS` | 64건 (`미분류` 케이스 포함, 상태 5종) |
| `FLOW_DEFAULT` | 진행 현황 한 벌 (문서 24 / 초안 24 / 대기 12 / 반영 286 / 오매칭 4.2% / 0.90 · 0.55) |
| `REVIEW_QUEUE` | 검수 큐 14건 — 답변 짧은 것·20줄짜리, 변형 0~15개, 채점 있음·없음, 출처 0~3건을 섞었습니다 |
| `BRAND` | 납품처 프로필(조직·서비스 이름·한 줄 소개) |
| `MODELS` / `MODEL_DEFAULT` | 설치된 모델 5개 + 역할별 기본값 |
| `JOBS_FIXTURE` | 실행 중 1건(QA 생성 62%) + 최근 작업 5건(done·stopped·failed 섞음) |
| `UPLOAD_FIXTURE` | 폴더 등록 42건 (등록·갱신·건너뜀·실패 섞음) |
| `FB_REPORTS` / `fbForIndex()` | 검수 신고 더미(0·1·3·6건) / 이력 행 평가 (12행당 1건꼴) |
| `FB_REASONS` | `mismatch` `wrong` `thin` 라벨 |
| `HELP_TEXT` | 6칸 도움말 문구 (`data-help` 키별, 요청서 07 · 4번 그대로) |

값은 시드 기반(`rnd`)으로 생성되어 새로고침해도 동일합니다.

---

## 7. 신규 토큰 및 사유

`chat.css` / `quickApiReg.css` 에 없어 추가한 값만 적습니다. 기존 토큰이 있으면 값만 교체하면 됩니다.

| 토큰 | 값 | 사유 |
| --- | --- | --- |
| `--ad-bg` | `#f3f4f6` | 관리자 페이지 바닥. 카드가 많아 챗봇(`#f7f7f8`)보다 한 단 어둡게 |
| `--ad-surface` | `#fff` | 카드·헤더 표면 |
| `--ad-soft` | `#f7f7f8` | 테이블 헤더 · 모달 푸터 |
| `--ad-soft2` | `#f2f2f4` | 중립 배지 · 아이콘 배경 |
| `--ad-line-soft` | `#ececee` | 행 구분선(테두리 `--qr-line` 은 행마다 쓰면 과함) |
| `--ad-ok` / `--ad-ok-bg` | `#2f8f5b` / `#e6f4ec` | `검수완료`·`적중` — teal(정보)과 구분되는 **성공** 색이 필요 |
| `--ad-warn` / `--ad-warn-bg` | `#c8892a` / `#fdf2df` | `related_docs` 중간 톤 · 경고. 요청서 5번의 "노랑/주황 계열" |
| `--ad-danger-bg` | `#fdf3f3` | danger 배경 파생 |
| `--ad-row-hover` | `#f7fbfb` | 테이블 행 hover (teal 아주 옅게) |

그 외 파생 리터럴: teal hover `#25848a`, teal 텍스트 `--qr-teal-ink:#1f6d72`(teal-bg 위 대비), 차트 주황 `#e0a53c`, `QA 생성됨` 보라 `#ede3f6`/`#6b3f96`(studio 배지와 동일 계열), `검토됨` `#eef0f4`/`#5a6478`.

---

## 8. 확인용 상태 목업 바

`[data-dev-only]` — 마크업(`admin.html` 상단 주석 블록), CSS(`admin.css` 맨 아래 블록), JS(`admin.js` 맨 아래 블록) 3곳이 주석으로 분리돼 있어 그대로 삭제하면 됩니다.

- **모드**: `serve` ↔ `studio` (현재 모드 버튼에 `.is_on`)
- **저장**: 저장중 / 성공 / 실패 / 변경됨
- **알림**: 토스트 성공 · 실패
- **데이터**: 빈 상태 / 로딩(스켈레톤) / 검색 결과 없음 — 현재 활성 탭에 적용
- **진행**: 퍼센트 / 불명 / 실패
- **모달**: QA 검수대기 · 검수완료 · 읽기전용 / 확인 / 삭제 확인 / 대분류
- **로그인**: 첫접속 / 세션 만료 / 입력 중 / 시도 중 / 실패 / 연속 실패 잠금 / Caps Lock / 인증 되돌리기
  (`세션 만료` 버튼은 studio + QA 탭을 열어둔 채 모달을 덮어 **배경이 지워지지 않는 것**을 확인시켜 줍니다)
- **피드백**: 이력 👍👎– 섞임 / 👎만 필터 / 검수 신고 0건(영역 숨김) / 신고 3건(펼침)
- **도움말**: ① 열어보기 / ⑥ 왼쪽 펼침 / 긴글·짧은글 함께(①②④ 동시) / 닫기
- **작업**: 없음 / 실행 중 / 중지 요청됨 / 완료 / 실패 / 폴링 실패
- **작업종류**: 문서 색인 · QA 생성 · 품질 평가 · 문서 업로드 (제목·단계 문구가 바뀝니다)
- **최근작업**: 0건 / 1건 / 5건 · 다음단계 있음 / 없음(`next: null`) / **배너와 겹침**(버튼이 숨는지)
- **폴더등록**: 진행 중 / 완료 / 일부 실패
- **모델힌트**: 답변과 동일 / 채점 안 함 / 정상
- **진행현황**: 칸 상태 4종(정상 / 주의 / 할 일 / 잠김) 을 여섯 칸 전체에 걸어 봅니다
- **지금할일**: 검수대기 / 초안 / 초안없음 / 오매칭 / 문서없음 / 할 일 없음 — 6가지 전부
- **검수**: 대기 0건 / 불러오는 중 / 저장 중 / 저장 실패(그 자리에 머무는지) / 읽기 전용 / 대기 되돌리기
- **브랜드**: `긴 이름`(조직 9자·서비스 24자)으로 헤더가 깨지지 않는지 / `기본`
- **드래그**: 드래그 중 + 드롭 대상 표시(2.5초) / 초기화
