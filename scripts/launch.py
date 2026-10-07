"""더블클릭 실행용 런처 — `실행.bat` 이 부른다.

매번 cmd 에서 venv 를 켜고 uvicorn 을 치는 것이 번거로워 만들었다. 처음 실행이거나 환경이
비어 있으면 필요한 준비를 알아서 한다.

### 왜 배치 파일이 아니라 파이썬인가

처음에는 전부 `.bat` 으로 썼는데 **한글이 섞이면 파서가 깨졌다.** cmd 는 배치 파일을 콘솔
코드페이지(한국어 Windows 기본 949)로 읽는데 파일은 UTF-8이라, 한글 바이트가 엉뚱한 문자로
해석되면서 줄이 잘리고 라벨을 건너뛰었다. `chcp 65001` 을 첫 줄에 넣어도 마찬가지였다.

그래서 `.bat` 은 **ASCII만** 남기고(파이썬을 찾아 이 파일을 부르는 세 줄), 안내 문구와 판단은
전부 여기로 옮겼다. 파이썬은 콘솔에 유니코드로 직접 쓰기 때문에 코드페이지와 무관하다.

### 어떤 팩으로 띄우는가

    python scripts/launch.py                          data/ 를 그대로 (지금까지와 같음)
    python scripts/launch.py mcp-manager --port 18101 packs/mcp-manager 로

**팩마다 `.bat` 을 따로 둔다**(`실행-api.bat` · `실행-mcp.bat`). 하나가 둘 다 띄우면 한쪽이
죽어도 눈치채기 어렵고, 어느 창이 어느 도메인인지 알 수 없다. 창 제목과 콘솔 머리글에 팩
이름을 적어 두는 것이 그래서 중요하다.

포트를 팩 파일(`pack.json`)에 적지 않는 이유: 팩은 **반입물**이고 포트는 **설치처 사정**이다.
같은 팩을 다른 포트로 두 번 띄우는 경우(운영 확인용)가 실제로 있다.

### 하는 일

1. 이미 그 포트에서 돌고 있으면 브라우저만 연다 — 두 번 눌러도 사고가 안 난다
2. 가상환경이 없으면 만든다
3. Ollama 가 없으면 경고한다 — 임베딩이 없으면 모든 질문이 '미해결'로 떨어진다
4. 벡터 저장소가 없으면 색인한다 — 이 프로젝트에서 가장 흔한 함정이다
5. 서버를 띄우고, 응답하기 시작하면 브라우저를 연다
"""

import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
DEFAULT_PORT = 18100


def parse_args(argv: list[str]) -> tuple[str, int]:
    """`launch.py [팩이름] [--port 18101]`. 둘 다 없으면 지금까지와 같이 동작한다.

    인자를 안 주면 `data/` 를 그대로 쓴다 — 기존 설치와 `실행.bat` 이 그대로 돌아야 한다.
    """
    pack, port = "", DEFAULT_PORT
    rest = list(argv)
    if "--port" in rest:
        at = rest.index("--port")
        try:
            port = int(rest[at + 1])
        except (IndexError, ValueError):
            pass
        del rest[at:at + 2]
    if rest:
        # 'packs/mcp-manager' 처럼 경로째 줘도 받는다. 탭 완성으로 치면 그렇게 된다.
        pack = rest[0].replace("\\", "/").rstrip("/").split("/")[-1]
    return pack, port


PACK, PORT = parse_args(sys.argv[1:])
BASE = f"http://localhost:{PORT}"
PACK_DIR = ROOT / "packs" / PACK if PACK else None
VAR_DIR = ROOT / "var" / PACK if PACK else None


def child_env() -> dict:
    """자식 프로세스(uvicorn·색인)에 넘길 환경.

    설정은 `@lru_cache` 라 프로세스 안에서 굳는다. 그래서 **띄우기 전에** 정해야 하고,
    이 런처가 하는 일이 사실상 그것 하나다.
    """
    env = os.environ.copy()
    if PACK:
        env["PACK_DIR"] = str(PACK_DIR)
        env["VAR_DIR"] = str(VAR_DIR)
    return env


def pack_title() -> str:
    """콘솔 머리글에 쓸 이름. 창이 여러 개 떠 있을 때 어느 도메인인지 이것으로 가른다."""
    if not PACK:
        return "openapi-chat-serve"
    manifest = PACK_DIR / "pack.json"
    if manifest.exists():
        try:
            profile = json.loads(manifest.read_text(encoding="utf-8")).get("profile") or {}
            if profile.get("service_name"):
                return f"{profile['service_name']} ({PACK})"
        except (OSError, ValueError):
            pass   # 팩이 잘못됐으면 서버가 기동 때 막는다. 여기서 죽을 이유가 없다.
    return PACK


