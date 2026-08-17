---
title: 외부 시스템 연동 REST API
category: 연동 > 외부 REST
url: /apidev/api.json
related: [apigw-연동-구조, 시스템-아키텍처, 공통코드-체계]
updated: 2026-08-15
---

# 외부 시스템 연동 REST API

포털은 화면 외에 **타 시스템이 호출하는 REST 엔드포인트**를 제공합니다. 주소가
`.json` 으로 끝나는 것들이 여기에 해당합니다.

## 엔드포인트 목록

| 경로 | 메서드 | 하는 일 |
|---|---|---|
| `/apidev/api.json` | GET | API 정보 조회 |
| `/apidev/api.json` | POST | API 등록 |
| `/apidev/api.json` | PUT | API 수정 |
| `/apidev/api.json` | DELETE | API 취소/삭제 |
| `/apidev/apipost.json` | GET | API 등록 상태 조회 |
| `/apidev/apiput.json` | GET | API 수정 상태 조회 |
| `/apidev/delapi.json` | GET | API 삭제 상태 조회 |
| `/apidev/mbr.json` | GET | 회원 정보 조회 |
| `/apidev/mbr.json` | POST | 회원 인증 처리 |
| `/apidev/rest/authTest.do` | - | 인증 연동 테스트 |

이들 경로는 세션 체크 예외 목록에 들어 있습니다. 대신 **인증 키 헤더**로 호출자를
확인합니다. 인증 키는 환경 설정(`rest.authorization`)으로 관리되며 환경변수로
주입됩니다.

## 응답 구조

응답은 헤더부와 본문부로 나뉘는 공통 구조를 씁니다.

```
{
  "header": {
    "resultCode": "...",
    "resultMessage": "..."
  },
  "body": {
    "data": [ ... ]
  }
}
```

성공 여부는 헤더의 결과 코드로 판단합니다. HTTP 상태가 200이어도 헤더 결과 코드가
실패일 수 있으니, 상태 코드만 보고 판단하면 안 됩니다.

## SHUB 연동

사내 SHUB 플랫폼과도 연동합니다.

| 대상 | 용도 |
|---|---|
| 인스턴스 인증 API | 검증계·운영 각각 다른 주소 |
| 2FA 인증 발송/검증 | 메시징 게이트웨이 경유 |
| SHUB 로그인 대행 | 로컬 개발용 대리 엔드포인트 |

## Arsenal / GitLab 연동

사내 Arsenal 저장소 및 GitLab과 연동해 API 스펙을 주고받는 기능이 있습니다.

| 기능 | 경로 |
|---|---|
| API 이력 조회 | `/apidev/api/arsenal/selApiHistoryAjax.do` |
| GitLab 네임스페이스 확인 | `/apidev/api/reg/existsNSAtGitlabAjax.do` |

Arsenal 관련 코드 상당 부분은 현재 주석 처리되어 있고, 활성화된 것은 이력 조회
중심입니다. GitLab 토큰이 설정에 비어 있으면 연동 버튼이 동작하지 않습니다.

## 메일 발송 연동

배포 신청·승인·반려 알림은 사내 메일 발송 API를 통해 나갑니다. 발송 키가 설정되어
있어야 하며, 수신자 목록도 설정으로 관리됩니다.

## 자주 묻는 질문

**Q. `.json` 엔드포인트를 호출했더니 HTML이 옵니다.**
A. 인증에 실패해 로그인 화면으로 리다이렉트된 경우입니다. 인증 키 헤더를 확인하세요.

**Q. 같은 경로에 GET/POST/PUT/DELETE가 다 있습니다.**
A. REST 스타일로 메서드에 따라 동작이 갈립니다. 경로가 아니라 메서드로 구분하세요.

**Q. 응답이 200인데 처리가 안 됐습니다.**
A. 헤더의 결과 코드를 확인하세요. 업무 실패는 HTTP 200 + 실패 코드로 옵니다.

**Q. 연동 키는 어디서 받나요?**
A. 운영 담당자에게 요청합니다. 키는 환경별로 다르며 코드에 하드코딩하지 않습니다.

**Q. 호출 제한이 있나요?**
A. 게이트웨이를 경유하는 호출에는 SLA(유량 제한)가 걸릴 수 있습니다. 대량 호출
계획이 있으면 미리 협의하세요.
