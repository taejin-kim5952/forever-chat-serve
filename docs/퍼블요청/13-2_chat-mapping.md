# chat-mapping — 사용자 화면 재설계 (13 · 13-1)

산출물: `chat.html` · `chat.css` · `chat.js` · `fonts/` (Pretendard 400·500·600·700 woff2)
런타임: 바닐라 JS 만 사용합니다. 템플릿 문법·커스텀 엘리먼트·인라인 `style` 없음.

## 유지한 이름
| 이름 | 자리 |
| --- | --- |
| `#chatInput` | 질문 입력 textarea (Enter 전송, Shift+Enter 줄바꿈, 한글 조합 중 전송 막음) |
| `#chatSend` | 전송 버튼. 스트리밍 중 `중단` — `data-state="send" \| "stop"`, 클래스 `chat_btn--primary` ↔ `chat_btn--outline` |
| `.chat_msg` | 메시지 한 건. `data-role="user" \| "bot"`, 봇은 `data-mode="ai" \| "verified"` |
| `.chat_md` | 마크다운 렌더 자리 (p·h1~3·ul·ol·table·code·pre·a·blockquote 스타일) |
| `[data-doc-open]` | 커버 카드(서재·참고 자료 공통). 값 = `doc_id`. 클릭 → 문서 원문 모달 |
| `[data-brand="{app_name}"]` · `[data-brand-logo]` | 서비스 이름·로고 (서버가 채움) |

## 이전 시안(Chat.dc.html) → 이번 산출물
| 이전 | 이번 |
| --- | --- |
| `KTDesignSystem.Switch #chatAiMode` | `label.chat_switch > input#chatAiMode[role=switch]` |
| `KTDesignSystem.Switch #chatReasoning` | `label.chat_switch > input#chatReasoning[role=switch]` |
| `KTDesignSystem.Select #chatModel` | `select#chatModel.chat_select.chat_select--sm` |
| `KTDesignSystem.Select` (프로젝트) | `select#chatProject.chat_select` |
| `KTDesignSystem.Button #chatNew` · `#chatSend` | `button.chat_btn` |
| `KTDesignSystem.Tag` | `span.chat_tag.chat_tag--warning` / `--positive` |
| `KTDesignSystem.Popup` | `#chatDocModal.chat_modal` — `.is_open` 으로 여닫기 |
| `.chat_cover` (서재) | `.chat_cover.chat_cover--book` |
| 표지 색 인라인 지정 | `.chat_cover[data-tone="guide\|ops\|policy"]` (없으면 흰 표지) |
| 주제 선택 상태 인라인 지정 | `.chat_topic.is_selected` + `aria-pressed` |
| 추론 펼침 상태 | `.chat_think.is_collapsed` · `.chat_think.is_streaming` + `aria-expanded` |
| 서재 접힘 (JS 폭 감지) | CSS `@media (max-width:1499px)` + `.chat_app.is_lib_open` |

## 템플릿 (`<template>`)
| id | 한 건 | 채울 `data-bind` |
| --- | --- | --- |
| `tpl_topic` | 주제 줄 `.chat_topic[data-category-id]` | `name` `qa_count` |
| `tpl_cover` | 서재 책 `.chat_shelf_slot` | `category` `no` `title` `chunk_count` · 속성 `data-doc-open` `data-tone` |
| `tpl_source` | 참고 자료 작은 표지 `.chat_cover--sm` | `category` `title` `chunk_count` · 속성 `data-doc-open` `data-tone` |
| `tpl_suggest` | 첫 화면 질문 카드 `.chat_suggest_card[data-question]` | `text` `topic` |
| `tpl_msg_user` | 사용자 메시지 | `text` |
| `tpl_msg_bot` | 봇 메시지 (추론·배지·답변·참고 자료·꼬리말) | `think_label` `think_sec` `think` `wait` `foot` `copy_label` |
| `tpl_doc_section` | 원문 모달의 절 한 줄 | `no` `title` |

고정 자리의 `data-bind`: `shelf_title` `shelf_count`(#chatShelf) · `doc_total` `qa_total`(#chatWelcome) · `topic_name`(#chatTopicPill) · `hint`(#chatHint) · `note`(#chatNote) · `title` `meta`(#chatDocModal)

`[data-doc-category]` 는 분류 문자열 자리입니다. 서버가 `docs[].category` 를 주면 채우고, 표지 색은 `chat.js` 의 `TONE_BY_CATEGORY` 로 고릅니다.

## 서버 연결 자리 (`chat.js`)
| 함수 | 지금 | 바꿀 것 |
| --- | --- | --- |
| `loadLibrary()` | 더미 `DUMMY_LIBRARY` | `GET /api/library` |
| `loadModels()` | 더미 `DUMMY_MODELS` | `GET /api/models` — 실패(reject) 시 AI 스위치 비활성 |
| `openStream(req, handlers)` | 타이머로 더미 이벤트 | `EventSource` — `handlers.thinking/answer/sources/done/error` 에 그대로 연결, `close()` 반환 |
| `md()` | 더미용 간이 렌더 | 서버/기존 마크다운 렌더로 교체 (커서는 `withCursor()` 로 끝에 붙임) |

미리보기 전환: `chat.html?llm=single` · `?llm=down` · `?project=single` · `?speed=2`

## SSE → 화면
- `thinking` → `.chat_think_body [data-bind=think]` 에 이어 붙임 (`.is_streaming` 동안 커서)
- `answer` 첫 이벤트 → 추론 블록 접고(`.is_collapsed`) 경과 시간 고정, 이후 `.chat_md` 에 이어 붙임 + 끝에 `.chat_cursor`
- `sources` → 보관만, `done` 에서 `.chat_sources` 표시
- `done` → 커서 제거, 꼬리말 `모델 · N초 · 검수 전`
- 중단 → 지금까지 나온 글자 유지, 참고 자료 없음, 꼬리말에 `중단됨`

## 상태 규칙
- AI 답변 끔 → `#chatDepWrap.is_disabled`, 모델·추론 `disabled`, 덮개 `[data-blocker=dep]` 클릭 시 `#chatHint` 3초
- `/api/models` 실패 → `#chatAiMode` disabled, `[data-blocker=ai]` 클릭 시 `지금은 AI 답변을 쓸 수 없습니다`
- 모델 1개 → `#chatModelWrap` 숨기고 `#chatModelName` 표시
- 프로젝트 1개 → `#chatProjectWrap` 숨기고 `#chatProjectName` 표시
- 검수 배지: `data-mode="ai"` → `.chat_badge_ai` + `.chat_meta_ai` / `"verified"` → `.chat_badge_verified` + `.chat_meta_verified`. 한 메시지에 둘이 같이 나오지 않습니다
- 폭 < 1,500px → 서재 접힘, `#chatLibToggle` 로 덮개 형태로 열림 (`.chat_app.is_lib_open`)

## 남은 인라인 스타일
마크업에는 없습니다. `chat.js` 가 런타임에 `#chatInput` 높이(자동 늘어남)만 `style.height` 로 지정합니다.
