---
title: API 상세 등록 - 경로·카테고리·데이터타입
category: API 관리 > 상세 등록
url: /apidev/api/reg/mvApiInfoReg.do
related: [api-정의-등록화면, api-빠른등록과-템플릿, yaml-반입과-반출]
updated: 2026-08-15
---

# API 상세 등록 — 경로·카테고리·데이터타입

`/apidev/api/reg` 아래 화면들은 API 등록을 항목별로 나눠서 다루는 상세 화면 묶음입니다.
간편 등록으로 부족할 때, 또는 카테고리·데이터타입처럼 부가 정보를 정리할 때 씁니다.

## 화면 묶음

| 화면 | URL | 하는 일 |
|---|---|---|
| 기본 정보 등록 | `/api/reg/mvApiInfoReg.do` | API 기본 정보 입력 |
| 경로(Path) 등록 | `/api/reg/mvApiPathReg.do` | Method/Path와 파라미터 상세 |
| 카테고리 등록 | `/api/reg/mvApiCateInfoReg.do` | 규격서 목차 분류 관리 |
| 데이터타입 등록 | `/api/reg/mvApiDataTypeReg.do` | 공용 데이터 타입 정의 |

## 주요 비동기 호출

화면 안에서 데이터만 주고받는 호출들입니다. 문제가 생겼을 때 어느 단계에서 막혔는지
확인할 때 유용합니다.

| 호출 | URL | 하는 일 |
|---|---|---|
| API 정의 조회 | `selApiDefAjax.do` | 등록된 API 정의 불러오기 |
| 경로 저장 | `savApiRegPathAjax.do` | Path와 파라미터 저장 |
| 기본정보 저장 | `savApiRegBasicAjax.do` | 기본 정보 저장 |
| API 중복 확인 | `salApiDupCheckAjax.do` | 같은 Method+Path 존재 여부 |
| API ID 중복 확인 | `salApiIdCheckAjax.do` | ID 중복 여부 |
| Path 중복 확인 | `salApijDupPathCheckAjax.do` | Path 중복 여부 |
| 카테고리명 중복 | `selApiCateNmCheckAjax.do` | 카테고리 이름 중복 |
| API명 중복 | `selApiNmCheckAjax.do` | 이름 중복 |
| 버전 조회 | `selApiVerNoAjax.do` | 등록 가능한 버전 목록 |
| 다음 API ID | `selNextApiId.do` / `selNextApiIdInfo.do` | 자동 발번 |
| 이름 유효성 | `apiNameValidCheckAjax.do` | 이름 규칙 검사 |
| ID 유효성 | `apiIdValidCheckAjax.do` | ID 규칙 검사 |
| 경로 삭제 | `delApiPathAjax.do` | Path 1건 삭제 |
| 전체 경로 삭제 | `delApiAllPathAjax.do` | 그룹의 Path 전체 삭제 |
| 다른 API 불러오기 | `selImportApiListAjax.do` | 기존 API를 복사해 시작 |
| 배포 진행 확인 | `selDeployProc.do` | 이 API가 배포 중인지 |

## 카테고리 관리

카테고리는 규격서에서 API를 묶는 목차입니다. 등록 화면에서 이름과 설명, 정렬 순서를
정합니다.

| 항목 | 필드 | 설명 |
|---|---|---|
| 카테고리명 | `ctgryNm` | 목차에 노출되는 이름. 그룹 안에서 중복 불가 |
| 설명 | `ctgryDesc` | |
| 정렬 순서 | `sortOdrg` | 작은 값이 위로 |

카테고리를 삭제하면 그 카테고리에 속한 API는 분류가 비게 됩니다. API가 지워지는
것은 아니지만 규격서 목차에서 "미분류"로 밀려납니다.

## 데이터타입 관리

여러 API에서 반복되는 항목 묶음(예: 공통 주소 객체)을 데이터타입으로 정의해 두면
파라미터 설계에서 재사용할 수 있습니다. 등록은 `mvApiDataTypeReg.do` 화면에서
하고, 저장은 `savApiDataTypeRegAjax.do` 로 처리됩니다.

## 다른 API 복사해서 시작하기

`selImportApiListAjax.do` 로 조회되는 목록에서 기존 API를 고르면 그 API의 기본
정보와 파라미터가 폼에 복사됩니다. 비슷한 API를 여러 건 만들 때 가장 빠른 방법입니다.
복사한 뒤에는 반드시 **API ID와 Path를 바꿔야** 저장됩니다 — 중복 검사에 걸립니다.

## Arsenal / GitLab 연동 화면

`pathRegFormArsenal` 화면은 사내 Arsenal 저장소와 연동해 API를 등록하는 변형입니다.
GitLab 네임스페이스 존재 확인(`existsNSAtGitlabAjax.do`), YAML 파일 저장
(`saveYamlFileAjax.do`) 같은 호출이 추가로 붙습니다. 연동 설정(호스트·토큰)은 환경별
설정 파일에 들어 있으며, 토큰이 비어 있으면 이 화면의 연동 버튼이 동작하지 않습니다.

## 자주 묻는 질문

**Q. 기본 정보 화면과 경로 등록 화면을 다 채워야 하나요?**
A. 기본 정보를 먼저 저장해야 경로 등록으로 넘어갈 수 있습니다. 순서를 건너뛰면
"저장된 API가 없다"는 메시지가 나옵니다.

**Q. Path를 지웠는데 규격서에 그대로 있습니다.**
A. 규격서는 공개 상태(`APIREG1030`)의 데이터를 보여줍니다. 삭제 후에도 배포된 규격이
남아 있으면 재배포하거나 상태를 내려야 반영됩니다.

**Q. "이미 등록된 Path 입니다" 라고 나옵니다.**
A. 같은 그룹 안에 Method+Path 조합이 이미 있는 경우입니다. 중복 확인 버튼으로 어떤
API가 그 조합을 쓰고 있는지 먼저 확인하세요.

**Q. 전체 경로 삭제를 눌렀는데 되돌릴 수 있나요?**
A. 되돌릴 수 없습니다. 삭제 전에 YAML로 내려받아 두는 것을 권합니다.

**Q. 카테고리를 안 정하면 어떻게 되나요?**
A. 등록은 됩니다. 규격서 목차에서 분류 없이 표시될 뿐입니다. API 수가 많아지면
카테고리 없이는 찾기가 어려워지므로 초기에 정해 두는 편이 좋습니다.
