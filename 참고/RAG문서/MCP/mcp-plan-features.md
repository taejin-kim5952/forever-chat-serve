---
title: 기능 구현과 검증 · 권한 · 기술 스택
category: MCP Manager 개발계획 > 기능 구현
source_files: [MCP Manager 기술 개발계획서.pdf]
updated: 2026-10-07
---

# 기능 구현과 검증 · 권한 · 기술 스택

게시와 동기화 대상만 Hub 로 바뀌고 기능 구성은 그대로입니다. 이 문서는 기능 목록과 게시 전
검증 단계, 권한 방식, 쓰는 기술을 다룹니다.

## 기능별 구현 요점

질문: 기능이 뭐가 있나요 / FP-MCP 가 뭔가요 / v1.10 대비 기능 변경 / 동기화는 어떻게 바뀌나요

| 기능 | 구현 요점 | v1.10 대비 |
| --- | --- | --- |
| FP-MCP-01 Registry 관리 | server.json 등록·검증, Version 관리, Import/Export | Hub 연동 항목 입력 추가 |
| FP-MCP-02·03 Domain·Namespace | 관리 단위, 소유자·멤버 | Domain 별 기본 Hub category |
| FP-MCP-04 Tool 관리 | tools/list 수집, 사용 여부, 설명 보강 | 사용 Tool 이 Hub 인가 대상 |
| FP-MCP-05 Inspector/Test Suite | 형식 검증, 대조, Inspector, Test Suite | 변경 없음 |
| 게시 관리 | 상태 모델, 요청·승인·반려, 해제·폐기 | 승인 = Hub 등록 |
| FP-MCP-08 Dashboard | 현황, 상태 점검, 연동 결과 | Hub 연동 성공·실패 집계 |
| FP-MCP-09 운영관리 | 사용자·권한, 공통코드, 설정, 감사 로그 | Hub 연동 설정 추가 |
| FP-MCP-10 동기화 | Registry-Catalog Sync | **Hub 대사로 대체** |
| FP-MCP-11·12 Catalog | 게시 Server·Tool 조회 | Manager DB 기준 |

## 게시 전 검증 4단계

질문: 게시 전에 뭘 검증하나요 / 검증 단계가 몇 개인가요 / Test Suite 가 뭔가요 / 누가 최종 확인하나요

검증 4단계는 그대로이고, **형식 검증에 Hub 항목이 더해집니다.**

1. **형식 검증** — server.json 스키마와 필수값, Hub 항목(prefix 중복, category 코드)
2. **명세-실체 대조** — endpoint 연결, `tools/list` 응답과 등록 Tool·스키마 일치
3. **Test Suite** — Test Case 기반 `tools/call`, 기대값과 비교해 PASS/FAIL
4. **소유자 확인** — Namespace 소유자 이상이 결과를 확인하면 검증 완료

## 서버를 부르는 모듈과 테스트 인증

질문: MCP Server 를 어떻게 호출하나요 / SDK 가 뭔가요 / API_KEY 서버는 어떻게 테스트하나요

**MCP Java SDK 하나로** 명세 수집·대조·Inspector·Test Suite·상태 점검을 처리합니다. 어댑터로
감싸 SDK 교체에 대비합니다.

테스트 인증은 인증 방식에 따라 다릅니다. `NONE` 서버는 그대로 호출하고, `API_KEY` 서버는
시스템 설정의 **테스트 키**로 호출합니다. 키 발급 방식은 협의가 필요합니다.

## 사용자 인증과 역할

질문: 로그인은 어떻게 하나요 / 역할이 뭐가 있나요 / 권한 검사는 어디서 하나요

Manager 사용자는 **Entra ID SSO**(OIDC + PKCE)로 로그인하며 서버 세션 방식입니다.

역할은 **운영자 · Domain 소유자 · Namespace 소유자·멤버** 입니다. 모든 API 에서 역할과 담당
범위를 **서버가** 검사하고, 사용자 사이트와 관리자 사이트의 세션을 분리합니다.

## Manager 가 보관하지 않는 것

질문: 사용자 토큰은 누가 보관하나요 / API Key 는 어디에 저장되나요 / Manager 가 보관하는 키

사용자 개인의 API Key 와 OAuth 토큰은 **Hub 가 보관하며 Manager 는 관여하지 않습니다.**
Manager 는 테스트 키만 보관합니다.

Hub 설계 문서에 JWT 검증을 MS Entra ID 설정으로 맞출 예정이라는 언급이 있어, 같은 IdP 의
서비스 토큰으로 Hub 를 호출하는 방식을 우선 검토합니다.

## 기술 스택

질문: 어떤 기술을 쓰나요 / 백엔드 스택 / 프론트엔드 스택 / 오픈소스 라이선스

v1.10 과 같고 **Hub 연동 클라이언트만 추가**됩니다.

- **Backend** — JDK 21(LTS), Spring Boot 4.x · Spring Security, MyBatis,
  RestClient(Hub 관리 API 클라이언트 · 추가), Quartz + Spring Retry(재처리·대사·점검 배치)
- **Frontend** — Vue 3 + TypeScript, Vite · Pinia · Vue Router, Element Plus,
  Monaco Editor(스키마 편집), ECharts(대시보드)
- **MCP 특화·인프라** — MCP Java SDK, json-schema-validator, jsondiffpatch,
  PostgreSQL 또는 사내 표준 RDB, Entra ID(OIDC)

세부 버전과 사내 표준 적합성은 설계 단계에서 확정합니다. **오픈소스는 모두 MIT 또는
Apache 2.0 입니다.**
