---
title: Hub 입력 항목과 이름 규칙 · 대사와 점검
category: MCP Manager 개발계획 > Hub 연동
source_files: [MCP Manager 기술 개발계획서.pdf]
updated: 2026-10-07
---

# Hub 입력 항목과 이름 규칙 · 대사와 점검

Hub 에 보낼 값 가운데 `server.json` 에 없는 것이 네 가지 있습니다. 이 문서는 그 항목과 서버
이름 규칙, 그리고 등록한 뒤 어긋나지 않는지 어떻게 확인하는지를 다룹니다.

## server.json 에 없어 따로 입력받는 항목

질문: 등록할 때 뭘 더 입력해야 하나요 / prefix 가 뭔가요 / category 는 어떻게 정하나요 / 사내 서버 표시

| Hub 항목 | Manager 출처 | 규칙 |
| --- | --- | --- |
| name | prefix 에서 생성 | `{prefix}-mcp` 고정 |
| prefix | **신규 입력** | 소문자·숫자·하이픈, Hub 전체에서 유일, 최초 게시 후 변경 불가 |
| url · transportType | server.json `remotes[0]` | streamable-http 만 대상, `STREAMABLE_HTTP` 로 전달 |
| description | server.json description | 그대로 전달 |
| authType | **신규 입력** | `NONE`(기본) 또는 `API_KEY` |
| isInternal | **신규 입력** | 사내 서버 기본 `true` |
| category | **신규 입력**(Domain 기본값) | Hub 8종 코드, `GET /catalog/categories` 로 조회 |
| tools[] | 게시 Version 의 사용 Tool | name · description · inputSchema(JSON 문자열) |

## 서버 이름을 {prefix}-mcp 로 고정하는 이유

질문: 서버 이름 규칙이 뭔가요 / Tool 이름은 어떻게 만들어지나요 / 왜 -mcp 를 붙이나요

Hub 에서 Tool 이름이 세 곳에 쓰이는데 형식이 조금씩 다릅니다. 서버 이름을 `{prefix}-mcp` 로
고정하면 세 형식이 모두 일치합니다.

| 쓰이는 곳 | Hub 문서의 형식 | name = {prefix}-mcp 일 때 |
| --- | --- | --- |
| Agent 용 카탈로그 (mcpToolName) | `{serverName}_{toolName}` | `{prefix}-mcp_{toolName}` |
| Tool 단위 인가 | `{serviceName}_{toolName}` | `{prefix}-mcp_{toolName}` |
| Portal 인가 동기화 | `{prefix}-mcp_{name}` | `{prefix}-mcp_{toolName}` |

Tool 단위 인가의 `serviceName` 이 서버 이름과 같다는 것은 Hub 문서를 해석한 것이므로 Hub
코드로 확인이 필요합니다.

## prefix 를 정하는 법

질문: prefix 는 어떻게 정하나요 / prefix 중복 검사 / prefix 를 나중에 바꿀 수 있나요 / 예시

Namespace 와 Server 이름으로 기본값을 제안하고, **Manager DB 와 Hub 서버 목록 양쪽에서**
중복을 검사합니다. 경로와 인가 식별자에 쓰이므로 **최초 게시 후에는 바꾸지 않습니다.**

예시로 Namespace 가 `com.kt.customer` 이고 prefix 가 `customer-product` 이면 서버 이름은
`customer-product-mcp` 가 되고, Tool 이름은 `customer-product-mcp_get_customer_products`
형태가 됩니다.

## Hub 대사 — 기록이 Hub 와 같은가

질문: 대사가 뭔가요 / Hub 와 다르면 어떻게 아나요 / Hub 에서 직접 바꾸면 / 외부 서버도 대사하나요

주기 배치로 **Manager 기록과 Hub 등록 내용이 같은지** 비교합니다.

- 대상은 Manager 가 등록한 서버(`serverId` 보유)입니다.
- URL·설명·상태와 Tool 목록을 비교합니다.
- 불일치를 리포트하며, Hub 에서 직접 바뀐 경우도 잡힙니다.
- **Hub 에만 있는 외부 서버는 대상이 아닙니다.**
- 수동 대사와 이력 조회를 제공합니다.

## 게시 Server 상태 점검 — 실제로 도는가

질문: 서버가 살아 있는지 어떻게 확인하나요 / 상태 점검은 뭘 하나요 / 점검하면 상태가 바뀌나요

주기 배치로 **게시된 서버가 실제로 동작하는지** 확인합니다.

- 대상은 게시 중인 서버의 endpoint 입니다.
- `initialize` · `tools/list` 로 연결과 명세 일치를 확인합니다.
- 결과는 대시보드와 Server 상세에 표시합니다.
- **상태 전환은 하지 않습니다.**

Hub 는 NONE·API_KEY 서버를 점검하지 않으므로, 이것이 사내 서버의 유일한 점검입니다.
