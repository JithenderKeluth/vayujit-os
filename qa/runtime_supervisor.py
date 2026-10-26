"""Own/restart only the exact child API launched for a disposable QA installation."""

import os
import queue
import subprocess
import sys
import threading


def supervise(port: int, token: str) -> None:
    from qa.fixture_server import require_target

    require_target(f"vayujit_qa{token}_test", token)
    commands: queue.Queue[str] = queue.Queue()

    def read_parent() -> None:
        for line in sys.stdin:
            if line.strip() == f"restart:{token}":
                commands.put("restart")
        commands.put("stop")

    def start() -> subprocess.Popen[bytes]:
        return subprocess.Popen(
            [sys.executable, "-m", "qa.phase3_runtime", "--port", str(port), "--token", token],
            env=os.environ.copy(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def stop(child: subprocess.Popen[bytes]) -> None:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=10)

    threading.Thread(target=read_parent, daemon=True).start()
    child = start()
    try:
        while True:
            try:
                command = commands.get(timeout=0.25)
            except queue.Empty:
                if child.poll() is not None:
                    raise RuntimeError("QA_OWNED_API_EXITED") from None
                continue
            if command == "stop":
                break
            stop(child)
            child = start()
    finally:
        stop(child)
