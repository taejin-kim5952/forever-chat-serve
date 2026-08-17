---
title: API 검증(Verify)과 테스트케이스
category: 배포 > 검증
url: /apidev/api/deploy/mvVerifyExecute.do
related: [api-배포-신청과-승인, 배포-상태코드와-이력, api-정의-등록화면]
updated: 2026-08-15
---

# API 검증(Verify)과 테스트케이스

배포 전에 API가 실제로 동작하는지 확인하는 단계입니다. **테스트케이스를 등록하고 →
검증을 실행하고 → 결과를 확인**하는 순서로 진행합니다. 검증을 통과하지 못한 API는
배포 신청 목록에 올라오지 않습니다.

## 화면 주소

| 기능 | URL |
|---|---|
| 검증 실행 화면 | `/apidev/api/deploy/mvVerifyExecute.do` |
| 검증 등록 | `/apidev/api/deploy/mvVerifiInsert.do` |
| 검증 시작 | `/apidev/api/deploy/mvVerifiStart.do` |
| 검증 시작(비동기) | `/apidev/api/deploy/verifyStartAjax.do` |
| 검증 결과 조회 | `/apidev/api/deploy/mvVerifiResltAjax.do` |
| 검증 결과 갱신 | `/apidev/api/deploy/updateVerifiAjax.do` |
| 테스트케이스 목록 | `/apidev/api/deploy/mvTescCaseListAjax.do` |
| 테스트케이스 등록 | `/apidev/api/deploy/testCaseInser.do` |

개발자 도구(Vue) 쪽에도 같은 기능을 다루는 REST가 있습니다.

| 기능 | URL |
|---|---|
| 테스트케이스 조회 | `/apidev/adptran_api/{버전}/apiTestCase/{testcaseId}` (GET) |
| 테스트케이스 저장 | `/apidev/adptran_api/{버전}/apiTestCase` (POST) |
| 테스트케이스 목록 | `/apidev/adptran_api/{버전}/apiTestCaseList/{apiNo}` (GET) |
| 검증 결과 조회 | `/apidev/adptran_api/{버전}/apiVerify/{vefify_seq}` (GET) |
| 검증 결과 저장 | `/apidev/adptran_api/{버전}/apiVerify` (POST) |
| 파라미터 테스트 | `/apidev/adptran_api/{버전}/apiParamTest/{apiNo}` (GET/POST) |

## 테스트케이스 구성

테스트케이스 한 건에는 다음이 들어갑니다.

| 항목 | 설명 |
|---|---|
| 케이스 이름 | 무엇을 검증하는지 알 수 있는 이름 |
| 요청 파라미터 값 | request 트리 각 항목에 넣을 실제 값 |
| 헤더 값 | 인증 토큰 등 |
| 기대 결과 | 성공 판정 기준(결과코드 등) |
| 비고 | 특이사항 |

기대 결과는 API 정의에 적어 둔 **응답 코드 필드(`resmapResCdField`)와 성공 값
(`resmapSuccVal`)** 을 기준으로 판정합니다. 예를 들어 응답의 `returncode` 가 `0000`
이면 성공으로 본다고 정의해 두었다면, 검증은 그 값이 나왔는지를 확인합니다.

## 검증 실행

검증 실행 화면에서 대상 API와 테스트케이스를 고르고 실행하면, 서버가 검증계(TB)
엔드포인트로 실제 호출을 보냅니다. 진행 상황은 화면에서 주기적으로 갱신되며 결과는
케이스별 성공/실패로 표시됩니다.

검증 결과는 다음 값으로 집계됩니다.

| 지표 | 필드 | 설명 |
|---|---|---|
| 전체 케이스 수 | `verifiCnt` | 실행한 케이스 개수 |
| TB 성공 건수 | `tbSuccessCnt` | 성공한 케이스 |
| 필수 항목 수 | `requiredCnt` | 필수 파라미터 개수 |
| 오류 메시지 | `errorMsg` | 실패 시 원인 |

## 검증 이력

과거 검증 결과는 검증 이력 팝업(`popVerifiHst`)에서 볼 수 있습니다. 언제, 누가,
어떤 케이스로 실행했고 성공/실패가 어땠는지가 회차별로 남습니다. 같은 API를 여러 번
검증하면 최신 결과가 배포 신청 판정에 쓰이고, 과거 결과는 이력으로만 남습니다.

## 실패했을 때 볼 곳

1. **오류 메시지** — 결과 표의 오류 메시지 칼럼. 대부분 여기서 원인이 드러납니다.
2. **LAMP 로그** — 게이트웨이로 실제 나간 요청/응답 원문. 파라미터가 빠졌는지,
   백엔드가 무엇을 돌려줬는지 확인할 수 있습니다.
3. **엔드포인트 설정** — TB URL이 잘못되었거나 타임아웃이 너무 짧은 경우가 흔합니다.

## 자주 묻는 질문

**Q. 검증을 꼭 해야 하나요?**
A. 네. 검증을 실행하지 않은 API는 배포 신청 대상 목록에 나오지 않습니다.

**Q. 검증이 계속 타임아웃입니다.**
A. API 정의의 엔드포인트 타임아웃 값을 확인하세요. 백엔드 응답이 느린 API는 값을
늘려야 합니다. 백엔드가 검증계에서 아직 안 떠 있는 경우도 흔합니다.

**Q. 성공했는데 실패로 표시됩니다.**
A. 성공 판정 기준이 실제 응답과 다른 경우입니다. API 정의의 응답 코드 필드명과 성공
값을 백엔드 실제 응답과 맞춰 주세요. 예를 들어 백엔드가 `resultCode` 를 쓰는데
정의에는 `returncode` 로 적혀 있으면 항상 실패로 판정됩니다.

**Q. 테스트케이스를 여러 개 만들어야 하나요?**
A. 최소 한 건이면 검증은 돌아갑니다. 다만 필수 파라미터 누락, 오류 응답 같은 경우를
같이 확인하려면 정상 케이스와 예외 케이스를 나눠 만드는 편이 좋습니다.

**Q. 검증 결과를 수정할 수 있나요?**
A. 결과 자체는 실행 기록이라 임의로 바꾸지 않습니다. 잘못된 케이스로 실행했다면
케이스를 고치고 다시 실행하세요.
