import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Protocol

import numpy as np

BLOCK_FRAMES = 480
CLOSE_AFTER_IDLE_SECONDS = 30

log = logging.getLogger(__name__)


class Player(Protocol):
    def enqueue(self, audio: np.ndarray, requested_at: float | None = None) -> None: ...

    def clear(self) -> None: ...

    def prepare(self) -> None: ...

    def is_idle(self) -> bool: ...

    def drain_latencies(self) -> list[float]: ...

    def close_if_idle(self) -> None: ...

    def close(self) -> None: ...


@dataclass
class _Chunk:
    audio: np.ndarray
    requested_at: float | None
    position: int = 0


class AudioBuffer:
    """Thread-safe queue of audio chunks read by the audio callback."""

    def __init__(self):
        self._chunks: deque[_Chunk] = deque()
        self._lock = threading.Lock()
        self._latencies: deque[float] = deque(maxlen=64)
        self.last_audio_at = time.monotonic()

    def push(self, audio: np.ndarray, requested_at: float | None) -> None:
        with self._lock:
            self._chunks.append(_Chunk(audio.astype(np.float32, copy=False), requested_at))
            self.last_audio_at = time.monotonic()

    def clear(self) -> None:
        with self._lock:
            self._chunks.clear()

    def is_empty(self) -> bool:
        with self._lock:
            return not self._chunks

    def drain_latencies(self) -> list[float]:
        with self._lock:
            latencies = list(self._latencies)
            self._latencies.clear()
        return latencies

    def read_into(self, output: np.ndarray) -> None:
        output.fill(0)
        frames, written = output.shape[0], 0
        with self._lock:
            while written < frames and self._chunks:
                chunk = self._chunks[0]
                if chunk.position == 0 and chunk.requested_at is not None:
                    self._latencies.append(time.monotonic() - chunk.requested_at)
                take = min(frames - written, chunk.audio.size - chunk.position)
                output[written : written + take] = chunk.audio[chunk.position : chunk.position + take]
                written += take
                chunk.position += take
                if chunk.position >= chunk.audio.size:
                    self._chunks.popleft()
            if written:
                self.last_audio_at = time.monotonic()


class BufferedPlayer:
    def __init__(self, sample_rate: int):
        self._sample_rate = sample_rate
        self._buffer = AudioBuffer()
        self._stream_lock = threading.Lock()
        self._stream = None

    def enqueue(self, audio: np.ndarray, requested_at: float | None = None) -> None:
        if audio.size == 0:
            return
        self._buffer.push(audio, requested_at)
        self.prepare()

    def clear(self) -> None:
        self._buffer.clear()

    def prepare(self) -> None:
        with self._stream_lock:
            if self._stream is None:
                self._stream = self._open()
        self._buffer.last_audio_at = max(self._buffer.last_audio_at, time.monotonic())

    def is_idle(self) -> bool:
        return self._buffer.is_empty()

    def drain_latencies(self) -> list[float]:
        return self._buffer.drain_latencies()

    def close_if_idle(self) -> None:
        idle_for = time.monotonic() - self._buffer.last_audio_at
        if self._stream is not None and self.is_idle() and idle_for > CLOSE_AFTER_IDLE_SECONDS:
            self.close()

    def close(self) -> None:
        with self._stream_lock:
            stream, self._stream = self._stream, None
        if stream is not None:
            self._close(stream)

    def _open(self):
        raise NotImplementedError

    def _close(self, stream) -> None:
        raise NotImplementedError


class SounddevicePlayer(BufferedPlayer):
    def _open(self):
        import sounddevice

        stream = sounddevice.OutputStream(
            samplerate=self._sample_rate,
            channels=1,
            dtype="float32",
            blocksize=BLOCK_FRAMES,
            latency="low",
            callback=lambda output, _frames, _time, _status: self._buffer.read_into(output[:, 0]),
        )
        stream.start()
        return stream

    def _close(self, stream) -> None:
        stream.abort()
        stream.close()


class MiniaudioPlayer(BufferedPlayer):
    def _open(self):
        import miniaudio

        device = miniaudio.PlaybackDevice(
            output_format=miniaudio.SampleFormat.FLOAT32,
            nchannels=1,
            sample_rate=self._sample_rate,
            buffersize_msec=20,
        )
        generator = self._frames()
        next(generator)
        device.start(generator)
        return device

    def _close(self, device) -> None:
        device.close()

    def _frames(self):
        required = yield b""
        while True:
            output = np.zeros(required, dtype=np.float32)
            self._buffer.read_into(output)
            required = yield output.tobytes()


def create_player(sample_rate: int) -> BufferedPlayer:
    try:
        import sounddevice  # noqa: F401  (raises OSError when PortAudio is missing)

        return SounddevicePlayer(sample_rate)
    except OSError:
        log.info("PortAudio not available, playing audio through miniaudio")
        return MiniaudioPlayer(sample_rate)
