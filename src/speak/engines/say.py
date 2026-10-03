import subprocess
import tempfile
from pathlib import Path

import numpy as np

from speak.engines.base import SAMPLE_RATE
from speak.settings import Settings

BASE_WORDS_PER_MINUTE = 190


class SayEngine:
    name = "say"

    def synthesize(self, text: str, lang: str, settings: Settings) -> np.ndarray:
        import soundfile

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "speech.wav"
            command = ["say", "-o", str(output), f"--data-format=LEF32@{SAMPLE_RATE}", "--file-format=WAVE"]
            command += ["-r", str(round(BASE_WORDS_PER_MINUTE * settings.rate))]
            if voice := settings.say_voices.get(lang):
                command += ["-v", voice]
            subprocess.run([*command, "--", text], check=True, capture_output=True)
            audio, _ = soundfile.read(output, dtype="float32")
        return audio
