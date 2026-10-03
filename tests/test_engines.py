import numpy as np
import pytest

from speak.engines import registry
from speak.engines.manager import EngineManager
from speak.engines.phonemizer import MAX_PHONEMES, _chunk
from speak.settings import Settings


@pytest.mark.parametrize(
    ("platform", "machine", "expected"),
    [("darwin", "arm64", "kokoro-mlx"), ("darwin", "x86_64", "kokoro-onnx"), ("linux", "x86_64", "kokoro-onnx"), ("win32", "AMD64", "kokoro-onnx")],
)
def test_auto_engine_per_platform(monkeypatch, platform, machine, expected):
    monkeypatch.setattr(registry.sys, "platform", platform)
    monkeypatch.setattr(registry.platform, "machine", lambda: machine)
    assert registry.resolve_engine_name(Settings()) == expected


def test_explicit_engine_wins():
    assert registry.resolve_engine_name(Settings(engine="kokoro-onnx")) == "kokoro-onnx"


def test_phoneme_chunks_respect_model_limit():
    chunks = _chunk(" ".join(["ab"] * 400))
    assert len(chunks) > 1
    assert all(len(chunk) <= MAX_PHONEMES for chunk in chunks)


class Broken:
    name = "broken"

    def load(self):
        raise RuntimeError("no model")

    def warm(self, settings):
        pass


class Fallback:
    name = "fallback"

    def synthesize(self, text, lang, settings):
        return np.ones(3, dtype=np.float32)


def test_manager_uses_fallback_when_primary_fails_to_load():
    manager = EngineManager(Broken, Fallback())
    manager._load(Settings())
    assert manager.current.name == "fallback"
    assert manager.synthesize("hola", "es", Settings()).size == 3


def test_manager_without_any_engine_raises_after_load_fails():
    manager = EngineManager(Broken, None)
    manager._load(Settings())
    with pytest.raises(RuntimeError):
        manager.synthesize("hola", "es", Settings())
