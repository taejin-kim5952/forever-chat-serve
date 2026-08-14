# 폐쇄망 배포 절차 (GitHub Actions + Jenkins + Docker)

운영 서버는 인터넷이 되지 않는다. 그래서 **인터넷이 되는 곳(GitHub Actions)에서 반입 파일을
만들고**, 폐쇄망에서는 `docker load` 와 `docker compose up` 만 수행한다.

개발 서버는 인터넷이 되지만, **운영과 같은 절차를 리허설**하기 위해 같은 방식으로 배포한다.

## 반입 파일 구성

| 파일 | 내용 | 대략 크기 |
| --- | --- | --- |
| `app.tar` | 앱 이미지 (코드 + 시드 데이터) | ~1 GB |
| `ollama-base.tar` | 모델이 들어 있지 않은 공식 Ollama 이미지 | ~1.5 GB |
| `model-bge-m3.tar.gz` | 임베딩 모델 | ~1 GB |
| `model-qwen3.5-4b.tar.gz` | 답변 모델 | ~3 GB |
| `model-gemma4-latest.tar.gz` | 질문 생성·채점 모델 | ~9 GB |

> **모델을 이미지에 굽지 않는 이유**
> 세 모델을 합치면 13 GB라 빌드 러너 디스크(약 14 GB)와 아티팩트 크기를 넘긴다.
> 모델별 파일로 나누면 한 번에 하나씩만 다루면 되고, 운영에서 **모델만 따로 교체·반입**할 수 있다.
> 채점 모델이 부담되면 `exaone-deep:7.8b`(약 4.4 GB)로 낮춰도 된다.

---

## 0. 서버 스펙 요구사항

GPU 없이 CPU로 돌리는 것을 전제로 한다. **메모리가 가장 먼저 막히는 지점**이다.

| 항목 | 최소 | 권장 | 비고 |
| --- | --- | --- | --- |
| 메모리 | **8 GB** | 16 GB 이상 | 아래 모델별 소요 참고 |
| 디스크 | 30 GB | 50 GB | 모델 13 GB + 이미지 3 GB + 볼륨·백업 |
| CPU | 4 코어 | 8 코어 이상 | 코어 수가 답변 속도를 좌우한다 |

모델을 올릴 때 대략 그 파일 크기만큼 메모리를 쓴다.

| 모델 | 용도 | 메모리 |
| --- | --- | --- |
| `bge-m3` | 임베딩(검색) | ~1 GB |
| `qwen3.5:4b` | 답변 | ~4 GB |
| `gemma4:latest` | 질문 생성·채점 | ~9 GB |

### 판단 기준은 "전체 메모리"가 아니라 "가용 메모리"다

`free -h` 의 **available** 열을 봐야 한다. 같은 서버에서 다른 서비스가 이미 메모리를 쓰고 있으면
그만큼 못 쓴다. 예를 들어 전체 15 GB라도 다른 서비스가 6 GB를 쓰고 있으면 가용은 7 GB 남짓이라
`gemma4`(9 GB)는 올라가지 않는다.

### `OLLAMA_MAX_LOADED_MODELS` 를 1로 두지 말 것

질문 1건은 **임베딩 모델(검색) → 답변 모델(생성)** 순으로 두 모델을 모두 쓴다.
1로 두면 매 질문마다 서로를 밀어내며 수 GB를 디스크에서 다시 읽어 오히려 크게 느려진다.
**2가 기본값**이며, 이때 `bge-m3`(~1 GB) + 답변 모델(~4 GB) 이 함께 상주한다.

메모리가 부족하면 이 순서로 줄인다.

1. 채점 모델을 `exaone-deep:7.8b`(~4.4 GB)로 교체 → 반입 파일도 9 GB → 4.4 GB로 줄어든다
2. 그래도 부족하면 채점 모델을 빼고 답변 모델로 겸용(자기 채점 편향은 감수)
3. 답변 모델을 `gemma3:1b`(~0.8 GB)로 — 마지막 수단. 답변 품질이 눈에 띄게 떨어진다

```bash
# 실행 중 메모리 확인
docker stats --no-stream
docker compose -f docker-compose.prod.yml exec ollama ollama ps   # 현재 올라간 모델
```

---

## 1. 반입 파일 만들기 (GitHub Actions)

저장소 → **Actions** → **Build Deployment Images** → **Run workflow**

| 입력 | 값 |
| --- | --- |
| `image_tag` | `1.1` (배포할 때마다 올린다 — 롤백이 쉬워진다) |
| `models` | `["bge-m3","qwen3.5:4b","gemma4:latest"]` |

