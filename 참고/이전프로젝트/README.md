# 이전 프로젝트(`openapi-chat`) 참고 소스

**이 폴더는 실행되지 않습니다.** `app/` 에서 import 하지 마세요.
다른 PC에서 이어 작업할 때 이전 구현을 볼 수 없어 막히는 것을 막으려고 복사해 둔 것입니다.

이전 프로젝트는 **질문마다 LLM이 답변을 생성하는** 구조였습니다. 지금은 사전 생성 + 검색으로
바뀌었으므로 **그대로 가져다 쓰지 말고**, 아래 표의 "쓸 만한 부분"만 참고해서 새로 쓰세요.

| 파일 | 무엇 | 지금 쓸 만한 부분 |
| --- | --- | --- |
| `eval/question_gen.py` | 문서에서 질문 자동 생성 | QA 생성(할일 ①)의 프롬프트·파싱. **`is_korean()` 은 그대로 쓸 만합니다** — 모델이 중국어/영어를 섞어 뱉는 걸 걸러냅니다 |
| `eval/runner.py` | 백그라운드 실행 + 진행률 폴링 | 생성·평가가 수십 분 걸리므로 이 패턴이 필요합니다. 중지 버튼 포함 |
| `eval/retrieval_metrics.py` | Recall@5 / MRR | 품질 평가(할일 ②)에 거의 그대로 |
| `eval/golden_set.py` | 평가 문항 저장 | 구조 참고 |
| `eval/llm_judge.py` | LLM 채점 | **생성 모델과 채점 모델을 반드시 분리하세요** — 자기 답을 자기가 채점하면 점수가 부풀려집니다 |
| `pipeline/clustering.py` | 유사 질문 군집 + 통계 | 질문 분석(할일 ④)에 거의 그대로. 질문 임베딩 재사용 로직이 핵심 |
| `pipeline/draft.py` | 군집 → 문서 초안 생성 | 참고 |
| `deploy/*` | Docker · 폐쇄망 배포 | **이번 구조는 훨씬 단순합니다** — LLM(9GB)이 빠지고 임베딩(1.1GB)만 남습니다. 시드 디렉터리 패턴(볼륨이 이미지 data/를 가리는 문제)은 여전히 유효합니다 |

## 옮길 때 주의

- **설정 이름이 다릅니다.** 이전은 `rag_retrieval_floor`/`rag_soft_floor`,
  지금은 `qa_match_threshold`/`related_docs_floor` 입니다
- 이전 `answered_by`(cache/intent/rag/fallback) → 지금 `result_type`(answer/related_docs/unresolved)
- 시맨틱 캐시는 **지금 구조에 없습니다.** 답변이 이미 고정이라 캐시할 것이 없습니다
- 임베딩 호출부는 태스크 접두어를 받도록 바뀌었습니다(`app/ingestion/embedder.py`)