# 콘솔에 직접 쓸 때는 유니코드로 나가지만, 출력을 파일이나 파이프로 넘기면 파이썬이 지역
# 코드페이지(한국어 Windows 는 cp949)로 인코딩한다. 그때 cp949 에 없는 글자가 하나라도 있으면
# UnicodeEncodeError 로 **런처가 죽는다.** 안내 문구 하나 때문에 실행이 안 되는 건 말이 안 되므로
# UTF-8 로 고정하고, 그래도 못 쓰는 글자는 바꿔서 내보낸다.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def say(message: str = "") -> None:
    print(message, flush=True)


def is_serving() -> bool:
    """포트가 열려 있는가. 두 번 실행했을 때 uvicorn 이 'address in use' 로 죽는 것을 막는다."""
    with socket.socket() as sock:
        sock.settimeout(0.3)
        return sock.connect_ex(("127.0.0.1", PORT)) == 0


def http_ok(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout):
            return True
    except (urllib.error.URLError, OSError):
        return False


def ensure_venv() -> bool:
    if VENV_PYTHON.exists():
        return True

    say("[준비] 파이썬 가상환경이 없습니다. 처음 한 번만 만듭니다. 몇 분 걸립니다.")
    say(f"       사용할 파이썬: {sys.version.split()[0]}")
    if sys.version_info[:2] != (3, 11):
        # 3.12 이상은 chroma-hnswlib 휠이 없어 C++ 빌드 도구를 요구한다. 여기서 멈추는 편이
        # 낫다 — 설치가 몇 분 돌다가 컴파일러 오류로 끝나면 원인을 찾기 어렵다.
        say(f"[오류] Python 3.11 이 필요합니다. 지금은 {sys.version.split()[0]} 입니다.")
        say("       py install 3.11   을 실행한 뒤 다시 시도하세요.")
        return False

    if subprocess.run([sys.executable, "-m", "venv", str(ROOT / ".venv")]).returncode:
        say("[오류] 가상환경을 만들지 못했습니다.")
        return False

    say("[준비] 패키지를 설치합니다.")
    installed = subprocess.run([
        str(VENV_PYTHON), "-m", "pip", "install",
        "--disable-pip-version-check", "-q", "-r", str(ROOT / "requirements.txt"),
    ])
    if installed.returncode:
        say("[오류] 패키지 설치에 실패했습니다.")
        return False

    say("[준비] 완료.")
    return True


def ensure_embed_model() -> bool:
    """임베딩 모델 파일이 없으면 받는다.

    565MB 라 저장소에 넣지 않는다(`.gitignore`). 없으면 질문을 벡터로 바꿀 수 없어
    **모든 질문이 '미해결'로 떨어진다** — 화면은 멀쩡히 떠서 버그로 오해하기 쉽다.
    """
    model_dir = ROOT / "models" / "bge-m3-onnx"
    if (model_dir / "model.onnx").exists() and (model_dir / "tokenizer.json").exists():
        return True

    say("[준비] 임베딩 모델이 없습니다. 받습니다(약 565MB, 몇 분 걸립니다).")
    if subprocess.run([str(VENV_PYTHON), "scripts/fetch_onnx_model.py"], cwd=str(ROOT)).returncode:
        say("[경고] 모델을 받지 못했습니다. 모든 질문이 '미해결'로 떨어집니다.")
        say("       폐쇄망이면 외부망 PC에서 받아 models/ 폴더를 복사해 넣으세요.")
        say()
        return False
    say()
    return True


def warn_if_no_ollama() -> None:
    """LLM(질문·답변·채점)용. **임베딩과는 무관하다** — 그쪽은 앱 안에서 ONNX 로 돈다."""
    if http_ok("http://localhost:11434/api/version", timeout=3):
        return
    say("[알림] Ollama 응답이 없습니다. 챗봇 답변·검색에는 지장이 없습니다.")
    say("       QA 생성·채점(스튜디오 기능)만 쓸 수 없습니다.")
    say()


