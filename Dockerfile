# API Manager 도우미 — 운영 이미지
#
# ### 컨테이너 하나로 끝나는 이유
#
# 임베딩을 Ollama 가 아니라 **앱 안에서(ONNX Runtime)** 돌린다. 그래서 이 이미지 하나면
# 챗봇이 답한다. LLM(질문·답변·채점)은 스튜디오 전용이라 운영에 없다.
#
# ### 왜 도커여야 하는가
#
# 개발 서버가 CentOS 7(glibc 2.17)인데 `onnxruntime` 휠은 glibc 2.28 을 요구한다.
# 호스트에 직접 설치할 수 없다. 컨테이너는 자기 glibc 를 들고 오므로 상관없다.
#
# ### 모델을 이미지에 넣는 이유
#
# 운영이 **폐쇄망**이다. 이미지 하나만 반입하면 되도록 모델(565MB)을 함께 굽는다.
# 대신 `data/` 는 넣지 않는다 — 검수 결과와 질문 이력이 쌓이는 곳이라 볼륨으로 뺀다.

# ### 베이스 태그를 고정하는 이유 ★
#
# `python:3.11-slim` 은 떠다니는 태그다. 2026-08-17 에 받아 보니 **Debian 13(glibc 2.41)** 이
# 나왔다. 같은 Dockerfile 로 다음 달에 빌드하면 다른 OS 가 들어온다는 뜻이라, 여러 납품처에
# 같은 것을 설치해야 하는 제품에서는 그대로 두면 안 된다.
#
# bookworm(Debian 12 · glibc 2.36)으로 고정한다. `onnxruntime` 이 요구하는 glibc 2.28 을
# 넘고, 2028년까지 보안 지원이 있다.
#
# **옛날 도커가 도는 호스트라면 bullseye 로 빌드한다:**
#
#     docker build --build-arg BASE_IMAGE=python:3.11-slim-bullseye -t openapi-chat-serve .
#
# glibc 2.34 부터 `clone3` 시스템 호출을 쓰는데, 도커 20.10.10 미만의 기본 seccomp 규칙은
# 모르는 호출에 ENOSYS 가 아니라 EPERM 을 돌려준다. 그러면 glibc 가 옛 방식으로 물러서지
# 못하고 컨테이너가 'Operation not permitted' 로 죽는다. bullseye 는 glibc 2.31 이라
# `clone3` 을 아예 쓰지 않아 이 문제가 없다. CentOS 7 개발 서버가 여기에 해당할 수 있다.
ARG BASE_IMAGE=python:3.11-slim-bookworm
FROM ${BASE_IMAGE}

# 파이썬이 .pyc 를 남기지 않고, 로그를 버퍼링하지 않게 한다(컨테이너 로그가 늦게 보이면
# 장애 때 원인 추적이 늦어진다).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_MODE=serve \
    EMBED_ONNX_DIR=/app/models/bge-m3-onnx

WORKDIR /app

# 의존성을 먼저 넣어 레이어를 나눈다 — 코드를 고쳐도 이 무거운 단계를 다시 하지 않는다.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 임베딩 모델. 자주 바뀌지 않으므로 코드보다 먼저 넣는다.
COPY models/ ./models/

COPY app/ ./app/
COPY scripts/ ./scripts/

# 루트로 돌리지 않는다. 볼륨으로 붙일 data/ 도 이 사용자가 쓸 수 있어야 한다.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 18100

# 프로세스가 떠 있는 것과 답할 수 있는 것은 다르다 — 모델 파일이 없거나 QA 인덱스가 비면
# 화면은 뜨는데 모든 질문이 '미해결'로 떨어진다. 그 상태를 여기서 구분한다.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request,json,sys; \
r=json.load(urllib.request.urlopen('http://127.0.0.1:18100/health/ready', timeout=4)); \
sys.exit(0 if r.get('status')=='ok' else 1)"

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "18100"]
