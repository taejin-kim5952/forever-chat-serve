---
title: API 간편 조회(SimpleView)
category: API 조회 > 간편 조회
url: /apidev/api/simpleview/mvApiSimpleView.do
related: [api-검색과-규격조회, api-정의-등록화면, api-파라미터-설계]
updated: 2026-08-15
---

# API 간편 조회(SimpleView)

전체 등록 화면을 열지 않고 **API 정의와 파라미터를 한 화면에서 빠르게 보고 고치는**
화면입니다. 항목이 많은 정식 등록 화면과 달리 핵심만 보여줍니다.

## 화면 주소

| 기능 | URL |
|---|---|
| 간편 조회 화면 | `/apidev/api/simpleview/mvApiSimpleView.do` |
| API 정의 상세 조회 | `/apidev/api/simpleview/selApiDefDetailAjax.do` |
| 규격 필수정보 저장 | `/apidev/api/simpleview/savSpcEssentialAjax.do` |
| API 정의 저장 | `/apidev/api/simpleview/savApiDefDetailAjax.do` |
| 파라미터 저장 | `/apidev/api/simpleview/savApiDefParamsAjax.do` |

## 이 화면이 편한 경우

- 파라미터 설명만 몇 줄 고칠 때
- 규격의 필수 정보(호스트·기본경로 등)만 손볼 때
- 여러 API를 훑으며 내용 확인만 할 때

반대로 엔드포인트·핸들러 같은 게이트웨이 연동 항목까지 손봐야 한다면 정식 등록
화면을 써야 합니다.

## 저장 단위가 나뉘어 있는 이유

간편 조회 화면은 저장이 세 갈래로 나뉩니다.

| 저장 대상 | 무엇을 저장하나 |
|---|---|
| 규격 필수정보 | 그룹(SPC) 레벨의 공통 정보 |
| API 정의 | API 한 건의 기본 정보 |
| 파라미터 | request/response 트리 |

한 번에 전부 저장하지 않는 이유는, 화면에서 건드린 부분만 갱신해 실수로 다른 값을
덮어쓰지 않게 하려는 것입니다. 파라미터만 고쳤다면 파라미터 저장만 누르면 됩니다.

## 관련 팝업

- **API 복제**(`popApiClone`) — 기존 API를 복사해 새 API를 만듭니다.
- **간편 등록**(`popSimpleApiReg`) — 최소 항목만으로 API를 새로 만듭니다.
- **BEAST 시스템 선택**(`popBstSysSelect`) — 게이트웨이 시스템을 고릅니다.

## 자주 묻는 질문

**Q. 간편 조회에서 저장한 내용이 정식 화면에 반영되나요?**
A. 같은 데이터를 다루므로 그대로 반영됩니다. 화면만 다를 뿐입니다.

**Q. 저장 버튼이 여러 개라 헷갈립니다.**
A. 고친 영역에 해당하는 버튼을 누르면 됩니다. 파라미터를 고쳤는데 정의 저장만 누르면
파라미터 변경이 반영되지 않습니다.

**Q. 엔드포인트를 바꾸고 싶은데 항목이 없습니다.**
A. 간편 화면에는 노출되지 않습니다. 정식 등록 화면에서 수정하세요.

**Q. 복제한 API를 저장하면 원본이 바뀌나요?**
A. 아니요. 복제는 새 API를 만드는 동작이라 원본은 그대로입니다. 다만 API ID와 Path는
바꿔야 저장됩니다.
