# openapi-chat 관리자 화면 — 퍼블 산출물 / 데이터 매핑

## 파일

| 파일 | 내용 |
| --- | --- |
| `admin.html` | 헤더 + 탭 5개 + 패널 + 모달 3종 + 반복 단위 `<template>` |
| `admin.css` | `--qr-*` 토큰 재사용 스타일, 공통 컴포넌트, 애니메이션 |
| `admin.js` | jQuery 목업 동작 (더미 데이터) — `api()` 헬퍼만 실제 `$.ajax` 로 교체 |

사용자 챗봇 화면(`chat.css`)과 동일한 `--qr-*` / `--chat-*` 토큰을 씁니다.
신규 토큰은 2개만 추가했습니다.

| 토큰 | 값 | 사유 |
| --- | --- | --- |
| `--adm-max` | `1360px` | 표 정보량 확보용 넓은 최대 폭 (챗봇의 `--chat-max` 1040px과 역할이 다름) |
| `--adm-ok` | `#2f8f5b` | 저장 **성공** 상태색. 기존 토큰에 성공(초록) 역할이 없음 |

## 구조

- `.admin_page` > `.admin_head` / `.admin_tabs`(`role="tablist"`) / `.admin_body`
- 탭 전환: `.admin_tab.is_active` + `.admin_panel.is_active` 클래스 토글, `aria-selected` 동기화
- 패널 5개: `#panel_prompt` / `#panel_docs` / `#panel_categories` / `#panel_analytics` / `#panel_thresholds`
- 모든 패널 내용은 `.admin_card`(head / body / foot) 단위

## 공통 컴포넌트 ↔ 상태

| 컴포넌트 | 클래스 | 상태 |
| --- | --- | --- |
| 저장 상태 | `.admin_save_state` | 기본(빈 값 → `display:none`) / `.is_busy`(스피너) / `.is_ok`(`--adm-ok`) / `.is_err`(`--qr-danger`). `setState($el, 'ok'|'err'|'busy'|null, text)` |
| 변경됨 표시 | `.admin_dirty` | 부모 카드에 `.is_dirty` 가 있을 때만 노출(빨간 점 + "변경됨") |
| 데이터 테이블 | `.admin_table` (`.admin_table_wrap` 스크롤) | `thead th` sticky, 행 hover, 빈 상태 `.admin_empty` |
| 인라인 검색 | `.admin_search` | 기본 / `.is_filled`(✕ 클리어 노출) / `.is_noresult`(테두리 경고) |
| 토글 스위치 | `.admin_switch` (체크박스 기반) | on(`input:checked`) / off / disabled(`input:disabled`) |
| 필 태그 | `.admin_tag` + `.admin_tag_x` | 기본 / ✕ hover 시 danger |
| 드래그 핸들 | `.admin_drag` | 기본 / 행에 `.is_dragging` / 대상 행에 `.drop_target` |
| 확인 모달 | `#confirmModal` (`.qr_modal` 소형 + `.qr_modal_danger`) | 일반 / 위험(제목 danger 색) |
| 로딩 | `.admin_loading.is_on` + `.admin_skel` | 스켈레톤 3줄 |
| 토스트 | `.admin_toast` (`#adminToasts`) | `.is_ok` / `.is_err`, 3초 후 `.is_out` → 제거 |

드래그 정렬은 요청대로 **마크업 + 상태 스타일까지만**입니다. `dragstart`/`dragend`/`dragover` 로
`.is_dragging` · `.drop_target` 만 토글하며, 실제 순서 변경/저장은 개발에서 처리합니다.

## 탭 ① 시스템 프롬프트

| 요소 | ID | 비고 |
| --- | --- | --- |
| 프롬프트 textarea | `#spPrompt` | `.admin_textarea.is_code`, `rows=14`, 세로 리사이즈 |
| 저장 | `#spSave` | 클릭 → `busy` → `ok` + 토스트 |
| 저장 상태 | `#spState` | `.admin_save_state` |
| 변경됨 | `#spCard.is_dirty` | `input` 이벤트에서 부여, 저장 성공 시 제거 |

## 탭 ② RAG 문서 관리

