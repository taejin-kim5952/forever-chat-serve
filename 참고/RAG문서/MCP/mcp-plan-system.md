---
title: 시스템 구성과 외부 연동 대상
category: MCP Manager 개발계획 > 시스템 구성
source_files: [MCP Manager 기술 개발계획서.pdf]
updated: 2026-10-07
---

# 시스템 구성과 외부 연동 대상

MCP Manager 는 Kubernetes 클러스터 위에서 4 POD 로 돌아갑니다. 이 문서는 그 구성과, 바깥의
어떤 시스템을 언제 부르는지를 다룹니다.

## 4 POD 구성

질문: 시스템이 어떻게 구성되나요 / POD 가 몇 개인가요 / 사용자와 관리자가 나뉘나요 / 구성도

Kubernetes 클러스터 안에서 Ingress 가 HTTPS 와 사용자·관리자 경로 라우팅을 맡고, 그 아래
네 개의 POD 가 있습니다.

| POD | 역할 | 기술 |
| --- | --- | --- |
| POD 1 | 사용자 Frontend | Vue 3 정적 자원 |
| POD 2 | 사용자 Backend | 등록·검증·Server 호출 |
| POD 3 | 관리자 Frontend | Vue 3 정적 자원 |
| POD 4 | 관리자 Backend | 승인·Hub 연동·배치 |

공통 DB 는 PostgreSQL 또는 사내 표준 RDB 입니다. **4 POD 구성은 v1.10 에서 바뀌지
않았고, 외부 연동 대상에 Hub 관리 API 가 새로 들어왔습니다.**

## 누가 어느 쪽을 쓰나

질문: Server 개발자는 뭘 하나요 / 운영자는 뭘 하나요 / 사용자 사이트와 관리자 사이트 차이

- **Server 개발자** — 등록·검증·게시를 요청합니다. 사용자 Frontend·Backend 를 씁니다.
- **운영자** — 게시를 승인하고 운영을 관리합니다. 관리자 Frontend·Backend 를 씁니다.

Hub 관리 API 는 **관리자 Backend 만** 호출합니다.

## 외부 연동 대상 세 곳

질문: 어떤 외부 시스템과 연동하나요 / 연동 대상이 뭔가요 / Entra ID 는 어디에 쓰나요

| 대상 | 쓰임 |
| --- | --- |
| MCP Hub 관리 API | 서버·Tool 등록·수정·삭제·조회 (신규) |
| MCP Server (N개) | `tools/list` · `tools/call` — 수집·검증·상태 점검 |
| Microsoft Entra ID | OIDC 기반 SSO |

## Hub 관리 API 를 언제 부르나

질문: Hub API 를 언제 호출하나요 / 어떤 API 를 쓰나요 / 게시하면 무엇이 호출되나요

| 인터페이스 | 호출 시점 |
| --- | --- |
| `POST /catalog/servers` | 최초 게시 승인 |
| `PUT /catalog/servers/{id}` | 새 Version 게시 |
| `DELETE /catalog/servers/{id}` | 비공개 · 폐기 |
| `PUT /catalog/admin/servers/{id}/tools` | 게시, 게시 중 Tool 사용 여부 변경 |
| `GET /catalog/servers` · `…/tools` · `/catalog/categories` | 대사, category 코드 조회 |

경로는 앞의 `/api/v1/mcp` 를 생략한 것입니다. 호출 모듈은 모두 관리자 Backend 입니다.

## MCP Server 와 Entra ID 호출 시점

질문: MCP Server 를 언제 부르나요 / tools/call 은 언제 쓰나요 / 로그인은 어떻게 하나요

| 대상 | 인터페이스 | 호출 시점 | 호출 모듈 |
| --- | --- | --- | --- |
| MCP Server | `initialize` · `tools/list` | 등록, 검증, 상태 점검 | 사용자·관리자 Backend |
| MCP Server | `tools/call` | Inspector, Test Suite | 사용자 Backend |
| Entra ID | OIDC Authorization Code + PKCE | 로그인 | 양 Backend |

## 연동을 어댑터로 분리하는 이유

질문: 어댑터가 뭔가요 / Registry 로 바뀌면 어떻게 하나요 / 나중에 연동 방식이 바뀌면

Hub 연동은 **어댑터로 분리**합니다. 나중에 Registry 경유로 바뀌면 어댑터만 교체하면 됩니다.
MCP Server 호출도 MCP Java SDK 를 어댑터로 감싸 SDK 교체에 대비합니다.
