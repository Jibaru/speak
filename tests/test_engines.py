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


def test_resample_preserves_duration():
    from speak.engines.base import resample

    audio = np.sin(np.linspace(0, 100, 22050)).astype(np.float32)
    resampled = resample(audio, 22050, 24000)
    assert resampled.size == 24000
    assert resampled.dtype == np.float32


def test_sapi_script_embeds_culture_rate_and_escaped_path(tmp_path):
    from speak.engines.sapi import build_script

    script = build_script("es", 1.15, tmp_path / "it's.wav")
    assert "[Globalization.CultureInfo]'es-MX'" in script
    assert "$synth.Rate = 1" in script
    assert "it''s.wav" in script
    assert "catch {}" in script