실행이 끝나면 **Artifacts** 에서 파일을 내려받는다. 모델은 잡이 각각 돌아 개별 파일로 나온다.

- 코드만 바뀐 경우: `main` 에 push 하면 `app.tar` 만 자동으로 다시 만들어진다(모델은 그대로 재사용).
- 모델을 바꾸는 경우에만 `models` 입력을 넣어 수동 실행한다.

### 인터넷 되는 PC에서 직접 만들 수도 있다

```bash
docker build -t openapi-chat/app:1.1 .
docker save -o app.tar openapi-chat/app:1.1

docker pull ollama/ollama:latest
docker save -o ollama-base.tar ollama/ollama:latest

./scripts/export_models.sh bge-m3 qwen3.5:4b gemma4:latest   # artifacts/ 에 생성
```

---

## 2. 반입 (조직 보안 절차)

위 파일들을 배포 대상 서버의 `ARTIFACT_DIR`(기본 `/opt/openapi-chat/artifacts`)에 놓는다.
저장소 소스도 함께 있어야 한다 — `docker-compose.prod.yml`, `Jenkinsfile`, `scripts/` 가 필요하다.

---

## 3. 배포 (Jenkins)

Jenkins Job 파라미터

| 파라미터 | 기본값 | 설명 |
| --- | --- | --- |
| `ARTIFACT_DIR` | `/opt/openapi-chat/artifacts` | 반입 파일 경로 |
| `APP_TAG` | `1.1` | 배포할 앱 이미지 태그 |
| `LOAD_MODELS` | `true` | 모델 반입 여부(모델이 안 바뀌었으면 꺼서 시간 절약) |
| `BACKUP_DATA` | `true` | 배포 전 데이터 볼륨 백업 |
| `RUN_INGEST_CHECK` | `true` | 배포 후 헬스체크 |

파이프라인이 하는 일

1. 반입 파일 확인
2. **데이터 백업** — 질문 로그·분석 결과·편집한 문서는 복구가 안 되므로 먼저 받아둔다
3. `docker load` (앱 + Ollama 이미지)
4. `scripts/load_models.sh` 로 모델을 Ollama 볼륨에 풀어 넣기
5. `docker compose -f docker-compose.prod.yml up -d`
6. 헬스체크 + 설치된 모델 목록 확인

### Jenkins 없이 수동으로

```bash
docker load -i artifacts/app.tar
docker load -i artifacts/ollama-base.tar
./scripts/load_models.sh artifacts/model-*.tar.gz
APP_TAG=1.1 docker compose -f docker-compose.prod.yml up -d
```

---

## 4. 배포 후 확인

```bash
curl http://<서버IP>:8000/health          # {"status":"ok"}
curl http://<서버IP>:8000/models          # 반입한 모델 3종이 보여야 한다
curl http://<서버IP>:8000/categories      # 질문 카테고리가 비어 있지 않아야 한다
```

브라우저 확인

- `http://<서버IP>:8000/` — 챗봇. **입력창 위에 `주제 선택` 버튼이 보여야 한다**
  (안 보이면 카테고리가 비어 있다는 뜻 → 아래 문제 해결 참고)
- `http://<서버IP>:8000/admin` — 관리자 5개 탭

첫 질문은 문서 색인·모델 로딩 때문에 느릴 수 있다. 컨테이너 로그로 진행을 볼 수 있다.

```bash
docker compose -f docker-compose.prod.yml logs -f app
```

---

## 5. 데이터 — 무엇이 이미지에서 오고 무엇이 서버에 남는가

앱 이미지는 **초기값(시드)** 만 들고 온다. 운영 중 쌓이는 데이터는 서버 볼륨(`app_data`)에 남는다.

| 구분 | 항목 | 배포 시 |
| --- | --- | --- |
| **시드** (이미지에 포함) | `raw_docs/`, `categories.json`, `golden_set.jsonl` | 볼륨에 **없는 것만** 채움 |
| **운영 데이터** (볼륨) | `question_log.jsonl`, `question_embeddings.jsonl`, `analytics.json`, `runtime_config.json`, `fallback_queue.jsonl`, 편집한 문서 | **건드리지 않음** |
| **재생성 가능** | `chroma/`(벡터 색인), `semantic_cache.json`, `logs/` | 색인은 기동 시 자동 |