| 요소 | ID / 클래스 | 필드 |
| --- | --- | --- |
| 검색 | `#docSearch` (`#docSearchWrap`) | 제목·문서 ID 부분일치 |
| 새 문서 | `#docNewBtn` | 모달을 `새 문서` 모드로 |
| 테이블 | `#docTable` / `#docTableBody` / `#docTableWrap` | 행 템플릿 `#tpl_doc_row` |
| 행 바인딩 | `tr[data-doc-id]` | `doc_id` / `title` / `category` / `url` / `updated_at` / `chunks` |
| 행 작업 | `[data-doc-edit]` / `[data-doc-delete]` | 삭제는 `#confirmModal` 경유 (`confirm()` 미사용) |
| 빈 상태 | `#docEmpty` | 등록 0건 / 검색 결과 0건 두 문구를 JS에서 교체 |
| 로딩 | `#docLoading` | `.is_on` 시 표 숨김 |
| 에디터 모달 | `#docEditor` (`.qr_modal_wide`, 940px) | `#docId` `#docContent` `#docSaveBtn` `#docCancelBtn` `#docState` |

에디터는 신규/수정 공용이며 제목(`#docEditorTitle`)만 `새 문서` / `문서 수정` 으로 바뀝니다.
수정 모드에서는 `#docId` 가 `readonly` 입니다.

## 탭 ③ 질문 카테고리 (신규)

데이터: `admin.js` 상단 `CATEGORY_GROUPS` (5 대분류 / **48 카테고리**).
카테고리 1건 = `{ id, label, group_id, doc_ids: [], enabled, sort, questions: [] }`.

| 요소 | ID / 클래스 | data 속성 |
| --- | --- | --- |
| 탭 버튼 | `.admin_tab[data-tab="categories"]` | — |
| 패널 | `#panel_categories` | — |
| 트리 | `#catTree` (빈 상태 `#catTreeEmpty`) | — |
| 대분류 행 | `.admin_cat_group` (펼침 `.is_open`) | `data-group-id` |
| 대분류 수정 | `[data-group-edit]` | — |
| 카테고리 행 | `.admin_cat_item` (선택 `.is_selected`, 미사용 `.is_off` + `.admin_badge_off`) | `data-category-id`, `data-group-id` |
| 검색 | `#catSearch` | 카테고리명 부분일치 + `<mark>` 하이라이트 (2차 팝오버와 동일) |
| 대분류 추가 | `#catGroupAddBtn` | — |
| 카테고리 추가 | `#catAddBtn` | 신규 모드 — `#catId` 입력 가능 |
| 상세 영역 | `#catDetail` (빈 상태 `#catDetailEmpty`, 폼 `#catDetailForm`, 액션 `#catDetailFoot`) | `data-category-id` |
| 상세 필드 | `#catGroupSel` `#catLabel` `#catId`(수정 시 readonly) `#catDocs` `#catEnabled` | — |
| 연결 문서 태그 | `.admin_tag[data-doc-id]` (`#catDocTags`) | `data-doc-id` |
| 추천 질문 목록 | `#catQuestions` (개수 `#catQCount`, 추가 `#catQAddBtn`) | — |
| 추천 질문 행 | `.admin_cat_q` | `data-index` (삭제 후 재부여) |
| 추천 질문 없음 | `.admin_q_empty` | — |
| 저장/삭제 | `#catSaveBtn` `#catDeleteBtn` `#catCancelBtn` `#catState` | — |
| 대분류 모달 | `#catGroupModal` | `#catGroupLabel` `#catGroupId` `#catGroupEnabled` `#catGroupSaveBtn` `#catGroupDeleteBtn` + 경고 `#catGroupWarn` |

- 좌측 트리만 스크롤(`max-height: 560px`), 우측 상세는 영향받지 않습니다.
- `#catSaveBtn` payload: `{ id, label, group_id, doc_ids[], enabled, questions[] }`
- 삭제(카테고리·대분류)는 모두 `#confirmModal` 을 경유합니다. 대분류 모달에는 하위 카테고리 개수를
  넣은 경고 문구(`#catGroupWarnText`)가 들어갑니다.
- 2단 분할은 `grid-template-columns: minmax(300px, 360px) minmax(0, 1fr)` — 1280px에서도 우측이 좁아지지 않습니다.

## 탭 ④ 질문 분석 / 개선 (신규)

관리자의 작업 순서 = **발견 → 판단 → 문서화** 를 그대로 화면 순서로 잡았습니다:
분석 실행 바 → KPI 타일 → 차트 3종 → 질문 클러스터 테이블 → 문서 초안 생성 모달.
더미: `ANALYTICS`(요약·경로·추이·상위 미해결) + `CLUSTERS` **62건**(status·coverage·trend 전 조합 혼합,
클러스터당 원문 4건). 외부 차트 라이브러리 없이 인라인 SVG / CSS 로만 그립니다.