def ensure_index() -> None:
    """벡터 저장소가 없으면 만든다.

    `chroma/` 는 파생물이라 저장소에 없다. 없으면 검색이 아무것도 못 찾아서 "동작은 하는데
    답이 안 나오는" 상태가 되고, 이걸 버그로 오해하기 쉽다. 원본 파일(qa_index.json ·
    categories.json · raw_docs/)은 읽기만 한다.

    **팩이면 `pack_index.py` 에 맡긴다.** 색인 전에 팩을 검사해서 반쯤 들어간 인덱스를
    남기지 않는데, 그 판단이 두 벌이 되면 런처로 띄운 것과 손으로 색인한 것이 달라진다.
    """
    store = (VAR_DIR / "chroma") if PACK else (ROOT / "data" / "chroma")
    if store.exists():
        return

    say("[준비] 벡터 저장소가 없습니다. 문서와 QA를 색인합니다. 30초 정도 걸립니다.")
    if PACK:
        failed = subprocess.run(
            [str(VENV_PYTHON), "scripts/pack_index.py", str(PACK_DIR), str(VAR_DIR)],
            cwd=str(ROOT), env=child_env(),
        ).returncode
    else:
        code = (
            "from app.ingestion.doc_index import DocIndex;"
            "from app.qa.index import QaIndex;"
            "d=DocIndex().ingest_dir(force=True);"
            "q=QaIndex().rebuild();"
            "print('       문서', len(d), '건 / 청크', sum(d.values()), '개');"
            "print('       QA', q['items'], '건 / 검색 벡터', q['vectors'], '개')"
        )
        failed = subprocess.run([str(VENV_PYTHON), "-c", code], cwd=str(ROOT), env=child_env()).returncode
    if failed:
        say("[경고] 색인에 실패했습니다. 임베딩 모델 파일을 확인하세요.")
        say("       python scripts/fetch_onnx_model.py")
    say()


def open_browser_when_ready() -> None:
    """서버가 응답하면 브라우저를 연다. 바로 열면 '연결할 수 없음'이 먼저 보인다."""
    for _ in range(60):
        if http_ok(f"{BASE}/health", timeout=1):
            webbrowser.open(BASE)
            return
        time.sleep(1)


def main() -> int:
    say()
    say(" ============================================================")
    say(f"  {pack_title()} - 로컬 실행  (포트 {PORT})")
    say(" ============================================================")
    say()

    if PACK and not PACK_DIR.is_dir():
        say(f" [오류] 팩 폴더가 없습니다: {PACK_DIR}")
        say("        python scripts/pack_new.py <팩이름>   으로 만들 수 있습니다.")
        return 1

    if is_serving():
        # 무엇이 떠 있는지는 알 수 없다. 같은 포트에 다른 팩을 띄워 두고 이 창을 누르면
        # "왜 내 문서가 안 보이지" 가 되므로, 브라우저만 열되 그 가능성을 적어 둔다.
        say(f" 이미 {PORT} 포트에서 실행 중입니다. 브라우저만 엽니다.")
        say(" 원하는 팩이 아니라면 먼저 종료하세요 (stop 배치 파일).")
        webbrowser.open(f"{BASE}/admin")
        return 0

    if not ensure_venv():
        return 1

    # 모델이 먼저다 — 색인이 임베딩을 쓴다.
    ensure_embed_model()
    warn_if_no_ollama()
    ensure_index()

    if PACK:
        say(f"   팩         {PACK_DIR}")
        say(f"   운영 자료  {VAR_DIR}")
    say(f"   챗봇       {BASE}/")
    say(f"   관리자     {BASE}/admin")
    say(f"   API 문서   {BASE}/docs")
    say()
    say("   관리자 로그인은 .env 의 ADMIN_USERNAME / ADMIN_PASSWORD 입니다.")
    if not (ROOT / ".env").exists():
        say("   .env 가 없어 기본값으로 뜹니다 - admin / change-me")
    say()
    say("   종료: 이 창에서 Ctrl+C 또는 창 닫기")
    say(" ------------------------------------------------------------")
    say()

    threading.Thread(target=open_browser_when_ready, daemon=True).start()

    server = subprocess.Popen(
        [str(VENV_PYTHON), "-m", "uvicorn", "app.main:app", "--port", str(PORT), "--reload"],
        cwd=str(ROOT), env=child_env(),
    )
    try:
        return server.wait()
    except KeyboardInterrupt:
        # Ctrl+C 는 같은 콘솔의 자식에게도 전달된다. 여기서는 정리될 때까지 기다리기만 한다.
        server.wait()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
