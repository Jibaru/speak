import logging
import threading
from collections.abc import Callable
from typing import Protocol

from speak.settings import Settings

StopRequest = Callable[[str], None]

log = logging.getLogger(__name__)


class Watcher(Protocol):
    name: str

    def run(self, settings: Settings, request_stop: StopRequest, stopped: threading.Event) -> None: ...


class BackgroundInterrupts:
    """Runs interrupt watchers on daemon threads inside the voice daemon."""

    def __init__(self, watchers: list[Watcher]):
        self._watchers = watchers
        self._stopped = threading.Event()

    def start(self, settings: Settings, port: int, token: str, request_stop: StopRequest) -> None:
        for watcher in self._watchers:
            threading.Thread(
                target=self._run, args=(watcher, settings, request_stop), name=watcher.name, daemon=True
            ).start()

    def stop(self) -> None:
        self._stopped.set()

    def _run(self, watcher: Watcher, settings: Settings, request_stop: StopRequest) -> None:
        try:
            watcher.run(settings, request_stop, self._stopped)
        except Exception:
            log.exception("%s stopped working", watcher.name)


class EdgeTrigger:
    """Fires once each time a polled condition turns true."""

    def __init__(self):
        self._was_active = False

    def update(self, active: bool) -> bool:
        fired = active and not self._was_active
        self._was_active = active
        return fired
