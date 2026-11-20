"""Own the local service processes started by the Windows launcher."""

import json
import os
import signal
import subprocess
import sys
import time
import traceback
from contextlib import ExitStack
from pathlib import Path
from urllib.request import urlopen

from filelock import FileLock, Timeout

ROOT = Path(".local-run")
ORIGIN = "http://localhost:5173"


def read_health():
    with urlopen(ORIGIN + "/api/health", timeout=1) as response:
        return json.load(response)["mode"] == "demo"


def supervise():
    processes = []
    env = {**os.environ, "CULINARY_MODE": "demo", "CULINARY_DEPLOYMENT": "development", "APP_ORIGIN": ORIGIN,
           "CULINARY_DEMO_DATABASE_URL": "", "OLLAMA_MODEL": "", "CHROMA_HOST": "",
           "CULINARY_API_TARGET": "http://127.0.0.1:8000"}
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    commands = {
        "api": [sys.executable, "-m", "uvicorn", "backend.main:app", "--port", "8000"],
        "worker": [sys.executable, "-m", "backend.worker"],
        "web": ["node.exe", "node_modules/vite/bin/vite.js", "--host", "localhost", "--strictPort"],
    }
    with ExitStack() as resources:
        try:
            for name, command in commands.items():
                log = resources.enter_context((ROOT / (name + ".log")).open("ab"))
                processes.append(subprocess.Popen(command, env=env, creationflags=flags, stdout=log, stderr=log))
            deadline = time.monotonic() + 25
            while not (ROOT / "stop").exists():
                if any(p.poll() is not None for p in processes):
                    raise RuntimeError("A local service exited. Check its log.")
                if not (ROOT / "ready").exists():
                    try:
                        if read_health():
                            (ROOT / "ready").touch()
                    except (OSError, ValueError):
                        pass
                    if time.monotonic() > deadline:
                        raise RuntimeError("The demo API did not become ready through Vite.")
                time.sleep(0.25)
        finally:
            for p in processes:
                if p.poll() is None:
                    try:
                        p.send_signal(signal.CTRL_BREAK_EVENT if sys.platform == "win32" else signal.SIGTERM)
                    except OSError:
                        p.terminate()
            for p in processes:
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill()
                    p.wait()


def main():
    ROOT.mkdir(exist_ok=True)
    try:
        with FileLock(str(ROOT / "supervisor.lock"), timeout=0):
            for name in ("ready", "stop"):
                (ROOT / name).unlink(missing_ok=True)
            (ROOT / "owner").write_text(str(os.getpid()), encoding="ascii")
            try:
                supervise()
            except Exception:
                (ROOT / "supervisor.err").write_text(traceback.format_exc(), encoding="utf-8")
                raise
            finally:
                for name in ("ready", "stop", "owner"):
                    (ROOT / name).unlink(missing_ok=True)
    except Timeout:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
