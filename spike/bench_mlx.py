# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["mlx-audio", "soundfile", "misaki[en]", "espeakng-loader", "phonemizer-fork", "en-core-web-sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"]
# ///
import time
from pathlib import Path

import numpy as np
import soundfile as sf
from mlx_audio.tts.utils import load_model

from phrases import PHRASES, SPEED, VOICES

LANG_CODES = {"es": "e", "en": "a"}
OUT = Path(__file__).parent / "out" / "mlx"


def synthesize(model, lang, text):
    started = time.perf_counter()
    first_chunk_at = None
    chunks = []
    for result in model.generate(text=text, voice=VOICES[lang], speed=SPEED, lang_code=LANG_CODES[lang]):
        if first_chunk_at is None:
            first_chunk_at = time.perf_counter()
        chunks.append(np.array(result.audio))
    finished = time.perf_counter()
    return np.concatenate(chunks), first_chunk_at - started, finished - started


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    model = load_model("mlx-community/Kokoro-82M-bf16")
    print(f"load: {time.perf_counter() - started:.2f}s")
    synthesize(model, "es", "Hola.")
    synthesize(model, "en", "Hello.")

    for index, (lang, text) in enumerate(PHRASES):
        audio, first, total = synthesize(model, lang, text)
        duration = len(audio) / 24000
        sf.write(OUT / f"{index}-{lang}.wav", audio, 24000)
        print(f"[{lang}] first={first * 1000:.0f}ms total={total * 1000:.0f}ms audio={duration:.1f}s rtf={total / duration:.3f}")


if __name__ == "__main__":
    main()
