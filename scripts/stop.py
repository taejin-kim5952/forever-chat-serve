"""실행 중인 서버를 끈다 — `stop.bat` 이 부른다.

창을 닫거나 Ctrl+C 로도 꺼지지만, 창을 최소화해 두고 잊어버리는 일이 잦다. 그 상태로 `실행.bat`
을 다시 누르면 "이미 18100 포트에서 실행 중"만 뜨고 새 코드가 안 올라간다. 그때 쓰는 것이 이
스크립트다.

**18100 포트를 잡고 있는 프로세스만** 끈다. 파이썬 프로세스를 이름으로 찾아 끄면 관계없는
작업(생성 배치, 다른 프로젝트)까지 같이 죽는다. `--reload` 로 띄우면 감시 프로세스와 서버
프로세스가 부모-자식으로 두 개이므로 `taskkill /T` 로 자식까지 함께 끝낸다.

인코딩 주의: 출력을 파일로 넘기면 파이썬이 cp949 로 인코딩하다 죽을 수 있어 UTF-8 로 고정한다
(`scripts/launch.py` 와 같은 이유).
"""

import re
import socket
import subprocess
import sys
import time

PORT = 18100

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def say(message: str = "") -> None:
    print(message, flush=True)


def is_serving() -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.3)
        return sock.connect_ex(("127.0.0.1", PORT)) == 0


def listening_pids() -> list[str]:
    """18100 을 LISTENING 상태로 잡고 있는 PID 목록.

    netstat 로 찾는다 — psutil 을 쓰면 의존성이 하나 늘고, 이 스크립트는 가상환경이 깨진
    상태에서도 돌아야 한다(그때가 오히려 서버를 꺼야 하는 상황이다).
    """
    result = subprocess.run(
        ["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True, errors="replace"
    )
    pids: list[str] = []
    for line in result.stdout.splitlines():
        if "LISTENING" not in line:
            continue
        # 로컬 주소 열이 ':18100' 으로 끝나는 줄만. ':181000' 같은 부분 일치를 막는다.
        if not re.search(rf"[:\.]{PORT}\s", line):
            continue
        pid = line.split()[-1]
        if pid.isdigit() and pid != "0" and pid not in pids:
            pids.append(pid)
    return pids


def main() -> int:
    say()
    say(" ============================================================")
    say("  API Manager 도우미 - 서버 종료")
    say(" ============================================================")
    say()

    if not is_serving():
        say(f" {PORT} 포트에서 실행 중인 서버가 없습니다.")
        return 0

    pids = listening_pids()
    if not pids:
        # 포트는 열려 있는데 소유자를 못 찾는 경우. 다른 계정으로 띄웠거나 권한이 모자란다.
        say(f" {PORT} 포트는 사용 중인데 프로세스를 찾지 못했습니다.")
        say(" 관리자 권한으로 다시 실행하거나, 서버 창에서 Ctrl+C 로 종료하세요.")
        return 1

    for pid in pids:
        # /T 로 자식까지, /F 로 강제 종료. --reload 는 감시 프로세스가 부모다.
        killed = subprocess.run(
            ["taskkill", "/PID", pid, "/T", "/F"], capture_output=True, text=True, errors="replace"
        )
        state = "종료" if killed.returncode == 0 else "실패"
        say(f" PID {pid} {state}")

    for _ in range(10):
        if not is_serving():
            say()
            say(" 서버를 종료했습니다.")
            return 0
        time.sleep(0.5)

    say()
    say(" 포트가 아직 열려 있습니다. 잠시 뒤 다시 시도하세요.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