### 답변 경로 4색 — 화면 전체 고정

| 경로 | 클래스 | 색 |
| --- | --- | --- |
| cache | `.admin_route.is_cache` | 회색 (`#f1f1f2` / `--qr-ink-soft`) |
| intent | `.admin_route.is_intent` | 연한 틸 |
| rag | `.admin_route.is_rag` | `--qr-teal-bg` / `--qr-teal` |
| fallback | `.admin_route.is_fallback` | `--qr-danger` 계열 — **미해결 = 문서화 대상**을 위험색으로 |

같은 4색이 스택바(`.admin_stackbar_seg`)·레전드(`.admin_legend i`)·테이블 배지·원문 목록에서 동일하게 쓰입니다.

### AI 생성 값 시각 힌트

운영자가 확정값과 AI 추론값을 헷갈리면 잘못된 문서가 그대로 RAG에 들어가므로, AI가 만든 값에는
항상 힌트를 붙입니다.

| 용도 | 클래스 |
| --- | --- |
| 섹션 설명의 "AI 추론" 배지 | `.admin_ai_badge` |
| 컬럼 헤더의 점 표시 | `.admin_ai_dot` |
| 대표 질문·요약·추정 카테고리 텍스트 | `.is_ai_text` (보라 점선 밑줄) |
| 초안 입력 필드 | `.admin_input.is_ai` / `.admin_select.is_ai` / `.admin_textarea.is_ai` |
| 초안 모달 상단 고지 | `.admin_ai_notice` |

### ① 분석 실행 바

| 요소 | ID | 비고 |
| --- | --- | --- |
| 기간 | `#anPeriod` | 7/30/90/전체 |
| 실행 | `#anRunBtn` | 실행 중 `disabled` |
| 마지막 분석 / 대상 | `#anLastRun` / `#anLogCount` | — |
| 진행 영역 | `#anProgress` (`hidden` 토글) | `.is_indeterminate` = 초기 임베딩(진행률 불명) 단계, 이후 퍼센트 모드 |
| 진행바 / 퍼센트 / 문구 | `#anProgressFill` / `#anProgressNum` / `#anProgressLabel` | — |
| 상태 | `#anRunState` | `.admin_save_state` |

### ② KPI 타일

`#kpiTotal` 총 질문 / `#kpiUnique` 고유 질문(클러스터) / `#kpiUnresolved` 미해결률 /
`#kpiNoDoc`(버튼, `#kpiNoDocValue`) 문서 없음 / `#kpiLatency` 평균 응답.
`#kpiNoDoc` 클릭 시 `anFilter = 'no_doc'` 로 테이블이 필터링되고 타일·칩에 `.is_active` 가 붙습니다.
`unique` / `no_doc` 은 상수값이 아니라 `renderAnKpi()` 에서 `CLUSTERS` 로부터 파생시키고,
초안 저장·상태 변경 등으로 `has_doc`/`status` 가 바뀔 때마다 다시 호출해 **타일 숫자와 드릴다운 결과가
항상 일치**하도록 했습니다. 미해결률 더미도 `top_route` 와 맞물려 생성됩니다(fallback 행은 32% 이상).
증감 문구는 `.admin_kpi_sub.is_up`(악화=danger) / `.is_down`(개선=ok).

### ③ 차트 3종

| 차트 | 요소 | 구현 |
| --- | --- | --- |
| 답변 경로 분포 | `#anRouteBar` + `#anRouteLegend` | 도넛 대신 가로 스택바(CSS) |
| 일자별 질문 추이 | `#anTrendChart` + `#anTrendAxis` | 인라인 SVG polyline 2개(전체 실선 / 미해결 점선) + area |
| 미해결 상위 카테고리 | `#anTopBars` | 가로 바 목록(`.admin_bar_*`) |

### ④ 질문 클러스터 테이블

