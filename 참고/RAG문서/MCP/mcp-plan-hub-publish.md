---
title: Hub 연동 — 게시 승인 흐름과 상태 전환
category: MCP Manager 개발계획 > Hub 연동
source_files: [MCP Manager 기술 개발계획서.pdf]
updated: 2026-10-07
---

# Hub 연동 — 게시 승인 흐름과 상태 전환

게시를 승인하면 Manager 가 Hub 에 서버와 Tool 을 차례로 등록합니다. 이 문서는 그 순서와,
Manager 의 상태 변화가 Hub 에서 무엇으로 이어지는지를 다룹니다.

## 게시 승인 한 번에 일어나는 일

질문: 게시를 승인하면 어떤 일이 일어나나요 / Hub 등록 순서 / 승인하면 Hub 에 바로 올라가나요

운영자가 승인하면 일곱 단계가 이어집니다.

1. 운영자가 **게시 승인**
2. Manager 가 Hub 에 **서버 등록**(POST)
3. Hub 가 `201` 과 `serverId` 를 주고, Manager 는 **즉시 저장**
4. Manager 가 Hub 에 **Tool 목록 등록**(PUT)
5. Hub 가 AX Works Portal 에 **Tool 인가 대상 동기화**
6. Hub 가 `200` 과 등록 결과를 응답
7. Manager 가 **게시로 전환**하고 감사 로그를 남김

2번과 4번이 실패하면 게시 요청 상태를 유지하고 재처리 큐에 적재해, 남은 단계만 다시
실행합니다.

## Hub 에는 Version 이 없다

질문: Version 은 Hub 에 어떻게 반영되나요 / 이전 Version 은 어떻게 되나요 / Hub 에 몇 개가 올라가나요

Hub 에는 Version 개념이 없어 **서버마다 게시 Version 1건만** 반영됩니다. Version·Namespace·
Domain·Tool Tag 는 Hub 에 해당 항목이 없어 Manager 에만 보관합니다.

## 상태 전환과 Hub 호출

질문: 비공개하면 어떻게 되나요 / 폐기와 비공개 차이 / 새 Version 을 게시하면 / 재게시가 되나요

| Manager 상태 전환 | Hub 호출 | Hub 결과 |
| --- | --- | --- |
| 게시 요청 → 게시 (최초) | 서버 등록 POST, Tool 등록 PUT | 서버 ACTIVE, Tool 인가 대상 등록 |
| 게시 요청 → 게시 (새 Version) | 서버 수정 PUT, Tool 등록 PUT | 같은 serverId 의 URL·설명·Tool 교체 |
| 게시 → 비공개 | 서버 삭제 DELETE | INACTIVE (soft delete) |
| 게시 → 폐기 | 서버 삭제 DELETE | INACTIVE |
| 비공개 → 재게시 | **협의 필요** | INACTIVE 서버를 다시 활성화하는 방법이 Hub 문서에 없음 |
| 게시 중 Tool 사용 여부 변경 | Tool 등록 PUT (사용 Tool 전체) | Tool 인가 대상 교체 |
| 등록 · 검증 완료 · 반려 | 호출 없음 | Hub 와 Agent 에 노출되지 않음 |

새 Version 을 게시하면 이전 Version 은 Manager 에서 비공개가 됩니다. 폐기한 서버의 재게시
금지는 Manager 가 관리합니다.

## Hub 호출 자격

질문: Hub 를 누가 호출하나요 / 서비스 계정이 뭔가요 / 인증 방식은 정해졌나요

Hub 관리 API 는 **관리자 Backend 만 서비스 계정 자격으로** 호출합니다. Hub 는 JWT 와
API Key 중 한 모드로만 동작하므로 방식은 협의가 필요합니다.

서비스 계정 자격은 비밀 저장소에 두고 화면에 노출하지 않습니다.

## 멱등 처리와 부분 실패

질문: 같은 서버를 두 번 등록하면 / 이름 중복이 나면 / Tool 등록만 실패하면 어떻게 되나요

- **멱등 처리** — 서버 등록이 성공하면 `serverId` 를 바로 저장하고, 이후 같은 서버는
  수정(PUT)으로 호출합니다. 이름 중복 응답이면 목록을 조회해 `serverId` 를 찾아 연결합니다.
- **부분 실패** — 서버 등록은 됐는데 Tool 등록이 실패하면 **게시로 전환하지 않습니다.**
  재처리 큐에 진행 단계를 기록해 남은 단계만 다시 실행합니다.

## 재시도 규칙

질문: 실패하면 몇 번 다시 시도하나요 / 4xx 오류는 어떻게 되나요 / 재처리는 어떻게 도나요

즉시 재시도(Spring Retry)와 재처리 배치(Quartz)를 함께 씁니다. **5xx 와 타임아웃만
재시도하고, 4xx 는 운영자 확인 대상으로 넘깁니다.** 횟수는 시스템 설정입니다.
