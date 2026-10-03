import json
import socket
import time
from dataclasses import dataclass

from speak.paths import Paths
from speak.system.process import background_python, spawn_detached

REQUEST_TIMEOUT_SECONDS = 0.5
STARTUP_WAIT_SECONDS = 4.0
STARTUP_POLL_SECONDS = 0.05
MAX_LOG_BYTES = 1_000_000


@dataclass(frozen=True)
class Endpoint:
    port: int
    token: str

    @classmethod
    def read(cls, paths: Paths) -> "Endpoint | None":
        try:
            data = json.loads(paths.endpoint.read_text())
            return cls(int(data["port"]), str(data["token"]))
        except (OSError, ValueError, KeyError):
            return None


class DaemonClient:
    def __init__(self, paths: Paths):
        self._paths = paths

    def request(self, message: dict, timeout: float = REQUEST_TIMEOUT_SECONDS) -> dict | None:
        endpoint = Endpoint.read(self._paths)
        if endpoint is None:
            return None
        try:
            with socket.create_connection(("127.0.0.1", endpoint.port), timeout=timeout) as connection:
                connection.sendall(json.dumps({**message, "token": endpoint.token}).encode() + b"\n")
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
        spawn_detached([background_python(), "-m", "speak", "daemon"], self._paths.log)


def _read_line(connection: socket.socket) -> bytes:
    data = b""
    while not data.endswith(b"\n"):
        chunk = connection.recv(65536)
        if not chunk:
            break
        data += chunk
    return data
