import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Protocol

import numpy as np

BLOCK_SIZE = 480


class Player(Protocol):
    def enqueue(self, audio: np.ndarray, requested_at: float | None = None) -> None: ...

    def clear(self) -> None: ...

    def prepare(self) -> None: ...

    def is_idle(self) -> bool: ...

    def idle_seconds(self) -> float: ...

    def drain_latencies(self) -> list[float]: ...

    def close_if_idle(self) -> None: ...

    def close(self) -> None: ...


@dataclass
class _Chunk:
    audio: np.ndarray
    requested_at: float | None
    position: int = 0


class StreamPlayer:
    def __init__(self, sample_rate: int, close_after_idle_seconds: float = 30):
        self._sample_rate = sample_rate
        self._close_after_idle_seconds = close_after_idle_seconds
        self._chunks: deque[_Chunk] = deque()
        self._lock = threading.Lock()
        self._stream_lock = threading.Lock()
        self._stream = None
        self._last_audio_at = time.monotonic()
        self._latencies: deque[float] = deque(maxlen=64)

    def enqueue(self, audio: np.ndarray, requested_at: float | None = None) -> None:
        if audio.size == 0:
            return
        with self._lock:
            self._chunks.append(_Chunk(audio.astype(np.float32, copy=False), requested_at))
            self._last_audio_at = time.monotonic()
        self._ensure_stream()

    def clear(self) -> None:
        with self._lock:
            self._chunks.clear()

    def prepare(self) -> None:
        self._last_audio_at = time.monotonic()
        self._ensure_stream()

    def is_idle(self) -> bool:
        with self._lock:
            return not self._chunks

    def idle_seconds(self) -> float:
        return 0.0 if not self.is_idle() else time.monotonic() - self._last_audio_at

    def drain_latencies(self) -> list[float]:
        with self._lock:
            latencies = list(self._latencies)
            self._latencies.clear()
        return latencies

    def close_if_idle(self) -> None:
        if self._stream is not None and self.idle_seconds() > self._close_after_idle_seconds:
            self.close()

    def close(self) -> None:
        with self._stream_lock:
            stream, self._stream = self._stream, None
        if stream is not None:
            stream.abort()
            stream.close()

    def _ensure_stream(self) -> None:
        with self._stream_lock:
            if self._stream is not None:
                return
            import sounddevice

            stream = sounddevice.OutputStream(
                samplerate=self._sample_rate,
                channels=1,
                dtype="float32",
                blocksize=BLOCK_SIZE,
                latency="low",
                callback=self._fill,
            )
            stream.start()
            self._stream = stream

    def _fill(self, output, frames, _time, _status) -> None:
        output.fill(0)
        written = 0
        with self._lock:
            while written < frames and self._chunks:
                chunk = self._chunks[0]
                if chunk.position == 0 and chunk.requested_at is not None:
                    self._latencies.append(time.monotonic() - chunk.requested_at)
                take = min(frames - written, chunk.audio.size - chunk.position)
                output[written : written + take, 0] = chunk.audio[chunk.position : chunk.position + take]
                written += take
                chunk.position += take
                if chunk.position >= chunk.audio.size:
                    self._chunks.popleft()
            if written:
                self._last_audio_at = time.monotonic()
