---
title: 전제와 범위 — Manager 와 Hub 의 역할
category: MCP Manager 개발계획 > 전제
source_files: [MCP Manager 기술 개발계획서.pdf]
updated: 2026-10-07
---

# 전제와 범위 — Manager 와 Hub 의 역할

이 계획서는 **MCP Hub 직접 연동**을 기준으로 씁니다. Manager 가 검증·승인한 MCP Server 만
Hub API 로 등록하고, AI Agent 는 Hub 를 통해 그 Tool 을 호출합니다.

## 이 계획서가 다루는 것과 다루지 않는 것

질문: 이 계획서 범위가 뭔가요 / 일정도 들어 있나요 / Registry 는 안 쓰나요 / 무엇을 전제로 썼나요

세 가지를 전제로 합니다.

- **Registry 미경유** — 게시를 승인하면 Manager 가 Hub 의 서버 등록·Tool 등록 API 를 직접
  호출합니다. 나중에 Registry 를 쓰게 되면 연동 어댑터만 교체합니다.
- **기술 범위만** — 공수와 일정은 다루지 않습니다. 구성·인터페이스·데이터·검증·권한 방식만
  정리합니다.
- **확인 전 가정** — Hub 연동 방식은 KT 확인 전 가정입니다. 확인이 필요한 항목은 따로
  모아 두었습니다.

기준 문서는 개발계획서 v1.10, 요구사항정의서 v0.1, MCP Hub 설계 v0.4 입니다.

## Manager 가 책임지는 것

질문: Manager 는 무엇을 하나요 / Manager 역할 / 검증은 누가 하나요 / 승인은 어디서 하나요

Manager 는 Hub 앞단에서 등록·검증·승인을 맡습니다.

- **명세 품질** — 형식 검증, 명세-실체 대조
- **Tool 호출 검증** — Inspector, Test Suite
- **소유권** — Domain·Namespace 담당 관계
- **게시 승인과 Version 이력**
- **사내 서버 상태 점검**

## Hub 가 책임지는 것

질문: Hub 는 무엇을 하나요 / Hub 역할 / 인증은 누가 하나요 / 토큰은 누가 보관하나요

Hub 는 호출을 중개합니다.

- **사용자 인증** — AX Works JWT 검증
- **서버·Tool 단위 인가** — Portal 에 위임
- **외부 서버 토큰 보관·갱신·주입**
- **가드레일** — 요청·응답 검사
- **Agent 용 Tool 카탈로그 제공**

## 사내 서버와 외부 SaaS 서버의 구분

질문: 외부 SaaS 서버도 Manager 를 거치나요 / 사내 서버와 외부 서버 차이 / OAuth 서버는 어떻게 되나요

사내 MCP Server 는 Manager 를 거치고, 외부 SaaS 서버는 Hub 에 직접 등록합니다.

| 구분 | Manager 경유 (본 과제) | Hub 직접 등록 (범위 외) |
| --- | --- | --- |
| 대상 서버 | KT 업무 API 를 감싼 사내 MCP Server | Atlassian · GitHub 등 외부 SaaS MCP Server |
| Hub 인증 방식 | NONE(기본), 필요 시 API_KEY | OAUTH |
| 등록 주체 | Server 개발자 등록 → 운영자 승인 | 플랫폼 관리자가 Hub API 로 등록 |
| 검증 | 형식 검증, 명세-실체 대조, Test Suite | Manager 관여 없음 |
| 상태 점검 | Manager 가 tools/list 를 주기 호출 | Hub 가 OAuth 메타데이터로 점검 |

OAuth 서버는 사용자 토큰 없이 Tool 을 호출할 수 없어 Manager 의 수집·테스트가 성립하지
않습니다. 그래서 관리 범위를 Hub 인증 방식으로 나눕니다.

## v1.10 에서 달라지는 것

질문: 이전 계획과 뭐가 다른가요 / v1.10 대비 변경 / 바뀌지 않는 것은 뭔가요

달라지는 것은 모두 **게시 대상이 Registry 에서 Hub 로 바뀐 데서** 나옵니다.

| 항목 | v1.10 | 본 계획 |
| --- | --- | --- |
| 게시 대상 | MCP Registry 등록 API | Hub 서버 등록 + Tool 등록 API |
| 동기화 (FP-MCP-10) | Registry-Catalog Sync | Hub 대사 (서버·Tool 목록 비교) |
| Tool 인가 | 범위 밖 | 게시 Version 의 사용 Tool 을 Hub 에 등록 |
| Version | Registry 표준 | Manager 규칙으로 유지, Hub 에는 서버당 1건만 반영 |
| 등록 입력 항목 | server.json · Domain · Namespace | + prefix · Hub 인증 방식 · 사내/사외 · Hub category |
| 상태 점검 | 대시보드 보조 기능 | 사내 서버의 유일한 점검 |

**4 POD 구성 · 기술 스택 · 검증 체계 · 역할·권한 · 화면 메뉴는 변경이 없습니다.**