| 요소 | ID / 클래스 | data 속성 |
| --- | --- | --- |
| 검색 | `#anSearch` (`#anSearchWrap`) | 대표 질문 부분일치 |
| 필터 칩 | `#anFilters .admin_chip` (`.is_active`) | `data-filter` = all/no_doc/unresolved/new/applied |
| 정렬 | `#anSort` | count / unresolved / recent |
| 전체 선택 | `#anCheckAll` | — |
| 테이블 | `#anTable` / `#anTableBody` (`.admin_table_dense`) | 빈 상태 `#anEmpty` |
| 행 | `.admin_an_row` (펼침 `.is_open`, 제외 `.is_excluded`) | `data-cluster-id` |
| 행 바인딩 | `question`(AI) / `summary`(AI) / `category_label`(AI) / `count` / `unresolved_rate` / `top_route` / `trend` / `status` | 템플릿 `#tpl_an_row` |
| 펼친 원문 영역 | `.admin_an_detail` (`#tpl_an_raw_wrap`) | `data-cluster-id` |
| 원문 1건 | `.admin_an_raw` (`#tpl_an_raw`, 제외 `.is_excluded`) | `data-raw-id`, `[data-raw-exclude]` |
| 클러스터 상태 변경 | `[data-cluster-status="reviewed"|"excluded"]` | — |
| 초안 생성 | `#anDraftBtn`(선택 N건, `#anSelCount`) / 행별 `[data-cluster-draft]` | — |

상태 5종 배지 `.admin_st`: `.is_new`(신규·danger 톤) / `.is_reviewed`(검토됨) / `.is_drafted`(초안생성·AI 보라) /
`.is_applied`(반영됨·초록) / `.is_excluded`(제외·흐림). 미해결률 40% 이상은 `.admin_an_rate.is_high`.
추이는 `.admin_trend.is_up/.is_down/.is_flat`. 행 높이는 다른 탭보다 조밀합니다(본문 13px).

원문 개별 `[이 질문 제외]` 는 오타·장난 질문이 클러스터를 오염시키는 걸 사람이 걷어내기 위한 장치로,
토글식(제외 ↔ 제외 취소)입니다.

### ⑤ RAG 문서 초안 생성 모달 (`#anDraftModal`, 4단계)

| 단계 | 마크업 | 표시 |
| --- | --- | --- |
| 생성중 | `.admin_draft_stage[data-stage="generating"]` | 스피너 + 소요 안내 |
| 결과 | `[data-stage="result"]` | `.admin_ai_notice` + `#anDraftDocId` / `#anDraftCategory` / `#anDraftContent` (모두 `.is_ai`) |
| 저장중 | `#anDraftState.is_busy` (결과 단계 유지) | 저장 버튼 상태 |
| 실패 | `[data-stage="error"]` + `#anDraftRetryBtn` | `.admin_warn` |

근거 클러스터는 `#anDraftTags` 의 `.admin_tag[data-doc-id]`(= cluster id)로 모든 단계에 공통 노출됩니다.
저장하면 `DOCS` 에 새 문서가 추가되어 탭②에 즉시 나타나고, 근거 클러스터 상태가 `반영됨` 으로 바뀝니다.

### 이번 범위에서 제외

세션 대화 재생 / 사용자별 조회(개인정보) / 클러스터 수동 병합·분리 UI.
마지막 항목은 1차 운영 후 필요 여부를 보고 넣는 편이 낫다고 판단했습니다 — 지금부터 필요하면 추가합니다.

### 5차 보완 — 카테고리 필터 / 추천 질문 등록 경로

요소 네이밍은 산출물 기준(`#panel_analytics`, `an*`)으로 확정했습니다. 범위는 `#panel_analytics` 안이며
`chat.js` / `chat.css` 는 수정하지 않고 팝오버 마크업·스타일만 **복사 이식**했습니다(동일 클래스명 `chat_cat_*`).

#### A. 카테고리 필터 (`#anCatTrigger` / `#anCatPopover`)

| 요소 | ID / 클래스 | 비고 |
| --- | --- | --- |
| 트리거 | `#anCatTrigger` (`.chat_cat_trigger`, 선택 시 `.is_active`) | 내부 `.chat_cat_trigger_main` + `.chat_cat_clear[data-category-clear]` |
| 팝오버 | `#anCatPopover` (`.chat_cat_popover`, 열림 `.is_open`, 결과없음 `.is_empty`) | 위로 열리는 챗봇과 달리 툴바 아래로 열립니다(`top: calc(100% + 8px)`) |
| 검색 | `#anCatSearch` | 부분일치 + `<mark>` 하이라이트 |
| 특수 항목 | `#anCatSpecial` 안의 `.chat_cat_item[data-category-id="all"|"none"]` | **전체 카테고리 / 미분류(AI가 분류 못함)** |
| 대분류 / 항목 | `.chat_cat_group_head[data-group-id]` / `.chat_cat_item[data-category-id]` | 템플릿 `#tpl_an_cat_group`, `#tpl_an_cat_item` |
| 항목별 건수 뱃지 | `.admin_cat_num` (0건은 `.is_zero`) | `clusterCountFor(id)` 로 계산 |

