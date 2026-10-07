---
title: 내 API 관리와 버전
category: API 관리 > API 관리 화면
url: /apidev/api/main/mvMainList.do
related: [api-정의-등록화면, api-간편조회, api-배포-신청과-승인]
updated: 2026-08-15
---

# 내 API 관리와 버전

`/apidev/api/main` 화면은 **내가(또는 내 시스템이) 등록한 API를 모아 보고 관리하는**
자리입니다. 등록 화면이 "만드는 곳"이라면 이곳은 "관리하는 곳"입니다.

## 화면 주소

| 기능 | URL |
|---|---|
| API 목록 | `/apidev/api/main/mvMainList.do` |
| 목록 데이터 | `/apidev/api/main/selMainListAjax.do` (POST) |
| 개발 요청 등록 화면 | `/apidev/api/main/mvDevReqReg.do` |
| 개발 요청 저장 | `/apidev/api/main/savReqRegAjax.do` |
| 개발 요청 상세 | `/apidev/api/main/mvDevReqView.do` |
| 답변 등록 화면 | `/apidev/api/main/mvDevAnsReg.do` |
| 답변 저장 | `/apidev/api/main/savDevReplyRegAjax.do` |
| 의견 저장 | `/apidev/api/main/savReplyRegAjax.do` |
| API 삭제 | `/apidev/api/main/delDevApiAjax.do` |
| 버전 저장 | `/apidev/api/main/savApiVerAjax.do` |
| 버전 중복 확인 | `/apidev/api/main/salApiVerDupCheckAjax.do` |
| 비공개 설정 | `/apidev/api/main/savApiPrivateAjax.do` |
| 다중 파일 업로드 | `/apidev/api/main/mutiUploadFile.do` (POST) |
| YAML 조회 | `/apidev/api/main/getYmalAjax.do` |

## 목록에서 할 수 있는 일

- 등록 상태·시스템·카테고리로 필터링
- API 클릭 → 등록 화면으로 이동해 수정
- 비공개 전환 (규격서·검색에서 감추기)
- 버전 추가
- 삭제(논리 삭제)

## 버전 관리

같은 API의 규격이 바뀌면 새 버전을 만듭니다. 버전은 문자열(`v1.0`, `v2.0` 등)로
관리하고, 같은 그룹 안에서 중복될 수 없어 저장 전에 중복 확인을 합니다.

버전을 새로 만들면 기존 버전은 그대로 남습니다. 이미 그 API를 쓰는 시스템이 있기
때문에 옛 버전을 바로 없애지 않는 것이 원칙입니다. 옛 버전을 정리할 때는 사용 여부를
먼저 확인하세요.

## 개발 요청과 답변

포털 안에는 **API 개발을 요청하고 답변을 받는 흐름**도 들어 있습니다.

```
요청자: 개발 요청 등록 (필요한 API 설명, 사유)
   ↓
담당자: 요청 확인 → 답변 등록
   ↓
요청자: 답변 확인 → 필요 시 의견 추가
```

의견(댓글)은 요청 상세 화면에서 주고받습니다. 첨부파일을 붙일 수 있어 규격 초안이나
화면 캡처를 함께 전달할 수 있습니다.

## 검토(Review) 기능

API에 대한 검토 요청과 의견도 관리됩니다. 검토 요청 유형, 제목, 내용, 대상 시스템을
지정해 등록하고, 검토자가 의견을 답니다. 검토 이력은 API 이력과 함께 남습니다.

## 비공개 전환

비공개로 바꾸면 검색·규격서에서 감춰집니다. 이미 배포된 API는 게이트웨이에서 계속
동작하므로, **비공개 전환만으로 서비스가 멈추지는 않습니다.** 실제로 내리려면
게이트웨이 배포를 삭제해야 합니다.

## 자주 묻는 질문

**Q. 목록에 다른 팀 API도 보입니다.**
A. 권한 범위 안의 시스템에 속한 API가 모두 보입니다. 본인이 등록한 것만 보려면
등록자 필터를 쓰세요.

**Q. 삭제했는데 게이트웨이에서 계속 호출됩니다.**
A. 포털의 삭제는 논리 삭제입니다. 게이트웨이에서 내리려면 배포 삭제를 별도로
실행해야 합니다.

**Q. 버전을 잘못 만들었습니다.**
A. 사용 이력이 없으면 삭제할 수 있습니다. 이미 배포된 버전이면 사용 여부를 `N` 으로
내리고 새 버전을 쓰세요.

**Q. 개발 요청은 Q&A와 무엇이 다른가요?**
A. Q&A는 포털·규격 사용에 대한 질문이고, 개발 요청은 "이런 API를 만들어 달라"는
업무 요청입니다.

**Q. 비공개인데 규격서에 아직 보입니다.**
A. 규격서가 캐시된 경우이거나, 그룹 단위가 아니라 API 단위만 비공개로 바꾼 경우일 수
있습니다. 새로고침 후에도 같으면 등록 상태를 확인하세요.
