---
title: SQL Server → PostgreSQL 전환 정리
category: 기술 > 마이그레이션
url: /apidev
related: [데이터베이스-테이블-구조, jdk21-현대화-이력, 설정파일-구조]
updated: 2026-08-15
---

# SQL Server → PostgreSQL 전환 정리

포털의 데이터베이스는 SQL Server에서 PostgreSQL로 옮겨졌습니다. 모든 SQL이 Java
코드가 아니라 MyBatis XML에 모여 있어 패턴 단위 치환이 가능했던 점이 이 작업을
현실적으로 만들었습니다.

## 전환 규모

전체 변경 대상 패턴은 약 1,100건이고, 매퍼 XML 21개 중 거의 전부가 영향을
받았습니다.

## 단순 치환으로 끝난 것

| SQL Server | PostgreSQL | 건수 |
|---|---|---|
| `WITH(NOLOCK)` | 제거 (PostgreSQL은 MVCC 기본) | 약 559 |
| `ISNULL()` | `COALESCE()` | 약 235 |
| `GETDATE()` | `NOW()` | 약 108 |
| `LEN()` | `LENGTH()` | 약 13 |
| `REPLICATE()` | `REPEAT()` | 1 |
| `+` 문자열 연결 | `\|\|` (파이프 2개) | 약 19 |
| `dbo.` 접두사 | 제거 | 4 |
| `CAST(... AS MONEY)` | `TO_CHAR()` / `NUMERIC` | 1 |

가장 많았던 `WITH(NOLOCK)` 은 SQL Server에서 잠금을 피하려고 붙이던 힌트인데,
PostgreSQL은 기본이 MVCC라 읽기가 쓰기를 막지 않으므로 그냥 지우면 됩니다.

## 손이 더 간 것

| 패턴 | 대응 | 건수 |
|---|---|---|
| `CONVERT(varchar, 날짜, style)` | `TO_CHAR(날짜, '포맷')` | 약 95 |
| `CONVERT(int, ...)` | `CAST(... AS INTEGER)` | 약 20 |
| `TOP n` | `LIMIT n` (위치 이동 필요) | 약 14 |
| `DATEDIFF()` | `EXTRACT(...)` | 1 |
| `STUFF() + FOR XML PATH('')` | `STRING_AGG()` | 1 |
| `TRY_CONVERT()` | `CASE WHEN ... THEN ...::타입 END` | 10 |
| `SCOPE_IDENTITY()` | `INSERT ... RETURNING PK` | 약 14 |
| `IDENT_CURRENT()` | 시퀀스 조회 | 약 7 |

날짜 변환은 style 코드별로 포맷이 달라서 표를 만들어 하나씩 대응했습니다.

| style | 의미 | PostgreSQL 포맷 |
|---|---|---|
| `102` | `yyyy.mm.dd` | `YYYY.MM.DD` |
| `23` | `yyyy-mm-dd` | `YYYY-MM-DD` |
| `120` | `yyyy-mm-dd hh:mi:ss` | `YYYY-MM-DD HH24:MI:SS` |
| `121` / `21` | 밀리초 포함 | `YYYY-MM-DD HH24:MI:SS.MS` |
| `11` | `mon dd yyyy` | `Mon DD YYYY` |

## 바꾸지 않아도 됐던 것

표준 SQL이라 그대로 동작한 것들입니다.

- `ROW_NUMBER() OVER()`, `RANK()`, `LAG`/`LEAD` 같은 윈도 함수
- `COALESCE`, `NULLIF`, `SUBSTRING`, `REPLACE`, `CAST`
- MyBatis 동적 태그(`<if>`, `<choose>`, `<foreach>`)
- `OFFSET/FETCH` 기반 페이징(구조 유사)

## 타입 매핑

| SQL Server | PostgreSQL |
|---|---|
| `INT IDENTITY(1,1)` | `SERIAL` 또는 IDENTITY 컬럼 |
| `BIGINT IDENTITY(1,1)` | `BIGSERIAL` |
| `NVARCHAR(n)` | `VARCHAR(n)` |
| `NTEXT` | `TEXT` |
| `BIT` | `BOOLEAN` |
| `DATETIME` / `DATETIME2` | `TIMESTAMP` |
| `MONEY` | `NUMERIC(19,4)` |
| `UNIQUEIDENTIFIER` | `UUID` |

## 설정 변경

| 파일 | 변경 |
|---|---|
| `pom.xml` | `mssql-jdbc` → `postgresql` 드라이버 |
| 환경별 `application-*.yml` | 드라이버 클래스와 접속 URL |
| `context.xml` | Tomcat JNDI DataSource |

PostgreSQL 접속 URL에는 두 옵션을 붙였습니다.

- `currentSchema=public` — SQL Server의 `dbo` 에 대응하는 기본 스키마 지정
- `stringtype=unspecified` — 문자 타입 판단을 드라이버에 맡겨 MyBatis 호환성 확보

MyBatis 설정 클래스와 JNDI 조회 코드는 손대지 않았습니다. DataSource만 바뀌면
자동으로 따라오는 구조였기 때문입니다.

## 이 전환이 수월했던 이유

- Java 코드 안에 raw SQL이 없었습니다. 전부 XML에 모여 있었습니다.
- 사용자 정의 함수(UDF)가 없었습니다.
- `MERGE INTO` 같은 SQL Server 전용 UPSERT 구문이 없었습니다.
- T-SQL 변수 선언(`DECLARE @...`)이 없었습니다.
- 페이징이 이미 `OFFSET/FETCH` 로 현대화되어 있었습니다.

## 남은 주의점

- `ISNULL` 과 `COALESCE` 는 타입 규칙이 다릅니다. PostgreSQL은 타입에 엄격해서
  명시적 캐스팅이 필요할 수 있습니다.
- `TRY_CONVERT` 는 대응 함수가 없어 `CASE WHEN` 으로 사전 검증해야 합니다.
  PostgreSQL에서 `'abc'::INTEGER` 는 NULL이 아니라 예외를 던집니다.
- `+` 가 숫자 덧셈으로 쓰인 곳(`SORT_ODRG + 1`)은 바꾸면 안 됩니다.
- 날짜 포맷, 문자 인코딩, NULL 처리 같은 경계값은 실제 데이터로 확인해야 합니다.

## 자주 묻는 질문

**Q. 전환 후 조회 결과가 예전과 다릅니다.**
A. 날짜 포맷 변환(`CONVERT` → `TO_CHAR`)이 가장 흔한 원인입니다. style 코드 매핑이
맞는지 확인하세요.

**Q. INSERT 후 생성된 키를 못 받습니다.**
A. `SCOPE_IDENTITY()` 를 `RETURNING` 으로 바꾸면서 반환 컬럼을 잘못 지정한 경우입니다.
테이블 PK 컬럼명을 확인하세요.

**Q. 숫자로 변환하다 오류가 납니다.**
A. `TRY_CONVERT` 를 단순 캐스팅으로 바꾼 자리입니다. 값이 숫자인지 먼저 검사하는
조건을 넣어야 합니다.
