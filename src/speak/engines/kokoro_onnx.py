import numpy as np

from speak.engines.base import concatenate, flatten
from speak.engines.download import ensure_file
from speak.engines.phonemizer import MixedPhonemizer
from speak.paths import Paths
from speak.settings import Settings
from speak.text.codeswitch import CodeSwitcher

RELEASE_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
MODEL_FILES = {"fp32": "kokoro-v1.0.onnx", "fp16": "kokoro-v1.0.fp16.onnx", "int8": "kokoro-v1.0.int8.onnx"}
VOICES_FILE = "voices-v1.0.bin"
PREFERRED_PROVIDERS = ("CUDAExecutionProvider", "DmlExecutionProvider", "CPUExecutionProvider")
LANGUAGES = ("en", "es", "fr", "it", "pt")


class KokoroOnnxEngine:
    name = "kokoro-onnx"

    def __init__(self, paths: Paths, switcher: CodeSwitcher, precision: str = "fp32"):
        self._paths = paths
        self._switcher = switcher
        self._precision = precision
        self._kokoro = None
        self._phonemizer: MixedPhonemizer | None = None

    def load(self) -> None:
        import onnxruntime
        from kokoro_onnx import Kokoro

        model = ensure_file(f"{RELEASE_URL}/{MODEL_FILES[self._precision]}", self._paths.models / MODEL_FILES[self._precision])
        voices = ensure_file(f"{RELEASE_URL}/{VOICES_FILE}", self._paths.models / VOICES_FILE)
        available = set(onnxruntime.get_available_providers())
        providers = [provider for provider in PREFERRED_PROVIDERS if provider in available]
        session = onnxruntime.InferenceSession(str(model), providers=providers)
        self._kokoro = Kokoro.from_session(session, str(voices))
        self._phonemizer = MixedPhonemizer(self._switcher)

    def warm(self, settings: Settings) -> None:
        for lang in LANGUAGES:
            self.synthesize("Ok.", lang, settings)

    def synthesize(self, text: str, lang: str, settings: Settings) -> np.ndarray:
        if self._kokoro is None or self._phonemizer is None:
            raise RuntimeError("Kokoro model is not loaded")
        lang = lang if lang in LANGUAGES else "en"
        voice = settings.voices[lang]
        chunks = []
        for phonemes in self._phonemizer.phonemize(text, lang):
            audio, _ = self._kokoro.create(phonemes, voice=voice, speed=settings.rate, is_phonemes=True)
            chunks.append(flatten(audio))
        return concatenate(chunks)
