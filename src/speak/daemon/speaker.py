import asyncio
import logging
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from speak.daemon.player import Player
from speak.text.speech import Segment

Synthesize = Callable[[Segment], np.ndarray]

log = logging.getLogger(__name__)


class Speaker:
    def __init__(self, synthesize: Synthesize, player: Player):
        self._synthesize = synthesize
        self._player = player
        self._queue: asyncio.Queue[tuple[int, Segment, float | None]] = asyncio.Queue()
        self._generation = 0
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="synth")
        self._worker: asyncio.Task | None = None

    def start(self) -> None:
        self._worker = asyncio.get_running_loop().create_task(self._run())

    async def close(self) -> None:
        if self._worker:
            self._worker.cancel()
        self._executor.shutdown(wait=False, cancel_futures=True)

    def speak(self, segments: Sequence[Segment], preempt: bool, requested_at: float | None = None) -> None:
        if preempt:
            self.stop()
        requested_at = requested_at or time.monotonic()
        for index, segment in enumerate(segments):
            self._queue.put_nowait((self._generation, segment, requested_at if index == 0 else None))

    def stop(self) -> None:
        self._generation += 1
        while not self._queue.empty():
            self._queue.get_nowait()
        self._player.clear()

    def is_idle(self) -> bool:
        return self._queue.empty() and self._player.is_idle()

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            generation, segment, requested_at = await self._queue.get()
            if generation != self._generation:
                continue
            try:
                audio = await loop.run_in_executor(self._executor, self._synthesize, segment)
            except Exception:
                log.exception("synthesis failed for %r", segment.text)
                continue
            if generation == self._generation:
                self._player.enqueue(audio, requested_at)
