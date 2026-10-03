import os
import platform
import shutil
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass

from speak.client import DaemonClient
from speak.paths import Paths
from speak.settings import SettingsStore

SAMPLE = "Speak doctor: la voz funciona y el deploy del hook suena bien."
LATENCY_WAIT_SECONDS = 20


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str
    optional: bool = False


class Doctor:
    def __init__(self, paths: Paths):
        self._paths = paths
        self._store = SettingsStore(paths)
        self._client = DaemonClient(paths)

    def run(self, report: Callable[[Check], None]) -> bool:
        checks = [self._platform, self._engine, self._audio, self._daemon, self._speech, self._hotkey, self._microphone]
        results = []
        for check in checks:
            try:
                result = check()
            except Exception as error:
                result = Check(check.__name__.strip("_"), False, f"{type(error).__name__}: {error}")
            report(result)
            results.append(result)
        return all(result.ok or result.optional for result in results)

    def _platform(self) -> Check:
        detail = f"{platform.system()} {platform.release()} {platform.machine()}, Python {platform.python_version()}"
        return Check("platform", True, f"{detail}, plugin at {self._paths.plugin_root}")

    def _engine(self) -> Check:
        from speak.engines import registry

        settings = self._store.load()
        name = registry.resolve_engine_name(settings)
        fallback = registry.create_fallback()
        return Check("engine", True, f"{name} (fallback: {fallback.name if fallback else 'none'})")

    def _audio(self) -> Check:
        from speak.daemon.player import create_player

        player = create_player(24000)
        backend = type(player).__name__
        if backend == "SounddevicePlayer":
            import sounddevice

            device = sounddevice.query_devices(kind="output")["name"]
            return Check("audio", True, f"{backend} → {device}")
        return Check("audio", True, backend)

    def _daemon(self) -> Check:
        response = self._client.send({"op": "ping"}, start_daemon=True)
        if response is None:
            return Check("daemon", False, f"did not start, see {self._paths.log}")
        status = self._client.request({"op": "status"}) or {}
        return Check("daemon", True, f"pid {status.get('pid')}, engine {status.get('engine')}")

    def _speech(self) -> Check:
        before = (self._client.request({"op": "status"}) or {}).get("last_latency_ms")
        response = self._client.request({"op": "speak", "text": SAMPLE, "mode": "full"})
        if not response or not response.get("ok"):
            return Check("speech", False, f"speak request failed: {response}")
        deadline = time.monotonic() + LATENCY_WAIT_SECONDS
        while time.monotonic() < deadline:
            time.sleep(0.25)
            status = self._client.request({"op": "status"}) or {}
            latency = status.get("last_latency_ms")
            if latency is not None and latency != before:
                return Check("speech", True, f"first audio after {latency} ms with {status.get('engine')}")
        return Check("speech", False, "no audio was played (still downloading the model?)")

    def _hotkey(self) -> Check:
        settings = self._store.load()
        if sys.platform == "darwin":
            exists = self._paths.helper_binary.exists()
            return Check("hotkey", exists, f"{settings.hotkey} via {self._paths.helper_binary}", optional=True)
        if sys.platform == "win32":
            return Check("hotkey", True, f"{settings.hotkey} via RegisterHotKey (see daemon log for registration)", optional=True)
        has_x11 = "DISPLAY" in os.environ
        detail = f"{settings.hotkey} via X11" if has_x11 else "no X11: bind `speak stop` to a shortcut"
        return Check("hotkey", has_x11, detail, optional=True)

    def _microphone(self) -> Check:
        settings = self._store.load()
        if not settings.stop_on_mic:
            return Check("microphone", True, "disabled in config")
        if sys.platform == "win32":
            from speak.interrupts.windows import microphone_in_use

            return Check("microphone", True, f"consent registry readable, in use now: {microphone_in_use()}", optional=True)
        if sys.platform == "linux":
            pactl = shutil.which("pactl")
            return Check("microphone", bool(pactl), "pactl" if pactl else "pactl not found", optional=True)
        return Check("microphone", self._paths.helper_binary.exists(), "CoreAudio via native helper", optional=True)
