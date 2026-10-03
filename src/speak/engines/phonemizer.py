import os
import shutil
import tempfile
from pathlib import Path

from speak.text.codeswitch import ENGLISH, CodeSwitcher

ESPEAK_VOICES = {"es": "es-419", "fr": "fr-fr", "it": "it", "pt": "pt-br"}
MAX_PHONEMES = 500
ESPEAK_MAX_DATA_PATH = 120


class MixedPhonemizer:
    """Phonemizes each run of a sentence with the G2P of its own language.

    Kokoro shares one phoneme inventory across languages, so English words inside a
    Spanish sentence can be voiced with English phonemes by the Spanish voice.
    """

    def __init__(self, switcher: CodeSwitcher):
        _use_short_espeak_data_path()
        from misaki import en, espeak

        self._switcher = switcher
        self._espeak_module = espeak
        self._english = en.G2P(trf=False, british=False, fallback=espeak.EspeakFallback(british=False), unk="")
        self._native: dict[str, object] = {}

    def phonemize(self, text: str, lang: str) -> list[str]:
        parts = []
        for run in self._switcher.runs(text, lang):
            phonemes, _ = self._g2p(run.lang)(run.text)
            if phonemes and phonemes.strip():
                parts.append(phonemes.strip())
        return _chunk(" ".join(parts))

    def _g2p(self, lang: str):
        if lang == ENGLISH:
            return self._english
        if lang not in self._native:
            self._native[lang] = self._espeak_module.EspeakG2P(language=ESPEAK_VOICES.get(lang, lang))
        return self._native[lang]


def _chunk(phonemes: str) -> list[str]:
    chunks: list[str] = []
    while len(phonemes) > MAX_PHONEMES:
        cut = phonemes.rfind(" ", 0, MAX_PHONEMES)
        cut = cut if cut > 0 else MAX_PHONEMES
        chunks.append(phonemes[:cut])
        phonemes = phonemes[cut:].lstrip()
    if phonemes:
        chunks.append(phonemes)
    return chunks


def _use_short_espeak_data_path() -> None:
    """espeak-ng truncates long data paths, and phonemizer resolves symlinks, so copy instead."""
    import espeakng_loader
    import misaki.espeak  # noqa: F401  (sets the default espeak data path on import)
    from phonemizer.backend.espeak.wrapper import EspeakWrapper

    data_path = Path(espeakng_loader.get_data_path())
    if len(str(data_path)) <= ESPEAK_MAX_DATA_PATH:
        return
    short_path = Path(tempfile.gettempdir()) / f"speak-espeak-{_user_id()}"
    if not (short_path / "phontab").exists():
        staging = Path(tempfile.mkdtemp(prefix="speak-espeak-"))
        shutil.copytree(data_path, staging, dirs_exist_ok=True)
        shutil.rmtree(short_path, ignore_errors=True)
        staging.rename(short_path)
    EspeakWrapper.set_data_path(str(short_path))


def _user_id() -> str:
    return str(os.getuid()) if hasattr(os, "getuid") else os.environ.get("USERNAME", "user")