> **시드가 "없는 것만" 채우는 이유**
> Docker 볼륨은 처음 만들어질 때만 이미지 내용을 복사한다. 이미지 안 `/app/data` 에 문서를 두면
> 두 번째 배포부터 문서를 고쳐도 반영되지 않는다. 그래서 이미지는 `/app/seed` 에 원본을 두고,
> 컨테이너가 뜰 때 볼륨에 없는 파일만 복사한다.
> 결과적으로 **새로 추가한 문서·카테고리는 다음 배포에 반영되고, 관리자 화면에서 편집한 내용은 보존된다.**

### 시드로 강제 초기화하기

이미지 내용으로 문서·카테고리를 되돌리려면 한 번만 켠다.

```bash
SEED_FORCE=true APP_TAG=1.1 docker compose -f docker-compose.prod.yml up -d
# 확인 후 다시 끄고 재기동 (켜둔 채로 두면 배포마다 편집 내용이 되돌아간다)
APP_TAG=1.1 docker compose -f docker-compose.prod.yml up -d
```

### 백업 / 복원

```bash
# 백업 (Jenkins 파이프라인이 배포 전에 자동으로 수행)
docker run --rm -v openapi-chat_app_data:/data -v $(pwd):/backup \
  busybox tar czf /backup/app_data_$(date +%Y%m%d).tar.gz -C /data .

# 복원
docker compose -f docker-compose.prod.yml down
docker run --rm -v openapi-chat_app_data:/data -v $(pwd):/backup \
  busybox sh -c 'rm -rf /data/* && tar xzf /backup/app_data_20260814.tar.gz -C /data'
docker compose -f docker-compose.prod.yml up -d
```

---

## 6. 모델 / 코드 갱신

| 무엇이 바뀌었나 | 할 일 |
| --- | --- |
| 코드만 | `app.tar` 만 새로 반입 → Jenkins 재실행 (`LOAD_MODELS=false`) |
| 문서·카테고리 | 같은 이미지에 포함되므로 `app.tar` 재반입. **새 파일은 자동 반영, 기존 파일 수정은 `SEED_FORCE` 필요** |
| 모델 | 해당 `model-*.tar.gz` 만 새로 반입 → `LOAD_MODELS=true` |

이미지 태그(`1.1`, `1.2` …)를 배포마다 올려두면 이전 태그로 되돌리는 것만으로 롤백된다.

---

## 7. 문제 해결

**챗봇에 `주제 선택` 버튼이 안 보인다**
카테고리가 비어 있다. `curl .../categories` 로 확인하고, 비었으면 시드가 안 들어간 것이다.

```bash
docker compose -f docker-compose.prod.yml exec app ls -l /app/seed /app/data
docker compose -f docker-compose.prod.yml logs app | grep 시드
```

**답변이 안 나온다 / `/models` 가 비어 있다**
모델이 볼륨에 안 들어갔다. `scripts/load_models.sh` 를 다시 실행하고 Ollama 컨테이너를 재기동한다.

```bash
docker compose -f docker-compose.prod.yml restart ollama
docker compose -f docker-compose.prod.yml exec ollama ollama list
```

**답변이 문장 중간에서 끊긴다**
컨텍스트 창이 작다. 관리자 → 임계값 설정 → LLM 생성 설정에서 `OLLAMA_NUM_CTX` 를 올린다
(compose 기본값 8192).

**첫 기동이 오래 걸린다**
문서 색인 때문이다. 로그에 `RAG 문서 적재 중...` 이 보이면 정상이다.
임베딩 모델이 없으면 3분 대기 후 색인을 건너뛰고 서버만 뜬다(로그에 경고).
모델 반입 후 관리자 화면에서 문서를 저장하면 그때 색인된다.

---

## 8. CPU 전용 환경 성능 참고

GPU 없이 CPU로 돌리는 환경 기준(로컬 측정값이며 서버 사양에 따라 달라진다).

| 모델 | 답변 1건 | 비고 |
| --- | --- | --- |
| `qwen3.5:4b` | 20~60초 | 현재 기본 답변 모델 |
| `gemma3:1b` | 20~30초 | 빠르지만 답변 품질이 낮다 |

관리자 → 품질 평가 탭에서 답변 모델을 바꿔가며 Recall@5 / MRR / 답변 점수를 비교할 수 있다.
**답변 모델과 채점 모델은 다르게 고르는 것을 권한다** — 같은 모델이 답하고 채점하면 점수가 후해진다.

---

## 9. 보안 참고

`/admin` 에는 **인증이 없다.** 문서 삭제, 설정 변경, LLM 배치 실행이 접근 가능한 누구나 가능하다.
사내망 한정으로 운영하고, 필요하면 리버스 프록시(Nginx 등)에서 접근 제어를 걸어야 한다.
