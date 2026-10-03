import subprocess
import tempfile
from pathlib import Path

import numpy as np

from speak.engines.base import resample
from speak.settings import Settings

CULTURES = {"en": "en-US", "es": "es-MX", "fr": "fr-FR", "it": "it-IT", "pt": "pt-BR"}
SCRIPT = """
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try { $synth.SelectVoiceByHints('NotSet', 'NotSet', 0, [Globalization.CultureInfo]'__CULTURE__') } catch {}
$synth.Rate = __RATE__
$synth.SetOutputToWaveFile('__OUTPUT__')
$synth.Speak([Console]::In.ReadToEnd())
$synth.Dispose()
"""


def build_script(lang: str, rate: float, output: Path) -> str:
    return (
        SCRIPT.replace("__CULTURE__", CULTURES.get(lang, "en-US"))
        .replace("__RATE__", str(max(-10, min(10, round((rate - 1) * 10)))))
        .replace("__OUTPUT__", str(output).replace("'", "''"))
    )


class SapiEngine:
    """Windows' built-in voices, used while the neural engine loads."""

    name = "sapi"

    def synthesize(self, text: str, lang: str, settings: Settings) -> np.ndarray:
        import soundfile

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "speech.wav"
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", build_script(lang, settings.rate, output)],
                input=text.encode("utf-8"),
                check=True,
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            audio, sample_rate = soundfile.read(output, dtype="float32")
        return resample(audio.reshape(-1) if audio.ndim == 1 else audio.mean(axis=1), sample_rate)
