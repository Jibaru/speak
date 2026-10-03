import asyncio
import json
from collections.abc import Callable, Iterator
from pathlib import Path

POLL_SECONDS = 0.08

OnText = Callable[[str, str], None]


class TranscriptFollower:
    def __init__(self, path: Path, offset: int | None = None):
        self._path = path
        self._offset = offset if offset is not None else _size(path)

    def read_new_texts(self) -> list[str]:
        try:
            with self._path.open("rb") as transcript:
                transcript.seek(self._offset)
                data = transcript.read()
        except FileNotFoundError:
            return []
        complete = data[: data.rfind(b"\n") + 1]
        self._offset += len(complete)
        return [text for line in complete.splitlines() for text in _assistant_texts(line)]


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except FileNotFoundError:
        return 0


def _assistant_texts(line: bytes) -> Iterator[str]:
    try:
        entry = json.loads(line)
    except ValueError:
        return
    if entry.get("type") != "assistant" or entry.get("isSidechain"):
        return
    content = entry.get("message", {}).get("content")
    if not isinstance(content, list):
        return
    for block in content:
        if block.get("type") == "text" and block.get("text", "").strip():
            yield block["text"]


class Narrator:
    def __init__(self, on_text: OnText):
        self._on_text = on_text
        self._followers: dict[str, TranscriptFollower] = {}
        self._task: asyncio.Task | None = None

    def watch(self, session: str, transcript: Path, offset: int | None = None) -> None:
        self._followers[session] = TranscriptFollower(transcript, offset)
        if self._task is None or self._task.done():
            self._task = asyncio.get_running_loop().create_task(self._poll_forever())

    def finish(self, session: str) -> None:
        follower = self._followers.pop(session, None)
        if follower:
            self._emit(session, follower)

    def unwatch(self, session: str) -> None:
        self._followers.pop(session, None)

    @property
    def watching(self) -> bool:
        return bool(self._followers)

    async def _poll_forever(self) -> None:
        while self._followers:
            for session, follower in list(self._followers.items()):
                self._emit(session, follower)
            await asyncio.sleep(POLL_SECONDS)

    def _emit(self, session: str, follower: TranscriptFollower) -> None:
        for text in follower.read_new_texts():
            self._on_text(session, text)