- 더미에 `category_id: null` 클러스터 **7건**을 넣어 `미분류` 필터가 실제로 검증됩니다.
- 선택 시 테이블뿐 아니라 **KPI 타일·차트 3종이 함께 재계산**됩니다
  (`renderClusters()` → `renderAnKpi(list)` / `renderAnCharts(list)`; 경로 분포·상위 미해결은 필터 집합에서
  파생, 추이는 건수 비중으로 스케일). 헤더의 `대상 N건`·KPI 총 질문도 같은 파생값을 씁니다.
- 기존 상태 칩(`#anFilters`) · 카테고리 · 검색은 **AND** 조건이며, 적용된 조건은 `#anApplied` 의
  필 태그(`[data-applied-remove]` 로 개별 해제)와 `#anAppliedCount`(N건 / 전체 M건), `#anResetBtn`(전부 해제)로 노출됩니다.

#### B. 추천 질문 등록 경로

운영 루프 두 갈래 중 ⓑ(답변 잘 됨 → 추천질문)를 보완했습니다. `[문서 초안 생성]`을 분할 버튼으로 바꿨습니다.

| 요소 | ID / 클래스 | 비고 |
| --- | --- | --- |
| 주 버튼 / 더보기 | `#anDraftBtn`(`.admin_split_main`) / `#anMoreBtn`(`.admin_split_more`) | `.admin_split_btn` 래퍼, 선택 0건이면 둘 다 `disabled` |
| 메뉴 | `#anMoreMenu` (`role="menu"`, `.admin_menu_item[data-action]`) | `promote` / `assign` / `exclude` |
| 추천질문 등록 모달 | `#anPromoteModal` | `#anPromoteCat`(등록 대상 카테고리) / `#anPromoteRows` / `#anPromoteCount` / `#anPromoteDupHint` / `#anPromoteSaveBtn` / `#anPromoteState` |
| 등록 행 | `.admin_promote_row` (`#tpl_an_promote_row`, 중복 시 `.is_dup`) | `data-cluster-id`, 편집 가능한 `input[data-bind="question"]`, 원문은 `.is_ai_text` 로 병기 |
| 카테고리 지정 모달 | `#anAssignModal` | `#anAssignTags` / `#anAssignCat` / `#anAssignSaveBtn` / `#anAssignState` |
| 일괄 제외 | `#confirmModal` 경유 (`bulkExclude()`) | 행 단위 원문 제외 토글은 그대로 유지 |

- **문구 편집이 핵심**: 대표 질문은 원문에서 뽑은 값이라 `ㅇㅇ 템플릿 수정` 같은 날것이 섞입니다.
  모달에서 다듬은 초안을 제공하고(접두 감탄사·`(변형 표현)` 꼬리 제거, 물음표 보정) 운영자가 최종 편집합니다.
  선택한 카테고리에 **이미 있는 문구는 자동으로 체크 해제**되고 `이미 등록된 문구` 뱃지가 붙습니다.
  카테고리를 바꾸면 중복 판정이 다시 계산됩니다.
- 등록하면 해당 카테고리의 `questions` 에 추가되어 **탭③ 상세와 챗봇 추천 질문에 즉시 반영**되고,
  클러스터에 `.admin_st.is_promoted`(추천질문) 뱃지가 붙습니다. 이 뱃지는 `반영됨`과 다른 축이므로
  **한 행에 뱃지 2개**가 함께 표시됩니다(`.admin_st + .admin_st`).
- **AI값 → 확정값 전환**: 카테고리 지정 모달에서 확정하면 해당 셀의 `.is_ai_text`(보라 점선)가 제거되고
  `.is_confirmed`(체크 마크 + 진한 텍스트)로 바뀝니다. 화면에서 이 전환이 보이는 유일한 지점입니다.

#### C. 그 외

- 임계값 기본값 정정: 캐시 유사도 **0.95** / 의도분류 **0.85** / 검색 문서 개수 **5**
  (`DEFAULT_THRESHOLDS` 상수와 `.admin_hint_badge` 문구 동시 수정, 검색 임계값 0.35는 유지).
