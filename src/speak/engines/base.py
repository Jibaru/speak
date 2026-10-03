from typing import Protocol

import numpy as np

from speak.settings import Settings

SAMPLE_RATE = 24000


class Engine(Protocol):
    name: str

    def synthesize(self, text: str, lang: str, settings: Settings) -> np.ndarray: ...


class LoadableEngine(Engine, Protocol):
    def load(self) -> None: ...

    def warm(self, settings: Settings) -> None: ...


def flatten(audio) -> np.ndarray:
    return np.asarray(audio, dtype=np.float32).reshape(-1)


def concatenate(chunks: list[np.ndarray]) -> np.ndarray:
    return np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)


def resample(audio: np.ndarray, source_rate: int, target_rate: int = SAMPLE_RATE) -> np.ndarray:
    if source_rate == target_rate or audio.size == 0:
        return audio.astype(np.float32, copy=False)
    duration = audio.size / source_rate
    target_times = np.arange(round(duration * target_rate)) / target_rate
    source_times = np.arange(audio.size) / source_rate
    return np.interp(target_times, source_times, audio).astype(np.float32)
