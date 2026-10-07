---
title: API 배포 신청과 승인
category: 배포 > 신청·승인
url: /apidev/api/deploy/mvDeployList.do
related: [api-검증과-테스트케이스, 배포-상태코드와-이력, beast-게이트웨이-관리]
updated: 2026-08-15
---

# API 배포 신청과 승인

등록·검증이 끝난 API를 실제 게이트웨이에 올리는 절차입니다. 배포는 **신청 → 승인 →
TB(검증계) 배포 → 운영(CB) 배포** 순서로 진행되고, 각 단계마다 이력이 남습니다.

## 화면 주소

| 화면 | URL |
|---|---|
| 배포 목록 | `/apidev/api/deploy/mvDeployList.do` |
| 배포 목록 데이터 | `/apidev/api/deploy/mvDeployListAjax.do` |
| 승인 목록(신규) | `/apidev/api/deploy/mvApprovalListN.do` |
| 승인 목록 데이터 | `/apidev/api/deploy/mvApprovalListAjax.do` |
| 배포 상세 | `/apidev/api/deploy/mvDeployView.do` |
| 배포 상세 처리 | `/apidev/api/deploy/mvDeployViewProcAjax.do` |
| 배포 신청 | `/apidev/api/deploy/mvDeployApply.do` |
| 신청 목록 | `/apidev/api/deploy/mvDeployApplyListAjax.do` |
| 신청서 인쇄 | `/apidev/api/deploy/mvDeployApplyPrintAjax.do` |
| 신청 삭제 | `/apidev/api/deploy/mvDeployApplyDel.do` |
| 반려 처리 | `/apidev/api/deploy/deployRejectAjax.do` |
| TB 배포 실행 | `/apidev/api/deploy/mvTbDeployProc.do` |
| 운영 배포 실행 | `/apidev/api/deploy/mvCbDeployProc.do` |
| 배포 이력 | `/apidev/api/deploy/mvDeployHstAjax.do` |
| TB 배포 이력 | `/apidev/api/deploy/mvTbDeployHstAjax.do` |
| 운영 배포 조회 | `/apidev/api/deploy/mvCbDeployViewAjax.do` |
| 신규 API 목록 | `/apidev/api/deploy/newApiListAjax.do` |
| 배포 상태 조회 | `/apidev/api/deploy/mvProcDeployStateAjax.do` |
| API 삭제 처리 | `/apidev/api/deploy/mvProcDelApi.do` |
| 버전 갱신 | `/apidev/api/deploy/apiVerNoUpdateAjax.do` |

## 배포 신청서 작성

신청 화면에서는 배포할 API를 목록에서 골라 담고, 신청 사유와 희망 일정을 적습니다.

| 항목 | 설명 |
|---|---|
| 신청 대상 API | 검증을 통과한 API만 목록에 나옵니다 |
| 배포 구분 | 신규 / 변경 / 삭제 |
| 대상 환경 | TB(검증계) 또는 운영 |
| 신청 사유 | 결재자가 읽는 설명 |
| 희망 일시 | 배포 예정 시각 |
| 비고 | 특이사항 |

신청서는 인쇄용 양식으로도 출력됩니다(`mvDeployApplyPrintAjax.do`). 결재 문서로
첨부해야 할 때 이 양식을 씁니다.

## 승인과 반려

승인 권한이 있는 계정에게는 승인 목록 화면이 열립니다. 목록에서 신청 건을 열고
내용을 확인한 뒤 **승인** 또는 **반려**를 누릅니다.

- **승인** — 다음 단계(배포 실행)로 넘어갑니다.
- **반려** — 사유를 반드시 입력해야 합니다. 반려되면 신청자에게 메일이 나가고,
  신청 건은 수정 후 재신청할 수 있는 상태로 되돌아갑니다.

반려 사유 없이 반려 버튼만 누르면 서버가 거부합니다.

## TB 배포와 운영 배포

- **TB 배포(`mvTbDeployProc.do`)** — 검증계 게이트웨이에 올립니다. 여기서 실제 호출
  테스트를 합니다.
- **운영 배포(`mvCbDeployProc.do`)** — 운영 게이트웨이에 올립니다. TB 배포와 검증이
  성공해야 버튼이 열립니다.

배포는 게이트웨이 API를 호출하는 비동기 작업입니다. 실행 직후 상태가 "배포 중"으로
바뀌고, 완료되면 "완료" 또는 "실패"로 갱신됩니다. 화면을 닫아도 작업은 계속 진행되며,
목록을 새로고침하면 최신 상태를 볼 수 있습니다.

## 배포 상태 흐름

게이트웨이 작업 상태는 다음 값을 가집니다.

| 코드 | 의미 |
|---|---|
| `STANDBY` | 대기 |
| `INIT` | 초기화 |
| `DEPLOYING` | 배포 중 |
| `ROLLING_BACK` | 롤백 중 |
| `DONE` | 완료 |
| `FAIL` | 실패 |

검증·작업 단위의 상태는 별도로 `STANDBY / DOING / DONE / FAILURE` 를 씁니다.

## 메일 알림

배포 신청·승인·반려 시 관련자에게 메일이 발송됩니다. 수신자 목록은 환경 설정의
`deployapply.mail.list` 값으로 관리되며, 신청자 본인은 항상 수신자에 포함됩니다.

## 자주 묻는 질문

**Q. 배포 신청 목록에 우리 API가 안 보입니다.**
A. 검증(Verify)을 한 번도 실행하지 않았거나 검증이 실패한 상태입니다. 검증을 먼저
통과시켜야 신청 대상 목록에 올라옵니다.

**Q. 승인이 났는데 운영 배포 버튼이 비활성입니다.**
A. 운영 배포는 TB 배포가 성공한 뒤에만 열립니다. TB 배포 이력에서 성공 여부를 먼저
확인하세요.

**Q. 배포가 "배포 중"에서 오래 멈춰 있습니다.**
A. 게이트웨이 응답을 기다리는 중입니다. LAMP 로그 팝업에서 실제로 나간 요청과 받은
응답을 확인할 수 있습니다. 응답 자체가 없으면 게이트웨이 쪽 장애일 수 있으니
운영자에게 문의하세요.

**Q. 잘못 신청했습니다. 취소할 수 있나요?**
A. 승인 전이면 신청 삭제(`mvDeployApplyDel.do`)로 지울 수 있습니다. 이미 배포가
시작되었다면 배포 취소 팝업을 통해 롤백을 요청해야 합니다.

**Q. 배포는 성공했는데 실제 호출이 404 입니다.**
A. 호스트·기본경로·Path 조합이 실제 게이트웨이 라우팅과 맞는지 확인하세요. 그룹의
기본경로를 바꾼 뒤 재배포하지 않으면 이런 상태가 됩니다.

**Q. 같은 API를 다시 배포해도 되나요?**
A. 됩니다. 변경 배포로 신청하면 게이트웨이에 있는 정의가 갱신됩니다. 이력에는 배포
회차가 모두 남습니다.