- 클러스터당 원문 더미를 **31~39건**으로 늘려 `.admin_an_raws`(max-height 240px) 스크롤을 검증할 수 있습니다.
- 페이지네이션은 이번 범위에서 보류했습니다. 넣을 자리는 `#anTable` 을 감싼 `.admin_table_wrap` **직후**,
  `#anEmpty` 앞이며(`.admin_pager` 예정), `renderClusters()` 의 `anFiltered` 배열을 slice 하는 지점이
  유일한 로직 변경점입니다.

### 6차 — 자주 찾는 주제 (탭 ③ 최상단 카드)

챗봇 인트로(`#chatCatQuick` / `.chat_cat_quick_chip`)에 노출되는 칩 6개를 지정하는 화면입니다.
카테고리 트리와 성격이 달라 2단 분할 **위쪽**에 별도 `.admin_card` 로 두었습니다.
더미 상수는 `admin.js` 상단 `quickCategoryIds`(서버의 `quick_category_ids`), 최대 개수는 `QUICK_MAX`.

| 요소 | ID / 클래스 | 비고 |
| --- | --- | --- |
| 카드 | `#quickCard` (변경 시 `.is_dirty`, 6개 시 `.is_full`) | — |
| 칩 목록 | `#quickChips` | **표시 순서 = 챗봇 노출 순서** |
| 칩 1개 | `.admin_quick_chip`(`.admin_tag` 변형, `#tpl_quick_chip`) | `data-category-id`, `data-category-label`, 말줄임 + `title`, 드래그 핸들 + `.admin_tag_x[data-quick-remove]` |
| 미사용 뱃지 | `.admin_badge_off` | `enabled: false` 카테고리에만 |
| 개수 | `#quickCount` | `4 / 6` |
| 추가 버튼 | `#quickAddBtn` | 6개면 `disabled` + `#quickHint` 문구 교체 |
| 선택 팝오버 | `#quickCatPopover` (`#anCatPopover` 구조 재사용, 특수 항목 없음) | 검색 `#quickCatSearch`, 목록 `#quickCatGroups` |
| 팝오버 항목 | `.chat_cat_item` (담긴 것 `.is_selected` + 체크, 미사용 `.is_off`) | 클릭 = 추가/제거 토글 |
| 빈 상태 | `#quickEmpty` | 0개일 때 |
| 경고 | `#quickWarn` (`.admin_warn`) | 미사용 카테고리가 담겼을 때 |
| 저장 / 상태 | `#quickSaveBtn` / `#quickState` | 422 실패는 `.admin_save_state.is_err` |

- 저장 payload 는 `{ quick_category_ids: [...] }` — 실제로는 카테고리 트리와 함께 `PUT /admin/categories`.
- 카테고리를 삭제하면 `quickDropCategory(id)` 로 이 목록에서도 빠지며, 삭제 확인 모달 문구에도
  "자주 찾는 주제에 포함되어 있으면 함께 제거됩니다."가 들어갑니다.

### 6차 — 드래그 정렬 (`admin:reorder`)

드롭 대상에 `data-drop-position="before" | "after"`(마우스 Y가 대상 높이 절반보다 위면 `before`)를
부여하고, `drop` 시 커스텀 이벤트를 **1회** 발생시킵니다. 화면 DOM 이동은 하지 않습니다
(서버 저장 실패 시 되돌리기가 쉽도록 개발 쪽에서 다시 그리는 방식 권장).

```js
$(document).on('admin:reorder', function (e, d) {
  // d = { kind: 'category'|'group'|'question'|'quick', fromId, toId, position: 'before'|'after' }
});
```

| kind | 대상 요소 | id 소스 |
| --- | --- | --- |
| `group` | `.admin_cat_group` | `data-group-id` |
| `category` | `.admin_cat_row` | 내부 `.admin_cat_item[data-category-id]` |
| `question` | `.admin_cat_q` | `data-index` |
| `quick` | `.admin_quick_chip` | `data-category-id` |

목업에는 확인용으로 이벤트 수신 시 토스트를 띄우는 핸들러가 있습니다(개발 이식 시 삭제).

## QA 가져오기 (`#qaImportModal`)

