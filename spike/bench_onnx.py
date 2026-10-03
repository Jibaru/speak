# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["kokoro-onnx", "soundfile"]
# ///
import time
from pathlib import Path

import soundfile as sf
from kokoro_onnx import Kokoro

from phrases import PHRASES, SPEED, VOICES

LANGS = {"es": "es", "en": "en-us"}
MODEL_DIR = Path(__file__).parent / "out" / "onnx-model"
OUT = Path(__file__).parent / "out" / "onnx"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    kokoro = Kokoro(str(MODEL_DIR / "kokoro-v1.0.onnx"), str(MODEL_DIR / "voices-v1.0.bin"))
    print(f"load: {time.perf_counter() - started:.2f}s")
    kokoro.create("Hola.", voice=VOICES["es"], speed=SPEED, lang="es")

    for index, (lang, text) in enumerate(PHRASES):
        started = time.perf_counter()
        audio, sample_rate = kokoro.create(text, voice=VOICES[lang], speed=SPEED, lang=LANGS[lang])
        total = time.perf_counter() - started
        duration = len(audio) / sample_rate
        sf.write(OUT / f"{index}-{lang}.wav", audio, sample_rate)
        print(f"[{lang}] first={total * 1000:.0f}ms audio={duration:.1f}s rtf={total / duration:.3f}")


if __name__ == "__main__":
    main()
