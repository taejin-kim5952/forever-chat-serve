---
title: API Manager 개요와 시스템 구성
category: API Manager 설계 > 개요
source_files: [KT_API_Manager_Plan2.pdf]
updated: 2026-10-07
---

# API Manager 개요와 시스템 구성

KT API Manager 는 API 를 등록하고 배포·테스트하는 통합 관리 시스템입니다. 이 문서는 왜 이
시스템을 만드는지와, 어떤 요소들이 서로 연결되어 있는지를 다룹니다.

## 통합 API 관리 시스템이 필요한 이유

질문: API Manager 를 왜 만드나요 / 도입 배경이 뭔가요 / 통합 관리가 왜 필요한가요 / 목표가 뭔가요

세 가지를 목표로 합니다.

- **라이프사이클 중앙화** — API 를 만드는 것부터 폐기까지 전 과정을 한곳에서 관리합니다.
- **보안·안정성 확보** — 강력한 보안 정책과 장애 격리로 서비스 안정성을 확보합니다.
- **셀프 서비스 포털** — 내부 개발자와 외부 파트너사가 직접 등록·배포·테스트를 합니다.

## 시스템 구성도

질문: 시스템이 어떻게 구성되나요 / 구성도 설명해주세요 / 어떤 시스템이 연결되나요 / 전체 구조

웹과 WAS 를 중심에 두고, 인증은 Entra ID 가, 배포는 BEAST 게이트웨이가 맡습니다.

| 구성 요소 | 하는 일 |
| --- | --- |
| Microsoft Entra ID | SSO 인증 |
| API Manager (Web) | API 그룹 · 운영 배포 관리 · MY PAGE 화면 |
| API Manager (WAS) | 화면 API · 업무 처리 · 전문 생성 · 연동 |
| DB | 엔티티 보관 |
| BEAST 게이트웨이 | API 배포 |
| TB · 운영 시스템 | 호출 로그 |

사용자는 등록자와 승인자로 나뉘어 이 화면들을 씁니다.

## 연동 대상 네 가지

질문: 어떤 시스템과 연동하나요 / 연동 대상이 뭔가요 / BEAST 는 뭔가요 / 외부 시스템 연결

API Manager 는 네 곳과 연동합니다.

1. **Microsoft Entra ID** — 로그인, 직원 확인, 권한
2. **BEAST 게이트웨이** — 배포 요청, 등록 조회, 롤백
3. **TB 시스템** — 테스트 요청, 응답, 검증
4. **운영 시스템** — 운영 배포 결과 확인

## 배포 대상 게이트웨이

질문: 게이트웨이가 몇 개인가요 / TB 와 운영 게이트웨이 주소 / 어디로 배포되나요 / BEAST 서버 목록

TB 와 운영에 각각 두 대씩, 모두 네 대입니다.

| 구분 | 게이트웨이 | 주소 |
| --- | --- | --- |
| TB_KTC | BEAST-TB-01 | tb-gw01.kt.com |
| TB_AZURE | BEAST-TB-02 | tb-gw02.kt.com |
| PRD_KTC | BEAST-PRD-01 | gw01.kt.com |
| PRD_AZURE | BEAST-PRD-02 | gw02.kt.com |

## Handler 일곱 가지

질문: Handler 가 뭔가요 / Handler 종류 / Handler 를 바꾸면 어떻게 되나요 / 전문 처리 방식

배포 전문을 처리하는 Handler 는 일곱 가지입니다.

`COMMON` · `ANYCOMMON` · `KOS` · `KOSMOS` · `SCAP` · `CAPRI` · `SB`

**Handler 를 바꾸면 설정 항목 연동도 함께 바뀝니다.** 요청과 응답에 각각 Handler 를 지정하며,
배포 전문의 `reqHndlr` · `resHndlr` 필드로 전달됩니다.
