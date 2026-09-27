import subprocess
import time
from pathlib import Path

import requests

from config import (
    INDICF5_SERVER_DIR,
    INDICF5_SERVER_PYTHON,
    INDICF5_SERVER_SCRIPT,
    INDICF5_SERVER_URL,
)


SERVER_URL = INDICF5_SERVER_URL.rstrip("/")
HEALTH_URL = f"{SERVER_URL}/health"
SHUTDOWN_URL = f"{SERVER_URL}/shutdown"
STARTUP_TIMEOUT_SECONDS = 300
_SERVER_PROCESS = None


def is_server_running():
    try:
        response = requests.get(HEALTH_URL, timeout=2)
        if response.status_code != 200:
            return False
        payload = response.json()
        return payload.get("status") == "ok" and payload.get("engine") == "indicf5"
    except (requests.RequestException, ValueError):
        return False


def start_server(timeout=STARTUP_TIMEOUT_SECONDS):
    global _SERVER_PROCESS
    if is_server_running():
        print(f"IndicF5 server already running at {SERVER_URL}")
        return _SERVER_PROCESS

    server_dir = Path(INDICF5_SERVER_DIR)
    server_script = Path(INDICF5_SERVER_SCRIPT)
    server_python = Path(INDICF5_SERVER_PYTHON)
    if not server_script.is_file():
        raise FileNotFoundError(f"IndicF5 server script not found: {server_script}")
    if not server_python.is_file():
        raise FileNotFoundError(f"Movie explainer venv Python not found: {server_python}")

    log_path = server_dir / "indicf5_server.log"
    with log_path.open("a", encoding="utf-8") as log_file:
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        _SERVER_PROCESS = subprocess.Popen(
            [
                str(server_python),
                str(server_script),
                "--host",
                "127.0.0.1",
                "--port",
                "8765",
            ],
            cwd=str(server_dir),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=creation_flags,
        )

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_server_running():
            print(f"IndicF5 server is ready at {SERVER_URL}")
            return _SERVER_PROCESS
        if _SERVER_PROCESS.poll() is not None:
            try:
                details = log_path.read_text(encoding="utf-8", errors="replace")[-2000:]
            except OSError:
                details = "Server log could not be read."
            raise RuntimeError(f"IndicF5 server exited during startup.\n{details}")
        time.sleep(1)

    raise TimeoutError(
        f"IndicF5 server did not become healthy within {timeout} seconds. "
        f"See {log_path}."
    )


def stop_server(timeout=15):
    global _SERVER_PROCESS
    if not is_server_running():
        if _SERVER_PROCESS and _SERVER_PROCESS.poll() is not None:
            _SERVER_PROCESS = None
        print("IndicF5 server is not running.")
        return False

    response = requests.post(SHUTDOWN_URL, timeout=5)
    response.raise_for_status()
    if _SERVER_PROCESS is not None:
        try:
            _SERVER_PROCESS.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _SERVER_PROCESS.terminate()
            _SERVER_PROCESS.wait(timeout=5)
        _SERVER_PROCESS = None
    else:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and is_server_running():
            time.sleep(0.25)
    print("IndicF5 server shutdown requested.")
    return True