스튜디오(사내 작업 PC)에서 만든 QA 파일을 서버로 들여오는 경로입니다. ⑤ RAG 문서의 `폴더 등록`
(`#docUploadModal`)과 같은 구조 — 파일 선택 → 미리보기 → 실행 → 결과표. **새 탭은 없습니다.**

> ⚠️ 진입 버튼 `#qaImportBtn` 은 요청서상 사이드바 ④ `검수` 화면 머리에 놓여야 하지만, 이 산출물에는
> 아직 사이드바·검수 화면이 없어(선행 요청서 05·06은 이식본에서 진행) 임시로 ⑤ RAG 문서 카드 머리에
> 두었습니다. **id 는 그대로이므로 이식 시 버튼 마크업 한 덩이만 검수 화면 머리로 옮기면 됩니다.**

| 요소 | ID / 클래스 | 비고 |
| --- | --- | --- |
| 진입 버튼 | `#qaImportBtn` | 이식 시 검수 화면 머리로 이동 |
| 모달 | `#qaImportModal` (`.qr_modal_wide`) | 3단계 `.admin_import_stage[data-stage="pick"|"preview"|"run"]` |
| 안내 문구 / 도움말 | `.admin_import_lead` / `#qaImportHelp` + `#qaImportHelpBox` | `?` 토글 (요청서 07 방식) |
| 파일 놓는 자리 | `.admin_import_drop` (`#qaImportDrop`, `#qaImportFile`) | `.json` 1개, 끌어놓기 `.is_over` / 잘못된 확장자 `.is_invalid` |
| 고른 파일 | `#qaImportFileInfo` | `file_name` / `file_size` + 해제 `#qaImportFileClear` |
| 요약 3칸 | `.admin_import_sum` · `[data-sum="new"|"over"|"skip"]` | **서버가 계산한 값**을 표시 (화면이 세지 않음) |
| 미리보기 표 | `#qaImportPreviewBody` (`#tpl_qa_prev_row`) | 상태 / 대표 질문 / 주제 / 점수, 표 영역만 스크롤(300px) |
| 상태 배지 | `.admin_qa_st.is_new|.is_over|.is_skip|.is_added|.is_fail` | `새로` / `덮음` / `건너뜀` / `추가` / `실패` |
| 덮어쓰기 체크 | `#qaImportOverwrite` | **끈 상태가 기본**. 끄면 `over` → 전부 `skip` 으로 재계산 |
| 미리보기 0건 | `#qaImportPreviewEmpty` | 실행 버튼 `disabled` |
| 진행 막대 | `.admin_progress` (`#qaImportProgress`, `#qaImportProgressFill`, `#qaImportProgressNum`) | `9 / 12` 형식 |
| 결과표 | `#qaImportResultBody` (`#tpl_qa_result_row`) | 대표 질문 / 결과 / 비고, 실패 줄 유지 |
| 버튼 | `#qaImportCheckBtn` / `#qaImportStartBtn` / `#qaImportGotoBtn`(`data-goto-tab="review"`) | 단계별로 하나만 노출 |
| 상태 문구 | `#qaImportState` | `.admin_save_state` 재사용 |

### 3단계 상태 규칙

| 단계 | 조건 | 노출 |
| --- | --- | --- |
| ① pick | 파일 없음 | 드롭존만, `#qaImportCheckBtn` `disabled` |
| ① pick | `.json` 1개 선택 | `#qaImportFileInfo` + `내용 확인` 활성 |
| ① pick | 확장자 불일치 | `.admin_import_drop.is_invalid` + `#qaImportState.is_err` |
| ② preview | 덮어쓸 것 있음 | `[data-sum="over"]` > 0 → 실행 시 `#confirmModal` 한 번 더 |
| ② preview | 전부 새로 | `over` 0 → 확인 모달 없이 바로 실행 |
| ② preview | 0건 | `#qaImportPreviewEmpty`, `#qaImportStartBtn` `disabled` |
| ③ run | 전송 중 | 진행 막대 + 결과표에 청크 단위로 행 추가 |
| ③ done | 완료 | `검수 화면으로` 노출, 실패 줄은 `비고`(예: `주제 없음`)와 함께 남김 |

### 지켜지고 있는 규칙 셋

1. **들여온 QA 는 무조건 검수 대기** — 결과표 `비고` 가 항상 `검수 대기` 이고,
   `승인 상태로 가져오기` 류의 선택지는 마크업에 없습니다.
