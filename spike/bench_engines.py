import sys
import time
from pathlib import Path

import soundfile as sf

from speak.engines.kokoro_onnx import KokoroOnnxEngine
from speak.paths import Paths
from speak.settings import Settings
from speak.text.codeswitch import CodeSwitcher

PHRASES = [
    ("es", "Listo, hice el deploy del hook en TypeScript y los tests pasan."),
    ("es", "Encontré el bug: el useEffect no limpiaba el listener al desmontar el componente."),
    ("en", "Done. I refactored the parser and all tests are green."),
]
OUT = Path(__file__).parent / "out" / "engines"


def main(precision: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    engine = KokoroOnnxEngine(Paths.from_env(), CodeSwitcher(), precision)
    started = time.perf_counter()
    engine.load()
    settings = Settings()
    engine.warm(settings)
    print(f"[onnx-{precision}] load+warm {time.perf_counter() - started:.1f}s")
    for index, (lang, text) in enumerate(PHRASES):
        started = time.perf_counter()
        audio = engine.synthesize(text, lang, settings)
        elapsed = time.perf_counter() - started
        sf.write(OUT / f"{index}-onnx-{precision}.wav", audio, 24000)
        print(f"[onnx-{precision}] {elapsed * 1000:.0f}ms for {len(audio) / 24000:.1f}s audio")


if __name__ == "__main__":
    main(sys.argv[1])
