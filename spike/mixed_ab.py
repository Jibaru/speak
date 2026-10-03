import re
from pathlib import Path

import numpy as np
import soundfile as sf
from mlx_audio.tts.utils import load_model
from wordfreq import zipf_frequency

OUT = Path(__file__).parent / "out" / "mixed"
PHRASES = [
    "Listo, hice el deploy del hook en TypeScript y los tests pasan.",
    "Encontré el bug: el useEffect no limpiaba el listener al desmontar el componente.",
    "Revisa el pull request, cambié el endpoint y el cache del token.",
    "Hice merge del branch de la feature y corrí el build en staging.",
]
CAMEL = re.compile(r"[a-z][A-Z]")
TOKEN = re.compile(r"[\w'-]+|[^\w\s]")


def is_english(word: str) -> bool:
    if CAMEL.search(word):
        return True
    en, es = zipf_frequency(word, "en"), zipf_frequency(word, "es")
    return en >= 2.5 and en - es >= 0.5


def runs(sentence: str):
    current, words = None, []
    for token in TOKEN.findall(sentence):
        lang = "en" if token[0].isalpha() and is_english(token) else ("es" if token[0].isalpha() else current or "es")
        if lang != current and words:
            yield current, " ".join(words)
            words = []
        current = lang
        words.append(token)
    if words:
        yield current, " ".join(words)


def phonemize(model, sentence: str, spanish_g2p=None) -> str:
    es, en = model._get_pipeline("e"), model._get_pipeline("a")
    parts = []
    for lang, text in runs(sentence):
        g2p = en.g2p if lang == "en" else (spanish_g2p or es.g2p)
        phonemes, _ = g2p(text)
        parts.append(phonemes.strip())
        print(f"   [{lang}] {text!r} -> {phonemes.strip()}")
    return " ".join(parts)


def audio(array) -> np.ndarray:
    return np.asarray(array, dtype=np.float32).reshape(-1)


def synth(pipeline, phonemes: str) -> np.ndarray:
    return np.concatenate([audio(r.output.audio) for r in pipeline.generate_from_tokens(phonemes, voice="ef_dora", speed=1.15)])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    model = load_model("mlx-community/Kokoro-82M-bf16")
    pipeline = model._get_pipeline("e")
    from misaki.espeak import EspeakG2P
    latam = EspeakG2P(language="es-419")
    for index, sentence in enumerate(PHRASES):
        print(sentence)
        current = np.concatenate([np.asarray(r.audio) for r in model.generate(text=sentence, voice="ef_dora", lang_code="e", speed=1.15)])
        mixed_ps = phonemize(model, sentence)
        latam_ps = phonemize(model, sentence, latam)
        sf.write(OUT / f"{index}-a-current.wav", audio(current), 24000)
        sf.write(OUT / f"{index}-b-mixed.wav", synth(pipeline, mixed_ps), 24000)
        sf.write(OUT / f"{index}-c-mixed-latam.wav", synth(pipeline, latam_ps), 24000)


main()
