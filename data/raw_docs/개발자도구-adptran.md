---
title: 개발자 도구(adptran) 화면
category: 개발 지원 > 개발자 도구
url: /apidev/adptran/devHome
related: [api-상태점검-모니터링, api-검증과-테스트케이스, apigw-연동-구조]
updated: 2026-08-15
---

# 개발자 도구(adptran) 화면

`/apidev/adptran` 아래 화면들은 다른 화면과 달리 **Vue 기반 단일 페이지 화면**입니다.
서버가 빈 껍데기 HTML만 내려주고, 그 위에 번들된 Vue 앱이 올라가 화면을 그립니다.
데이터는 전부 `/apidev/adptran_api/...` REST 호출로 주고받습니다.

## 화면 주소

| 화면 | URL | 내용 |
|---|---|---|
| 개발 홈 | `/apidev/adptran/devHome` | 도구 진입점 |
| 쿼리 도구 | `/apidev/adptran/devQuery` | 데이터 조회 도구 |

Vue 앱은 화면 종류에 따라 다른 번들을 올립니다.

| 번들 | 하는 일 |
|---|---|
| `adptranService` | 개발자 도구 메인 서비스 화면 |
| `apieditService` | API 편집 도구 |
| `devQuery` | 쿼리 도구 |
| `verifyExecute` | 검증 실행 화면 |
| `kosXlsxService` | KOS 엑셀 반입 도구 |
| `apistatus_list` / `apistatus_group` | API 상태 점검 목록·그룹 |

## 개발자 도구용 REST

Vue 화면이 호출하는 REST 엔드포인트는 `/apidev/adptran_api/{버전}` 아래에 모여
있습니다.

| 기능 | 메서드 · 경로 |
|---|---|
| API 조회 | GET `/api/{apiNo}` |
| API 저장 | POST `/api` |
| 파라미터 조회 | GET `/apiParam/{apiNo}` |
| 파라미터 저장 | POST `/apiParam` |
| 정의+규격 조회 | GET `/apiDefWithApiSpc/{apiNo}` |
| 정의+규격 저장 | POST `/apiDefWithApiSpc` |
| 파라미터 테스트 조회 | GET `/apiParamTest/{apiNo}` |
| 파라미터 테스트 실행 | POST `/apiParamTest` |
| 테스트케이스 조회/저장 | GET·POST `/apiTestCase` |
| 테스트케이스 목록 | GET `/apiTestCaseList/{apiNo}` |
| 테스트케이스 변환 | POST `/apiTestCaseTrans/{trans}` |
| 검증 조회/저장 | GET·POST `/apiVerify` |
| 게이트웨이 배포 | POST `/apigw_deploy` |
| 배포 상태 | POST `/apigw_deployStatus` |
| 배포 삭제 | POST `/apigw_deployDelete` |
| CP API 조회 | POST `/apigw_cpApiGet` |
| LAMP 로그 | POST `/apigw_LampLog` |

## 공통 참조 데이터 REST

화면에서 쓰는 코드·탭 데이터는 별도 REST(`/apidev/ref_adptran_api/{버전}`)로
관리됩니다.

| 기능 | 메서드 · 경로 |
|---|---|
| 탭 데이터 목록 | GET `/ref/tabdata_list` |
| 탭 데이터 조회 | GET `/ref/tabdata/{tabdata_seq}` |
| 탭 데이터 등록 | POST `/ref/tabdata` |
| 탭 데이터 수정 | PUT `/ref/tabdata/{tabdata_seq}` |
| 탭 데이터 삭제 | DELETE `/ref/tabdata/{tabdata_seq}` |
| 동적 조회 | POST `/ref/select_dynamic` |

## 화면에서 쓰는 팝업(다이얼로그)

Vue 화면은 자체 모달 다이얼로그를 씁니다.

- API 검색 다이얼로그
- 배포 다이얼로그
- 테스트케이스 등록/목록 다이얼로그
- 검증 결과 보기 다이얼로그
- LAMP 로그 보기 다이얼로그
- 엑셀 반입 다이얼로그
- 상태 점검 이력 목록/상세 다이얼로그
- 상태 점검 그룹 사용자 연결 다이얼로그

## KOS 엑셀 반입

KOS 규격서를 엑셀로 받아 파라미터를 자동 생성하는 도구가 들어 있습니다. 엑셀을
올리면 시트를 파싱해 request/response 트리를 만들고, 확인 후 저장합니다. 수백 개
항목을 손으로 넣지 않아도 되는 대신, 엑셀 양식이 정해진 형태와 다르면 파싱이
실패합니다.

## 세션 예외

개발자 도구 경로(`/adptran/*`, `/adptran_api/*`, `/apistatus_api/*`,
`/ref_adptran_api/*`)는 세션 체크 인터셉터의 예외 목록에 들어 있습니다. Vue 화면이
여러 REST를 연달아 호출하는 구조라 매 호출마다 세션 검사로 리다이렉트가 발생하면
화면이 깨지기 때문입니다.

## 자주 묻는 질문

**Q. 화면이 하얗게만 나옵니다.**
A. Vue 번들 스크립트가 로드되지 않은 경우입니다. 브라우저 캐시를 지우고 다시 열어
보세요. 그래도 같으면 정적 리소스 배포가 누락된 것일 수 있습니다.

**Q. 데이터가 안 보이는데 오류 메시지도 없습니다.**
A. REST 호출이 세션 만료로 리다이렉트된 경우 화면에는 아무것도 안 나올 수 있습니다.
개발자 도구 네트워크 탭에서 응답이 HTML(로그인 화면)로 오는지 확인하세요.

**Q. 일반 등록 화면과 개발자 도구 중 어느 걸 써야 하나요?**
A. 일반 업무는 일반 등록 화면으로 충분합니다. 개발자 도구는 파라미터가 매우 많거나
엑셀 반입, 반복 테스트가 필요할 때 씁니다.

**Q. 엑셀 반입이 실패합니다.**
A. 양식이 다르면 파싱이 실패합니다. 헤더 행 위치와 컬럼 이름을 표준 양식과 맞춘 뒤
다시 시도하세요.
