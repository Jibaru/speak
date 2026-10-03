import logging
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Protocol

import numpy as np

from speak.paths import Paths
from speak.settings import Settings

SAMPLE_RATE = 24000
KOKORO_MODEL = "mlx-community/Kokoro-82M-bf16"
KOKORO_LANG_CODES = {"en": "a", "es": "e", "fr": "f", "it": "i", "pt": "p"}
SAY_BASE_WORDS_PER_MINUTE = 190
ESPEAK_MAX_DATA_PATH = 120

log = logging.getLogger(__name__)


class Engine(Protocol):
    name: str

    def synthesize(self, text: str, lang: str, settings: Settings) -> np.ndarray: ...


class SayEngine:
    name = "say"

    def synthesize(self, text: str, lang: str, settings: Settings) -> np.ndarray:
        import soundfile

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "speech.wav"
            command = ["say", "-o", str(output), f"--data-format=LEF32@{SAMPLE_RATE}", "--file-format=WAVE"]
            command += ["-r", str(round(SAY_BASE_WORDS_PER_MINUTE * settings.rate))]
            if voice := settings.say_voices.get(lang):
                command += ["-v", voice]
            subprocess.run([*command, "--", text], check=True, capture_output=True)
            audio, _ = soundfile.read(output, dtype="float32")
        return audio


class KokoroEngine:
    name = "kokoro"

    def __init__(self, paths: Paths):
        self._paths = paths
        self._model = None

    def load(self) -> None:
        os.environ["HF_HOME"] = str(self._paths.huggingface)
        os.environ["HF_HUB_OFFLINE"] = "1" if self._paths.model_ready_marker.exists() else "0"
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        from huggingface_hub import snapshot_download
        from mlx_audio.tts.utils import load_model

        snapshot_download(KOKORO_MODEL)
        _shorten_espeak_data_path()
        self._model = load_model(KOKORO_MODEL)
        self._paths.model_ready_marker.touch()

    def warm(self, settings: Settings) -> None:
        for lang in KOKORO_LANG_CODES:
            self.synthesize("Ok.", lang, settings)

    def synthesize(self, text: str, lang: str, settings: Settings) -> np.ndarray:
        if self._model is None:
            raise RuntimeError("Kokoro model is not loaded")
        lang = lang if lang in KOKORO_LANG_CODES else "en"
        results = self._model.generate(
            text=text,
            voice=settings.voices[lang],
            speed=settings.rate,
            lang_code=KOKORO_LANG_CODES[lang],
        )
        chunks = [np.asarray(result.audio, dtype=np.float32) for result in results]
        return np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)


def _shorten_espeak_data_path() -> None:
    import espeakng_loader
    import misaki.espeak  # noqa: F401  (sets the default espeak data path on import)
    from phonemizer.backend.espeak.wrapper import EspeakWrapper

    data_path = Path(espeakng_loader.get_data_path())
    if len(str(data_path)) <= ESPEAK_MAX_DATA_PATH:
        return
    short_path = Path(tempfile.gettempdir()) / f"speak-espeak-{os.getuid()}"
    if not (short_path / "phontab").exists():
        staging = Path(tempfile.mkdtemp(prefix="speak-espeak-"))
        shutil.copytree(data_path, staging, dirs_exist_ok=True)
        shutil.rmtree(short_path, ignore_errors=True)
        staging.rename(short_path)
    EspeakWrapper.set_data_path(str(short_path))


class EngineManager:
    def __init__(self, paths: Paths, fallback: Engine | None = None):
        self._paths = paths
        self._fallback = fallback or SayEngine()
        self._primary: Engine | None = None
        self._loading = threading.Event()

    @property
    def current(self) -> Engine:
        return self._primary or self._fallback

    def load_in_background(self, settings: Settings) -> None:
        if self._loading.is_set():
            return
        self._loading.set()
        threading.Thread(target=self._load, args=(settings,), name="kokoro-loader", daemon=True).start()

    def _load(self, settings: Settings) -> None:
        try:
            engine = KokoroEngine(self._paths)
            engine.load()
            engine.warm(settings)
            self._primary = engine
            log.info("kokoro engine ready")
        except Exception:
            log.exception("kokoro engine failed to load, staying on say")

    def synthesize(self, text: str, lang: str, settings: Settings) -> np.ndarray:
        try:
            return self.current.synthesize(text, lang, settings)
        except Exception:
            if self.current is self._fallback:
                raise
            log.exception("primary engine failed, falling back to say")
            return self._fallback.synthesize(text, lang, settings)
