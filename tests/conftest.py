import shutil
import tempfile
import time
from pathlib import Path

import numpy as np
import pytest

from speak.paths import Paths


@pytest.fixture
def paths():
    home = Path(tempfile.mkdtemp(prefix="speak-", dir="/tmp"))
    yield Paths(home=home / "home", config=home / "config", plugin_root=home / "plugin")
    shutil.rmtree(home, ignore_errors=True)


class FakeEngine:
    name = "fake"

    def __init__(self, delay: float = 0.0):
        self.spoken: list[tuple[str, str]] = []
        self.delay = delay

    def synthesize(self, text, lang, settings):
        time.sleep(self.delay)
        self.spoken.append((text, lang))
        return np.ones(10, dtype=np.float32)


class FakeEngines:
    def __init__(self, engine: FakeEngine | None = None):
        self.engine = engine or FakeEngine()
        self.loaded = False

    @property
    def current(self):
        return self.engine

    def load_in_background(self, settings):
        self.loaded = True

    def synthesize(self, text, lang, settings):
        return self.engine.synthesize(text, lang, settings)


class FakePlayer:
    def __init__(self):
        self.played: list[np.ndarray] = []
        self.cleared = 0
        self.closed = False

    def enqueue(self, audio, requested_at=None):
        self.played.append(audio)

    def clear(self):
        self.cleared += 1

    def is_idle(self):
        return True

    def idle_seconds(self):
        return 0.0

    def drain_latencies(self):
        return []

    def close_if_idle(self):
        pass

    def close(self):
        self.closed = True


@pytest.fixture
def fake_engines():
    return FakeEngines()


@pytest.fixture
def fake_player():
    return FakePlayer()
