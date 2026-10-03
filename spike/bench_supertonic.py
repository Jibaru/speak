# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["supertonic", "soundfile"]
# ///
import inspect
import time
from pathlib import Path

import numpy as np
import soundfile as sf
from supertonic import TTS

PHRASES = [
    ("es", "Listo, hice el deploy del hook en TypeScript y los tests pasan."),
    ("es", "Encontré el bug: el useEffect no limpiaba el listener al desmontar el componente."),
    ("en", "Done. I refactored the parser and all tests are green."),
]
OUT = Path(__file__).parent / "out" / "engines"

print(inspect.signature(TTS.__init__))
print(inspect.signature(TTS.synthesize))
started = time.perf_counter()
tts = TTS()
print(f"load {time.perf_counter() - started:.1f}s")
style = tts.get_voice_style("F1") if hasattr(tts, "get_voice_style") else None
tts.synthesize("Hola.", voice_style=style, lang="es")
OUT.mkdir(parents=True, exist_ok=True)
for index, (lang, text) in enumerate(PHRASES):
    started = time.perf_counter()
    wav, duration = tts.synthesize(text, voice_style=style, lang=lang)
    elapsed = time.perf_counter() - started
    tts.save_audio(wav, str(OUT / f"{index}-supertonic.wav"))
    print(f"[supertonic] {elapsed * 1000:.0f}ms for {float(np.asarray(duration).reshape(-1)[0]):.1f}s audio")
