import os

import numpy as np

from speak.engines.base import concatenate, flatten
from speak.engines.phonemizer import MixedPhonemizer
from speak.paths import Paths
from speak.settings import Settings
from speak.text.codeswitch import CodeSwitcher

MODEL = "mlx-community/Kokoro-82M-bf16"
LANG_CODES = {"en": "a", "es": "e", "fr": "f", "it": "i", "pt": "p"}


class KokoroMlxEngine:
    name = "kokoro-mlx"

    def __init__(self, paths: Paths, switcher: CodeSwitcher):
        self._paths = paths
        self._switcher = switcher
        self._model = None
        self._phonemizer: MixedPhonemizer | None = None

    def load(self) -> None:
        os.environ["HF_HOME"] = str(self._paths.huggingface)
        os.environ["HF_HUB_OFFLINE"] = "1" if self._paths.model_ready_marker.exists() else "0"
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        from huggingface_hub import snapshot_download
        from mlx_audio.tts.utils import load_model

        snapshot_download(MODEL)
        self._phonemizer = MixedPhonemizer(self._switcher)
        self._model = load_model(MODEL)
        self._paths.model_ready_marker.touch()

    def warm(self, settings: Settings) -> None:
        for lang in LANG_CODES:
            self.synthesize("Ok.", lang, settings)

    def synthesize(self, text: str, lang: str, settings: Settings) -> np.ndarray:
        if self._model is None or self._phonemizer is None:
            raise RuntimeError("Kokoro model is not loaded")
        lang = lang if lang in LANG_CODES else "en"
        pipeline = self._model._get_pipeline(LANG_CODES[lang])
        voice = settings.voices[lang]
        return concatenate(
            [
                flatten(result.output.audio)
                for phonemes in self._phonemizer.phonemize(text, lang)
                for result in pipeline.generate_from_tokens(phonemes, voice=voice, speed=settings.rate)
            ]
        )
