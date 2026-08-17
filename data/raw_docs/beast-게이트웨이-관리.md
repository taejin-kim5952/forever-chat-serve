---
title: BEAST 게이트웨이 관리
category: 게이트웨이 > BEAST
url: /apidev/beast/apigwmng/bstAdmApiDplyList
related: [api-배포-신청과-승인, apigw-연동-구조, 배포-상태코드와-이력]
updated: 2026-08-15
---

# BEAST 게이트웨이 관리

BEAST는 API가 실제로 지나가는 게이트웨이입니다. 포털은 BEAST의 관리 API를 호출해
시스템·서비스·API 배포 현황을 조회하고, 신규 배포를 밀어 넣습니다.

## 화면 주소

| 화면 | URL | 내용 |
|---|---|---|
| API 배포 현황 | `/apidev/beast/apigwmng/bstAdmApiDplyList` | 게이트웨이에 올라간 API 목록 |
| 서비스 배포 현황 | `/apidev/beast/apigwmng/bstAdmSvcDplyList` | 서비스 단위 배포 현황 |
| 시스템 배포 현황 | `/apidev/beast/apigwmng/bstAdmSysDplyList` | 시스템 단위 배포 현황 |
| 연동 데이터 목록 | `/apidev/beast/apigwmng/bstAdmApiLinkDataList` | 포털-게이트웨이 동기화 데이터 |
| BEAST 배포 목록 | `/apidev/beast/deploy/mvDeployList.do` | BEAST 전용 배포 목록 |
| BEAST 배포 상세 | `/apidev/beast/deploy/mvDeployView.do` | 배포 1건 상세 |
| BEAST 검증 실행 | `/apidev/beast/deploy/mvVerifyExecute.do` | 검증 화면 |

화면 주소에 `{pathVal}` 형태가 들어가는 것들은 조회 대상(시스템/서비스/API)에 따라
경로 조각이 달라지는 공통 화면입니다. `/tb` 가 붙으면 검증계 대상입니다.

## 게이트웨이 환경 구분

BEAST는 검증계(TB)와 운영(PRD) 두 벌이 있습니다. 포털 화면에서도 조회 대상 환경을
고르게 되어 있고, API 정의에도 환경별 시스템 ID를 따로 적습니다.

| 필드 | 의미 |
|---|---|
| `bstgwYn` | 이 API가 BEAST 게이트웨이를 쓰는지 여부 |
| `bstgwTbSysId` | 검증계 BEAST 시스템 ID |
| `bstgwPrdSysId` | 운영 BEAST 시스템 ID |
| `apiVeriBaseurl` | 검증 호출에 쓸 기본 URL |

## 동기화 데이터

포털 DB와 BEAST가 각각 정보를 갖고 있어서, 둘이 어긋나면 화면과 실제 동작이
달라집니다. 그래서 동기화 조회 화면이 따로 있습니다.

- **시스템 동기화** — 게이트웨이에 등록된 시스템과 포털의 시스템 목록 비교
- **서비스 동기화** — 서비스(그룹) 단위 배포 상태 비교
- **API 동기화** — API 단위 배포 상태 비교
- **연동 데이터** — IP 접근 권한, SLA 설정 같은 부가 정보

동기화 화면에서 "포털에는 있는데 게이트웨이에 없음" 같은 항목이 보이면 재배포가
필요하다는 뜻입니다.

## 부가 설정 항목

BEAST 서비스 배포 정보에는 다음이 포함됩니다.

| 항목 | 설명 |
|---|---|
| IP 접근 권한 | 호출을 허용할 IP 대역 목록 |
| SLA | 유량 제한(초당/일일 호출 수 등) |
| 속성(Attribute) | 서비스별 부가 속성 |
| 핸들러 옵션 | 요청/응답 변환 세부 설정 |

## 엑셀 내보내기

BEAST 관리 화면에는 목록을 엑셀로 내려받는 기능이 붙어 있습니다. 배포 현황을
보고용으로 정리할 때 씁니다.

## 자주 묻는 질문

**Q. 포털에서는 배포 완료인데 게이트웨이 목록에는 없습니다.**
A. 배포 요청은 성공했지만 게이트웨이 반영이 실패한 경우입니다. 동기화 조회 화면에서
차이를 확인하고, LAMP 로그로 실제 응답을 본 뒤 재배포하세요.

**Q. TB에는 올라갔는데 운영에는 없습니다.**
A. 정상입니다. TB와 운영은 별개 배포입니다. 운영 배포를 따로 실행해야 합니다.

**Q. IP 제한 때문에 호출이 막힙니다.**
A. 서비스 배포 정보의 IP 접근 권한 목록에 호출자 IP가 들어 있는지 확인하세요.
사무실 IP가 바뀌었거나 신규 서버가 추가된 경우 자주 발생합니다.

**Q. BEAST와 APIGW는 다른 건가요?**
A. 포털은 두 가지 게이트웨이 연동 코드를 가지고 있습니다. `apigw` 패키지는 범용
게이트웨이 연동, `beast` 패키지는 BEAST 전용 연동입니다. API 정의에서 어느 쪽을
쓸지 지정합니다.

**Q. 유량 제한(SLA)은 누가 정하나요?**
A. 서비스 담당자와 게이트웨이 운영자가 협의해 정합니다. 포털 화면에서는 현재 설정된
값을 조회할 수 있습니다.
