---
title: API 정의(Definition) 등록 화면
category: API 관리 > API 정의 등록
url: /apidev/api/spcreg/def/mvApiDefReg.do
related: [api-그룹-등록화면, api-파라미터-설계, api-상세등록-경로와-카테고리]
updated: 2026-08-15
---

# API 정의(Definition) 등록 화면

그룹(SPC)이 만들어졌으면 그 안에 실제 API를 한 건씩 넣는 화면입니다. 여기서 말하는
API 한 건은 **Method + Path 조합 하나**입니다.

## 화면 주소

| 기능 | URL |
|---|---|
| API 등록 화면 | `/apidev/api/spcreg/def/mvApiDefReg.do?apiSpcNo={그룹번호}` |
| 그룹 안의 API 목록 | `/apidev/api/spcreg/def/selDefListByApiSpcNoAjax.do` |
| API 상세 조회 | `/apidev/api/spcreg/def/selApiDefDetailAjax.do` |
| API ID 중복 확인 | `/apidev/api/spcreg/def/selApiIdChkAjax.do` |
| 다음 API ID 자동 발번 | `/apidev/api/spcreg/def/selNextApiIdAjax.do` |
| BEAST 시스템 목록 | `/apidev/api/spcreg/def/selBstSysListAjax.do` |
| 저장 | `/apidev/api/spcreg/def/savApiDefRegAjax.do` |

주소에 `apiSpcNo`(그룹번호)가 반드시 있어야 합니다. 빠지면 어느 그룹에 넣을지 알 수
없어 좌측 목록이 비어 있는 채로 열립니다.

## 화면 구성

- **왼쪽 목록** — 이 그룹에 이미 등록된 API 목록. 클릭하면 오른쪽 폼에 값이 채워지고
  수정 모드가 됩니다.
- **`+ 새 API 추가`** — 폼을 빈 상태(신규 모드)로 되돌립니다.
- **`그룹 정보 수정`** — 이 API가 속한 그룹 자체를 고치러 그룹 등록 화면으로 이동합니다.
- **`템플릿으로 시작`** — 미리 만들어 둔 템플릿을 골라 기본 정보와 파라미터를 한 번에
  채웁니다.

## 기본 정보 입력 항목

| 항목 | 필드 | 필수 | 설명 |
|---|---|---|---|
| API ID | `apiId` | O | 시스템 안에서 유일. 자동 발번 버튼으로 다음 번호를 받을 수 있습니다 |
| API 이름 | `apiNm` | O | 목록·규격서에 노출 |
| Path | `apiPath` | O | `/` 로 시작. 그룹 기본경로 뒤에 붙는 부분만 입력 |
| Method | `methodCd` | O | GET/POST/PUT/DELETE/PATCH |
| 설명 | `apiDesc` | X | |
| API 구분 | `apiGubun` | O | Public / Private / Internal |
| 권한그룹 | `autId` | O | 호출 가능한 권한그룹 |
| 카테고리 | `ctgryNm` | X | 규격서 목차에서 묶이는 단위 |
| 샌드박스 사용 | `sandboxYn` | X | `Y`면 테스트 호출 허용 |

`API 구분`을 **Private** 으로 고르면 아래 연동 항목이 추가로 나타납니다.

| 항목 | 필드 | 설명 |
|---|---|---|
| 핸들러 | `apiHandlerCd` | 게이트웨이가 쓸 변환 핸들러 |
| 엔드포인트 Method | `endpntMethodCd` | 실제 백엔드 호출 방식 |
| TB 엔드포인트 | `endpntTbUrl` | 검증계 백엔드 주소 |
| 운영 엔드포인트 | `endpntPrdUrl` | 운영 백엔드 주소 |
| 타임아웃 | `endpntTimeout` | 밀리초 |
| 허용 IP | `endpntClientIp` | 호출 허용 대역 |
| 응답 코드 필드 | `resmapResCdField` | 백엔드 응답에서 결과코드를 담은 필드명 |
| 성공 값 | `resmapSuccVal` | 그 필드가 이 값이면 성공으로 판정 |
| 오류 코드 필드 | `resmapErrCdField` | |
| 오류 메시지 필드 | `resmapErrMsgField` | |

## 핸들러 종류

Private API가 게이트웨이를 지날 때 요청/응답 형식을 바꿔주는 모듈이 핸들러입니다.

| 코드 | 이름 | 쓰임 |
|---|---|---|
| `ADPJSON` | Common Handler | 표준 JSON 변환 |
| `ANYJSON` | Any Common Handler | 형식 제약이 적은 JSON |
| `KOSJSON` | KOS MOS Handler | KOS 계열 JSON |
| `KOSSOAP` | KOS Soap Handler | KOS SOAP 연동 |
| `ADPSCAP` | SCAP Handler | SCAP 연동 |
| `ADPCAPRI` | CAPRI Handler | CAPRI 연동 |
| `ADPSB` | SB Handler | SB 연동 |

핸들러를 잘못 고르면 배포는 성공하지만 실제 호출에서 파라미터가 전달되지 않습니다.
백엔드 담당자에게 어떤 핸들러를 쓰는지 먼저 확인하세요.

## 저장 동작

저장 버튼을 누르면 확인 팝업이 한 번 뜨고, 확인해야 실제 저장됩니다. 저장이 성공하면

- 왼쪽 목록이 갱신되고,
- **신규 등록이었다면 폼이 자동으로 비워집니다.** 화면 이동 없이 바로 다음 API를
  이어서 입력할 수 있게 하려는 동작입니다.
- 수정이었다면 해당 API만 갱신되고 새 API가 생기지 않습니다.

## 자주 묻는 질문

**Q. API ID를 직접 정해도 되나요?**
A. 됩니다. 다만 시스템 안에서 유일해야 하므로 중복 확인 버튼을 눌러 확인하세요.
규칙을 정하기 애매하면 자동 발번 버튼을 쓰는 편이 안전합니다.

**Q. Path에 그룹 기본경로까지 다 적었더니 주소가 두 번 겹칩니다.**
A. Path에는 기본경로 뒤에 붙는 부분만 적습니다. 기본경로가 `/message/v1.0` 이면
Path에는 `/send` 만 적어야 하고 `/message/v1.0/send` 라고 적으면 안 됩니다.

**Q. Public과 Private은 무엇이 다른가요?**
A. Public은 규격서에 공개되고 외부 개발자가 볼 수 있습니다. Private은 지정된
권한그룹만 사용하며, 게이트웨이 연동 정보(핸들러·엔드포인트)를 추가로 입력해야
합니다. Internal은 사내 전용입니다.

**Q. 같은 Path에 Method만 다르게 등록할 수 있나요?**
A. 가능합니다. `GET /messages` 와 `POST /messages` 는 서로 다른 API로 취급됩니다.
다만 Method와 Path가 모두 같은 조합은 중복으로 막힙니다.

**Q. 저장했는데 규격서에는 안 보입니다.**
A. 등록 상태가 공개(`APIREG1030`)가 되어야 규격서·검색에 노출됩니다. 등록 직후에는
보통 등록 완료 상태이고, 검토를 거쳐 공개로 바뀝니다.
