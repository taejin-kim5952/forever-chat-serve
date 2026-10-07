---
title: YAML(Swagger/OpenAPI) 반입과 반출
category: API 관리 > YAML 연동
url: /apidev/api/reg/yamlDownload.do
related: [api-파라미터-설계, api-상세등록-경로와-카테고리, 파일-업로드와-다운로드]
updated: 2026-08-15
---

# YAML(Swagger/OpenAPI) 반입과 반출

파라미터를 하나씩 손으로 넣는 대신, Swagger/OpenAPI 규격 파일을 붙여넣어 한 번에
반영하거나, 반대로 등록된 규격을 파일로 내려받는 기능입니다.

## 관련 화면·호출

| 기능 | URL |
|---|---|
| YAML 다운로드 | `/apidev/api/reg/yamlDownload.do` |
| URL에서 YAML 가져오기 | `/apidev/api/reg/selUrlToYamlAjax.do` |
| apidoc 등록 | `/apidev/api/reg/regApidocAjax.do` |
| YAML 저장 | `/apidev/api/reg/savApiYamlAjax.do` |
| YAML 파일 저장 | `/apidev/api/reg/saveYamlFileAjax.do` (POST) |
| YAML 조회 | `/apidev/api/main/getYmalAjax.do` |
| YAML 도구 팝업 | `popApiYamlTool` |

YAML 다운로드는 비로그인 허용 경로에 포함되어 있어, 공개 규격은 로그인 없이 받을 수
있습니다.

## 반입(Import) 경로 세 가지

1. **붙여넣기** — YAML 도구 팝업에 내용을 그대로 붙여넣습니다.
2. **URL 지정** — 스펙이 공개된 주소를 넣으면 서버가 내려받아 파싱합니다.
3. **파일 업로드** — 스펙 파일을 올립니다. apidoc(Swagger JSON) 형식도 지원합니다.

반입하면 서버가 스펙을 파싱해 **경로·Method·파라미터 트리**를 만들어 화면에 채웁니다.
바로 저장되지 않고 화면에서 확인한 뒤 저장을 눌러야 반영됩니다.

## 변환 도구

내부적으로 여러 변환기가 함께 쓰입니다.

| 변환 | 하는 일 |
|---|---|
| YAML → JSON | 스펙을 JSON으로 바꿔 다루기 쉽게 함 |
| JSON → YAML | 반대 방향 |
| YAML → 내부 객체 | 파라미터 트리 생성 |
| YAML 파서 | 구문 검사 |
| WSDL 반입 | SOAP 규격에서 항목 생성 |

## 편집기

YAML을 직접 손볼 수 있는 코드 편집기가 화면에 내장되어 있습니다. 구문 강조, 접기,
자동완성, 오류 표시(lint)를 지원합니다. 들여쓰기가 틀리면 저장 전에 편집기에서
경고가 뜹니다.

## 저장 위치

반입·반출한 YAML 파일은 환경별로 지정된 파일 서버 경로에 저장됩니다. 경로는 설정의
`yaml.file.path` / `yamlServer.host` 로 관리되고, apidoc 결과물은 별도 출력 경로에
쌓입니다.

## 반출(Export)

등록된 규격을 YAML로 내려받아 다음 용도로 씁니다.

- 백업 (큰 변경 전에 받아 두면 되돌리기 쉬움)
- 협력사·타 팀 전달
- 다른 그룹에 같은 구조를 복제할 때 반입 소스로 재사용

## 자주 묻는 질문

**Q. YAML을 붙여넣었는데 파라미터가 안 생깁니다.**
A. 구문 오류이거나 지원 범위를 벗어난 문법입니다. 편집기의 오류 표시를 먼저
확인하세요. 들여쓰기 문제(탭/스페이스 혼용)가 가장 흔합니다.

**Q. `$ref` 로 참조된 스키마가 풀리지 않습니다.**
A. 외부 파일 참조는 내려받을 수 없어 실패할 수 있습니다. 참조를 인라인으로 펼친
스펙을 사용하세요.

**Q. 반입하면 기존 파라미터가 지워지나요?**
A. 반입 결과가 화면에 채워지고, 저장하면 그 내용으로 대체됩니다. 기존 내용을
남기고 싶다면 반입 전에 YAML로 내려받아 두세요.

**Q. 다운로드한 파일이 열리지 않습니다.**
A. 확장자를 `.yaml` 또는 `.yml` 로 저장했는지 확인하고 텍스트 편집기로 여세요.

**Q. WSDL도 넣을 수 있나요?**
A. 참조 WSDL URL을 지정해 SOAP 규격에서 항목을 만들 수 있습니다. 다만 JSON 계열보다
변환 정확도가 낮아 결과를 눈으로 확인해야 합니다.
