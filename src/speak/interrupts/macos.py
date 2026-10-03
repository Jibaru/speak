import logging
import subprocess

from speak.paths import Paths
from speak.settings import Settings

log = logging.getLogger(__name__)


class MacHelper:
    def __init__(self, paths: Paths):
        self._paths = paths
        self._process: subprocess.Popen | None = None

    def start(self, settings: Settings, port: int, token: str, request_stop) -> None:
        binary = self._paths.helper_binary
        if not binary.exists():
            log.warning("native helper not found at %s, hotkey and mic detection disabled", binary)
            return
        command = [str(binary), "--port", str(port), "--token", token, "--hotkey", settings.hotkey]
        if settings.stop_on_mic:
            command.append("--stop-on-mic")
        self._process = subprocess.Popen(command, stdin=subprocess.DEVNULL)
        log.info("native helper started (pid %s)", self._process.pid)

    def stop(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.terminate()
