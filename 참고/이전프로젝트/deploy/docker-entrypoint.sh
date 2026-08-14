#!/bin/sh
set -e

OLLAMA_URL="${OLLAMA_HOST:-http://ollama:11434}"
EMBED_MODEL="${OLLAMA_EMBED_MODEL:-bge-m3}"
LLM_MODEL="${OLLAMA_LLM_MODEL:-qwen3.5:4b}"
SEED_DIR="${SEED_DIR:-/app/seed}"
DATA_DIR="${DATA_DIR:-/app/data}"
# true 로 두면 시드가 기존 파일을 덮어쓴다(이미지 내용으로 초기화). 평소에는 꺼둔다 —
# 관리자 화면에서 편집한 문서·카테고리가 배포 때마다 되돌아가면 안 되기 때문.
SEED_FORCE="${SEED_FORCE:-false}"

# ── 1. 시드 → 데이터 볼륨 ─────────────────────────────────────────────────────
# 볼륨은 최초 1회만 이미지 내용을 복사하므로, 이후 배포에서 추가된 문서/카테고리가
# 반영되지 않는다. 여기서 "볼륨에 없는 파일만" 채워 그 문제를 없앤다.
seed_copy() {
  src="$1"; dst="$2"
  [ -e "$src" ] || return 0
  if [ -e "$dst" ] && [ "$SEED_FORCE" != "true" ]; then
    echo "[entrypoint] 유지: ${dst} (이미 존재)"
    return 0
  fi
  cp -r "$src" "$dst"
  echo "[entrypoint] 시드 반영: ${dst}"
}

echo "[entrypoint] 시드 동기화 (SEED_FORCE=${SEED_FORCE})"
mkdir -p "${DATA_DIR}/raw_docs" "${DATA_DIR}/chroma" "${DATA_DIR}/logs"
if [ -d "${SEED_DIR}/raw_docs" ]; then
  for f in "${SEED_DIR}"/raw_docs/*; do
    [ -e "$f" ] || continue
    seed_copy "$f" "${DATA_DIR}/raw_docs/$(basename "$f")"
  done
fi
seed_copy "${SEED_DIR}/categories.json" "${DATA_DIR}/categories.json"
seed_copy "${SEED_DIR}/golden_set.jsonl" "${DATA_DIR}/golden_set.jsonl"

# ── 2. Ollama 준비 대기 ──────────────────────────────────────────────────────
echo "[entrypoint] Ollama(${OLLAMA_URL}) 준비 대기 중..."
until curl -sf "${OLLAMA_URL}/api/version" >/dev/null 2>&1; do
  sleep 2
done
echo "[entrypoint] Ollama 준비 완료"

# 임베딩 모델이 없으면 문서 적재가 실패한다. 폐쇄망에서는 모델 반입이 늦어질 수 있으므로
# 무한정 기다리지 않고, 일정 시간 뒤에는 적재를 건너뛰고 서버는 띄운다
# (모델 반입 후 관리자 화면에서 문서를 저장하면 그때 색인된다).
WAIT_LEFT="${MODEL_WAIT_SECONDS:-180}"
echo "[entrypoint] 임베딩 모델(${EMBED_MODEL}) 준비 대기 (최대 ${WAIT_LEFT}초)"
while [ "$WAIT_LEFT" -gt 0 ]; do
  if curl -sf "${OLLAMA_URL}/api/tags" 2>/dev/null | grep -q "\"${EMBED_MODEL}"; then
    echo "[entrypoint] 임베딩 모델 확인됨"
    break
  fi
  sleep 5
  WAIT_LEFT=$((WAIT_LEFT - 5))
done
if [ "$WAIT_LEFT" -le 0 ]; then
  echo "[entrypoint] 경고: 임베딩 모델(${EMBED_MODEL})을 찾지 못했습니다. 문서 적재를 건너뜁니다."
  echo "[entrypoint]        모델 반입 후 /admin 의 'RAG 문서 관리'에서 문서를 저장하면 색인됩니다."
fi

if ! curl -sf "${OLLAMA_URL}/api/tags" 2>/dev/null | grep -q "\"${LLM_MODEL}"; then
  echo "[entrypoint] 경고: 답변 모델(${LLM_MODEL})이 없습니다. 질문에 답할 수 없습니다."
fi

# ── 3. 문서 색인 ─────────────────────────────────────────────────────────────
if [ "$WAIT_LEFT" -gt 0 ]; then
  echo "[entrypoint] RAG 문서 적재 중... (변경된 문서만 재색인)"
  python scripts/ingest.py || echo "[entrypoint] 문서 적재 실패 — /admin 에서 재시도 가능"
fi

echo "[entrypoint] 서버 기동"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
