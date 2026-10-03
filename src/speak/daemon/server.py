import asyncio
import contextlib
import fcntl
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from speak.daemon.narrator import Narrator
from speak.daemon.player import Player
from speak.daemon.speaker import Speaker
from speak.paths import Paths
from speak.settings import Settings, SettingsStore
from speak.text.lexicon import Lexicon
from speak.text.speech import Segment, SpeechPreparer

HOUSEKEEPING_SECONDS = 1.0
ACTIVE_SESSION_SECONDS = 15 * 60

log = logging.getLogger(__name__)


class Engines(Protocol):
    @property
    def current(self): ...

    def load_in_background(self, settings: Settings) -> None: ...

    def synthesize(self, text: str, lang: str, settings: Settings) -> np.ndarray: ...


class Sidecar(Protocol):
    def start(self, settings: Settings) -> None: ...

    def stop(self) -> None: ...


@dataclass
class _Session:
    project: str
    last_seen: float


class Daemon:
    def __init__(self, paths: Paths, engines: Engines, player: Player, sidecar: Sidecar | None = None):
        self._paths = paths
        self._store = SettingsStore(paths)
        self._engines = engines
        self._player = player
        self._sidecar = sidecar
        self._settings = self._store.load()
        self._speaker = Speaker(self._synthesize, player)
        self._narrator = Narrator(self._narrate)
        self._sessions: dict[str, _Session] = {}
        self._last_spoken_session: str | None = None
        self._last_activity = time.monotonic()
        self._last_latency_ms: float | None = None
        self._shutdown = asyncio.Event()

    async def run(self) -> None:
        self._paths.home.mkdir(parents=True, exist_ok=True)
        with open(self._paths.lock, "w") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                log.info("another daemon is already running")
                return
            await self._serve()

    def request_shutdown(self) -> None:
        self._shutdown.set()

    async def handle(self, message: dict) -> dict:
        self._last_activity = time.monotonic()
        self._touch_session(message)
        operation = message.get("op")
        handler = getattr(self, f"_op_{operation}", None)
        if handler is None:
            return {"ok": False, "error": f"unknown op {operation!r}"}
        return handler(message) or {"ok": True}

    async def _serve(self) -> None:
        self._paths.socket.unlink(missing_ok=True)
        server = await asyncio.start_unix_server(self._serve_client, path=str(self._paths.socket))
        os.chmod(self._paths.socket, 0o600)
        self._speaker.start()
        asyncio.get_running_loop().run_in_executor(None, self._player.prepare)
        self._engines.load_in_background(self._settings)
        if self._sidecar:
            self._sidecar.start(self._settings)
        housekeeping = asyncio.get_running_loop().create_task(self._housekeep())
        log.info("daemon listening on %s (pid %s)", self._paths.socket, os.getpid())
        try:
            await self._shutdown.wait()
        finally:
            housekeeping.cancel()
            server.close()
            await server.wait_closed()
            await self._speaker.close()
            self._player.close()
            if self._sidecar:
                self._sidecar.stop()
            self._paths.socket.unlink(missing_ok=True)
            log.info("daemon stopped")

    async def _serve_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            line = await reader.readline()
            response = await self.handle(json.loads(line))
        except Exception as error:
            log.exception("request failed")
            response = {"ok": False, "error": str(error)}
        writer.write(json.dumps(response).encode() + b"\n")
        with contextlib.suppress(ConnectionError):
            await writer.drain()
        writer.close()

    def _op_ping(self, _message: dict) -> None:
        return None

    def _op_prepare(self, _message: dict) -> None:
        asyncio.get_running_loop().run_in_executor(None, self._player.prepare)

    def _op_speak(self, message: dict) -> dict:
        self._settings = self._store.load()
        segments = self._prepare(message.get("text", ""), message.get("mode", "full"))
        self._say(message.get("session"), segments, preempt=message.get("preempt", True))
        return {"ok": True, "segments": len(segments)}

    def _op_stop(self, message: dict) -> None:
        log.info("stop requested by %s", message.get("source", "client"))
        self._speaker.stop()

    def _op_watch(self, message: dict) -> None:
        self._settings = self._store.load()
        self._narrator.watch(message["session"], Path(message["transcript"]), message.get("offset"))

    def _op_finish(self, message: dict) -> None:
        self._narrator.finish(message["session"])

    def _op_unwatch(self, message: dict) -> None:
        self._narrator.unwatch(message["session"])

    def _op_reload(self, _message: dict) -> None:
        self._settings = self._store.load()

    def _op_status(self, _message: dict) -> dict:
        return {
            "ok": True,
            "pid": os.getpid(),
            "engine": self._engines.current.name,
            "speaking": not self._speaker.is_idle(),
            "projects": sorted(self._active_projects()),
            "last_latency_ms": self._last_latency_ms,
        }

    def _op_shutdown(self, _message: dict) -> None:
        self.request_shutdown()

    def _prepare(self, text: str, mode: str) -> list[Segment]:
        preparer = SpeechPreparer(Lexicon.load(self._paths.lexicon_file))
        return preparer.prepare(text, "brief" if mode == "brief" else "full")

    def _narrate(self, session: str, text: str) -> None:
        self._say(session, self._prepare(text, "full"), preempt=False)

    def _say(self, session: str | None, segments: list[Segment], preempt: bool) -> None:
        if not segments:
            return
        if self._needs_project_prefix(session):
            segments = [Segment(self._sessions[session].project, segments[0].lang), *segments]
        self._last_spoken_session = session
        self._speaker.speak(segments, preempt=preempt)

    def _needs_project_prefix(self, session: str | None) -> bool:
        return (
            session in self._sessions
            and session != self._last_spoken_session
            and len(self._active_projects()) > 1
        )

    def _touch_session(self, message: dict) -> None:
        session, project = message.get("session"), message.get("project")
        if session and project:
            self._sessions[session] = _Session(project, time.monotonic())

    def _active_projects(self) -> set[str]:
        horizon = time.monotonic() - ACTIVE_SESSION_SECONDS
        return {info.project for info in self._sessions.values() if info.last_seen >= horizon}

    def _synthesize(self, segment: Segment) -> np.ndarray:
        return self._engines.synthesize(segment.text, segment.lang, self._settings)

    async def _housekeep(self) -> None:
        while True:
            await asyncio.sleep(HOUSEKEEPING_SECONDS)
            for latency in self._player.drain_latencies():
                self._last_latency_ms = round(latency * 1000)
                log.info("first audio latency %sms", self._last_latency_ms)
            self._player.close_if_idle()
            if not self._speaker.is_idle():
                self._last_activity = time.monotonic()
            idle_limit = self._settings.idle_minutes * 60
            if time.monotonic() - self._last_activity > idle_limit and not self._narrator.watching:
                log.info("idle for %s minutes, shutting down", self._settings.idle_minutes)
                self.request_shutdown()
