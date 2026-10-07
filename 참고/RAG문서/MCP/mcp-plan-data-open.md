---
title: 데이터 모델 변경과 협의 필요 사항
category: MCP Manager 개발계획 > 데이터 · 협의
source_files: [MCP Manager 기술 개발계획서.pdf]
updated: 2026-10-07
---

# 데이터 모델 변경과 협의 필요 사항

데이터 모델은 Hub 연동 컬럼과 연동 이력 테이블만 바뀝니다. 이 문서는 그 변경과, 구현 전에
KT·Hub 팀과 확정해야 할 항목을 다룹니다.

## 테이블 변경

질문: 테이블이 어떻게 바뀌나요 / 어떤 컬럼이 추가되나요 / 새로 생기는 테이블 / 데이터 모델 변경

| 테이블 | 변경 | 주요 컬럼 |
| --- | --- | --- |
| mcp_server | 컬럼 추가 | hub_server_id, prefix, hub_auth_type, is_internal, hub_category |
| domain | 컬럼 추가 | default_hub_category |
| hub_sync_queue | registry_sync_queue 대체 | version_id, 작업 유형, 진행 단계(서버/Tool), 재시도 횟수, 오류 |
| hub_sync_log | registry_sync_log 대체 | 요청·응답 요약, 결과, 소요 시간 |
| hub_recon_result | **신규** | 대사 시각, 불일치 항목, 처리 여부 |
| system_config | 키 추가 | Hub 주소, 서비스 자격 참조, 대사 주기, 테스트 키 참조 |

user · namespace · mcp_server_version · mcp_tool · test_case 등 나머지는 요구사항정의서
v0.1 그대로 유지합니다.

## 비밀 값을 DB 에 두지 않는 이유

질문: 서비스 자격은 어디에 저장되나요 / 테스트 키는 DB 에 들어가나요 / 비밀 저장소

서비스 자격과 테스트 키는 **값이 아니라 비밀 저장소의 참조만** DB 에 둡니다. 컬럼과 제약은
상세 설계에서 확정합니다.

## 협의가 필요한 항목 — 우선순위 상

질문: 확정 안 된 것이 뭔가요 / 먼저 정해야 할 것 / KT 와 협의할 항목 / 승인 창구

구현 전에 KT·Hub 팀과 확정할 항목은 모두 여덟 가지이며, 그중 셋이 우선순위 '상' 입니다.

| 협의 항목 | 필요한 이유 |
| --- | --- |
| Manager → Hub 서비스 인증 방식 | Hub 관리 API 는 JWT 와 API Key 중 한 모드로 동작 |
| Hub Phase 2 등록/승인 워크플로우와의 범위 | 승인 창구가 둘이 되지 않도록 Manager 로 일원화 |
| Manager 가 등록한 서버의 Hub 직접 수정 금지 | 대사 불일치와 변경 이력 누락 방지 |

## 협의가 필요한 항목 — 우선순위 중

질문: 나머지 협의 항목 / INACTIVE 재활성화 / Domain 과 category 매핑 / 개발 환경에서 Hub 접근

| 협의 항목 | 필요한 이유 |
| --- | --- |
| INACTIVE 서버 재활성화 방법 | 비공개 후 재게시 처리 |
| 미등록 Tool 호출 시 Hub·Portal 동작 | Tool 사용 여부 제어의 실효성 |
| Domain 과 Hub category 매핑 | Hub 분류는 8종 고정 |
| 개발·검증 환경의 Hub 접근 경로 | 관리 API 가 클러스터 내부 주소로 안내되어 있음 |
| API_KEY 서버의 테스트 키 발급 | Test Suite 실행 |

미등록 Tool 과 관련해, Agent Builder 목록은 서버를 실시간 조회해 **미사용 Tool 도 보일 수
있습니다.**
