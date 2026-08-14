FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts

# ── 시드 데이터 ────────────────────────────────────────────────────────────────
# 초기 데이터를 /app/data 가 아니라 /app/seed 에 넣는 이유:
# 운영에서는 /app/data 에 볼륨을 붙이는데, 볼륨은 "처음 만들어질 때 비어 있을 때만"
# 이미지 내용을 복사한다. 이미지 안 /app/data 에 문서를 넣어두면 두 번째 배포부터는
# 문서를 고쳐도 반영되지 않는다(볼륨이 이미 채워져 있으므로).
# 시드를 별도 경로에 두고 entrypoint 가 "없는 것만" 복사하면,
#   - 새로 추가한 문서/카테고리는 다음 배포에 반영되고
#   - 관리자 화면에서 편집한 내용은 덮어쓰이지 않는다.
COPY data/raw_docs ./seed/raw_docs
COPY data/categories.json ./seed/categories.json
COPY data/golden_set.jsonl ./seed/golden_set.jsonl

COPY docker-entrypoint.sh .
RUN mkdir -p data/chroma data/logs \
    && chmod +x docker-entrypoint.sh \
    && useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
