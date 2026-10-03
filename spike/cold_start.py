# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["mlx-audio", "misaki[en]", "espeakng-loader", "phonemizer-fork", "en-core-web-sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"]
# ///
import time

started = time.perf_counter()
from mlx_audio.tts.utils import load_model

imported = time.perf_counter()
model = load_model("mlx-community/Kokoro-82M-bf16")
loaded = time.perf_counter()
for lang_code, voice in (("e", "ef_dora"), ("a", "af_heart")):
    next(model.generate(text="Hola.", voice=voice, lang_code=lang_code))
warmed = time.perf_counter()
print(f"import={imported - started:.2f}s load={loaded - imported:.2f}s warm={warmed - loaded:.2f}s")