2. **운영에서 쌓인 값은 덮지 않음** — `.admin_import_note` 와 확인 모달 문구에 명시
   ("적중 횟수와 사용자 신고는 서버 값이 유지됩니다").
3. **되돌리기 없음** — 미리보기가 마지막 확인 지점이며, `over > 0` 이면 `#confirmModal` 을 경유합니다.

### 개발 연동 지점

- `#qaImportCheckBtn` → 미리보기 조회(`api('previewQa', …)`). **요약 숫자와 상태 열은 서버 값**을 그대로 씁니다.
- `qaRun()` 은 `QA_CHUNK`(기본 3) 건씩 나눠 `api('importQa', { items, overwrite })` 를 반복 호출합니다.
  한 요청에 전부 담으면 진행을 보여줄 수 없고 타임아웃 시 무엇이 들어갔는지 알 수 없어서입니다.
- 목업 데이터는 `qaDummy()` 하나에 모여 있습니다(개발 이식 시 삭제).

### 자원 경로 (이식 시 2줄)

운영이 폐쇄망이므로 이식본에서는 절대경로로 바꿔주세요. 산출물은 미리보기가 되도록 상대경로로 두었고,
CDN·웹폰트는 `admin.*` 에 없습니다(jQuery만 CDN → 아래처럼 교체).

```html
<link rel="stylesheet" href="/static/admin.css">
<script src="/static/vendor/jquery-3.7.1.min.js"></script>
<script src="/static/admin.js"></script>
```

## 탭 ⑤ 임계값 설정

| 요소 | ID | 기본값 |
| --- | --- | --- |
| 검색 임계값 | `#thFloor` + `.admin_range[data-range-for="thFloor"]` | 0.35 |
| **약한 근거 하한** | `#thSoftFloor` + 동일 패턴 (`#thFloor` 바로 다음) | 0.20 |
| 캐시 유사도 | `#thCache` + 동일 패턴 | 0.95 |
| 의도분류 임계값 | `#thIntent` + 동일 패턴 | 0.60 |
| 검색 문서 개수 | `#thTopK` (숫자만, 1~20) | 5 |
| 저장 / 되돌리기 / 상태 | `#thSave` / `#thResetBtn` / `#thState` | — |
| **컨텍스트 창** | `#thNumCtx` (`#genCard`, min 2048 / max 131072 / step 1024) | 8192 |
| **답변 최대 길이** | `#thNumPredict` (`#genCard`, min 128 / max 8192 / step 128) | 1024 |
| LLM 카드 저장 / 상태 | `#genSave` / `#genState` | 범위 밖이면 422 → `.is_err` |

**검색 유사도 3구간 미리보기**(`#thZoneBar`): `#zoneFallback`(미해결, fallback danger 톤) /
`#zoneSoft`(약한 근거, 중간 톤) / `#zoneOk`(정상 답변, rag teal 톤) 의 폭이 두 값에 따라 실시간으로
변합니다. `약한 근거 하한 ≥ 검색 임계값` 이면 `.is_invalid` + `#thZoneErr` 경고 + `#thSave` `disabled`.
축 라벨은 `#zoneMarkSoft` / `#zoneMarkFloor`.

숫자 입력과 슬라이더는 `data-range-for` 로 짝지어 양방향 동기화됩니다. 기본값은 `DEFAULT_THRESHOLDS` /
`DEFAULT_GEN` 상수와 `.admin_hint_badge` 문구 두 곳에 있으니 값 변경 시 함께 수정하세요.
2열 그리드(`.admin_grid2`), LLM 생성 설정은 별도 카드(`#genCard`, 숫자 입력만).

## 개발 연동 지점

`admin.js` 의 `api(action, payload, done)` 헬퍼 하나만 실제 호출로 교체하면 됩니다
(현재는 700ms 후 `{ ok: true }` 를 돌려주는 더미). 더미 데이터 `DOCS` / `CATEGORY_GROUPS` /
`DEFAULT_THRESHOLDS` 는 파일 상단에 모여 있습니다.

## 퍼블 확인용 devbar

`[data-dev-only="true"]` 상단 회색 바에서 저장 상태 3종·변경됨·토스트 2종·문서 빈 상태·문서 로딩·
카테고리 미선택 · 분석 진행바 · 초안 생성 실패 상태를 즉시 확인할 수 있습니다. 개발 이식 시 해당 마크업과 `admin.css` 의
`.admin_devbar` 블록, `admin.js` 하단 목업 핸들러를 삭제하세요.
