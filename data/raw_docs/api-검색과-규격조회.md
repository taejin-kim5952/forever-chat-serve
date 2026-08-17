---
title: API 검색과 규격서 조회
category: API 조회 > 검색·규격서
url: /apidev/api/search/mvMainList.do
related: [api-그룹-등록화면, api-간편조회, 포털-전체개요]
updated: 2026-08-15
---

# API 검색과 규격서 조회

등록된 API를 찾아보는 화면입니다. **로그인하지 않아도 열람할 수 있는** 몇 안 되는
화면 중 하나입니다.

## 화면 주소

| 기능 | URL |
|---|---|
| API 검색 목록 | `/apidev/api/search/mvMainList.do` |
| 검색 목록 데이터 | `/apidev/api/search/selMainListAjax.do` (POST) |
| 상세 검색 화면 | `/apidev/api/search/apiSearch.do` |
| 상세 검색 결과 | `/apidev/api/search/apiSearchListAjax.do` |
| 규격 목록 | `/apidev/api/info/mvInfoList.do` |
| 규격서 상세 | `/apidev/api/info/mvInfoView.do` |
| 규격서 메뉴 조회 | `/apidev/api/info/selApiAjax.do` |
| 규격서 메뉴 저장 | `/apidev/api/info/savApiMenuListAjax.do` |
| API 검색 목록(규격) | `/apidev/api/info/selApiSearchList.do` |

## 검색에 나오는 조건

- **검색어** — API 이름, 설명, Path에 대해 부분 일치로 찾습니다.
- **시스템** — 특정 시스템에 속한 API만.
- **카테고리** — 규격서 목차 기준 분류.
- **Method** — GET/POST 등.
- **공개 구분** — Public/Private/Internal.

검색 결과는 페이지 단위로 끊어서 보여줍니다. 기본 페이지 크기는 20건이고, 목록 하단
페이지 번호로 이동합니다.

## 검색에 안 나오는 API

검색 목록에 노출되는 것은 **등록 상태가 공개(`APIREG1030`)인 API뿐**입니다. 아래
경우에는 등록되어 있어도 검색되지 않습니다.

- 아직 작성 중이거나(`APIREG1000`) 등록 완료 단계(`APIREG1010`)인 API
- 사용여부(`USE_YN`)가 `N` 으로 내려간 API
- 삭제 처리된 API (`DEL_DT` 값이 채워진 경우)
- 비공개(Private/Internal)로 지정되어 권한이 없는 사용자에게 감춰진 API

## 규격서 화면 구성

규격서(`mvInfoView.do`)는 왼쪽에 목차, 오른쪽에 본문이 있는 구조입니다.

- **목차** — 그룹 → 카테고리 → API 순서로 접히는 트리.
- **본문** — 선택한 API의 기본 정보, 요청 파라미터 표, 응답 파라미터 표, 예시,
  오류 코드가 순서대로 나옵니다.
- **다운로드** — 규격을 YAML/문서 파일로 내려받는 버튼이 있습니다.

파라미터 표의 행 순서는 파라미터 설계에서 정한 정렬 순서를 그대로 따릅니다.

## 조회수

FAQ와 마찬가지로 규격서에도 조회 횟수가 기록됩니다. 어떤 API가 많이 조회되는지
집계해 개선 우선순위를 정할 때 참고합니다.

## 자주 묻는 질문

**Q. 우리 팀이 등록한 API가 검색되지 않습니다.**
A. 등록 상태를 먼저 확인하세요. 공개 상태가 아니면 검색되지 않습니다. 상태가 공개인데도
안 보이면 사용여부가 `N` 이거나 삭제 처리된 경우입니다.

**Q. 로그인 없이 어디까지 볼 수 있나요?**
A. 검색 목록과 규격서 상세까지 볼 수 있습니다. 다만 Private API의 엔드포인트나 내부
연동 정보는 비로그인 상태에서 감춰집니다.

**Q. 검색어를 넣었는데 결과가 0건입니다.**
A. 검색은 부분 일치이지만 띄어쓰기까지 그대로 비교합니다. 짧은 키워드로 다시
시도하거나, 시스템·카테고리 조건을 지우고 검색해 보세요.

**Q. 규격서 목차 순서를 바꾸고 싶습니다.**
A. `savApiMenuListAjax.do` 로 저장되는 메뉴 구성 기능을 씁니다. 권한이 있는 계정만
목차를 편집할 수 있습니다.

**Q. 규격서를 파일로 받아 협력사에 전달해도 되나요?**
A. Public API 규격은 가능합니다. Private/Internal 규격에는 엔드포인트와 내부 시스템
정보가 들어 있으므로 대외 전달 전에 담당자 확인이 필요합니다.
