import asyncio
import contextlib
import json
import logging
import os
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from speak import __version__
from speak.daemon.narrator import Narrator
from speak.daemon.player import Player
from speak.daemon.speaker import Speaker
from speak.paths import Paths
from speak.settings import Settings, SettingsStore
from speak.system.lock import InstanceLock, write_private
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


StopRequest = Callable[[str], None]


class Sidecar(Protocol):
    def start(self, settings: Settings, port: int, token: str, request_stop: StopRequest) -> None: ...

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
        self._narrator = Narrator(self._narrate, self._interrupted)
        self._sessions: dict[str, _Session] = {}
        self._last_spoken_session: str | None = None
        self._last_activity = time.monotonic()
        self._last_latency_ms: float | None = None
        self._shutdown = asyncio.Event()
        self._token = secrets.token_hex(16)

    async def run(self) -> None:
        lock = InstanceLock(self._paths.lock)
        if not lock.acquire():
            log.info("another daemon is already running")
            return
        try:
            await self._serve()
        finally:
            lock.release()

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
        loop = asyncio.get_running_loop()
        server = await asyncio.start_server(self._serve_client, host="127.0.0.1", port=0)
        port = server.sockets[0].getsockname()[1]
        write_private(self._paths.endpoint, json.dumps({"port": port, "token": self._token, "pid": os.getpid(), "version": __version__}))
        self._speaker.start()
        loop.run_in_executor(None, self._player.prepare)
        self._engines.load_in_background(self._settings)
        if self._sidecar:
            self._sidecar.start(self._settings, port, self._token, self._stop_from_thread(loop))
        housekeeping = loop.create_task(self._housekeep())
        log.info("daemon listening on 127.0.0.1:%s (pid %s)", port, os.getpid())
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
            self._paths.endpoint.unlink(missing_ok=True)
            log.info("daemon stopped")

    async def _serve_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            message = json.loads(await reader.readline())
            if not secrets.compare_digest(str(message.pop("token", "")), self._token):
                response = {"ok": False, "error": "unauthorized"}
            else:
                response = await self.handle(message)
        except Exception as error:
            log.exception("request failed")
            response = {"ok": False, "error": str(error)}
        writer.write(json.dumps(response).encode() + b"\n")
        with contextlib.suppress(ConnectionError):
            await writer.drain()
        writer.close()

    def _stop_from_thread(self, loop: asyncio.AbstractEventLoop) -> StopRequest:
        def request_stop(source: str) -> None:
            loop.call_soon_threadsafe(self._op_stop, {"source": source})

        return request_stop

    def _op_ping(self, _message: dict) -> None:
        return None

    def _op_prepare(self, _message: dict) -> None:
        asyncio.get_running_loop().run_in_executor(None, self._player.prepare)

    def _op_speak(self, message: dict) -> dict:
        self._settings = self._store.load()
        segments = self._segments(message.get("text", ""), message.get("mode", "full"))
        self._say(message.get("session"), segments, preempt=message.get("preempt", True))
        return {"ok": True, "segments": len(segments)}

    def _op_stop(self, message: dict) -> None:
        log.info("stop requested by %s", message.get("source", "client"))
        self._speaker.stop()

    def _op_watch(self, message: dict) -> None:
        self._settings = self._store.load()
        self._narrator.watch(message["session"], Path(message["transcript"]), message.get("offset"))

    def _op_finish(self, message: dict) -> None:
        self._narrator.finish(message["session"], message.get("text", ""))

    def _op_unwatch(self, message: dict) -> None:
        self._narrator.unwatch(message["session"])

    def _op_status(self, _message: dict) -> dict:
        return {
            "ok": True,
            "pid": os.getpid(),
            "version": __version__,
            "engine": self._engines.current.name if self._engines.current else "loading",
            "speaking": not self._speaker.is_idle(),
            "projects": sorted(self._active_projects()),
            "last_latency_ms": self._last_latency_ms,
        }

    def _op_shutdown(self, _message: dict) -> None:
        self.request_shutdown()

    def _segments(self, text: str, mode: str) -> list[Segment]:
        preparer = SpeechPreparer(Lexicon.load(self._paths.lexicon_file))
        return preparer.prepare(text, "brief" if mode == "brief" else "full")

    def _narrate(self, session: str, text: str) -> None:
        self._say(session, self._segments(text, "full"), preempt=False)

    def _interrupted(self, session: str) -> None:
        log.info("turn interrupted in session %s", session)
        self._speaker.stop()

    def _say(self, session: str | None, segments: list[Segment], preempt: bool) -> None:
        if not segments:
            return
        if self._needs_project_prefix(session):
            segments = [Segment(self._sessions[session].project, segments[0].lang), *segments]
        self._last_spoken_session = session
        log.info("speaking %d segments (%s): %s", len(segments), segments[0].lang, segments[0].text[:80])
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
