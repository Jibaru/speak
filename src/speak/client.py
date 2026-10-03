import json
import os
import socket
import subprocess
import sys
import time

from speak.paths import Paths

REQUEST_TIMEOUT_SECONDS = 0.5
STARTUP_WAIT_SECONDS = 4.0
STARTUP_POLL_SECONDS = 0.05
MAX_LOG_BYTES = 1_000_000


class DaemonClient:
    def __init__(self, paths: Paths):
        self._paths = paths

    def request(self, message: dict, timeout: float = REQUEST_TIMEOUT_SECONDS) -> dict | None:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                connection.settimeout(timeout)
                connection.connect(str(self._paths.socket))
                connection.sendall(json.dumps(message).encode() + b"\n")
                return json.loads(_read_line(connection))
        except (OSError, ValueError):
            return None

    def send(self, message: dict, start_daemon: bool = False) -> dict | None:
        response = self.request(message)
        if response is not None or not start_daemon:
            return response
        self.spawn()
        deadline = time.monotonic() + STARTUP_WAIT_SECONDS
        while time.monotonic() < deadline:
            time.sleep(STARTUP_POLL_SECONDS)
            if (response := self.request(message)) is not None:
                return response
        return None

    def is_running(self) -> bool:
        return self.request({"op": "ping"}) is not None

    def ensure_running(self) -> bool:
        if self.is_running():
            return True
        self.spawn()
        return False

    def spawn(self) -> None:
        self._paths.home.mkdir(parents=True, exist_ok=True)
        if self._paths.log.exists() and self._paths.log.stat().st_size > MAX_LOG_BYTES:
            self._paths.log.unlink()
        with open(self._paths.log, "ab") as log:
            subprocess.Popen(
                [sys.executable, "-m", "speak", "daemon"],
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                start_new_session=True,
                env=os.environ.copy(),
            )


def _read_line(connection: socket.socket) -> bytes:
    data = b""
    while not data.endswith(b"\n"):
        chunk = connection.recv(65536)
        if not chunk:
            break
        data += chunk
    return data
