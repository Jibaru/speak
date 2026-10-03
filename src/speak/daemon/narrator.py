import asyncio
import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

POLL_SECONDS = 0.08
INTERRUPT_MARKER = "[Request interrupted by user"

OnText = Callable[[str, str], None]
OnInterrupt = Callable[[str], None]


@dataclass(frozen=True)
class TranscriptUpdate:
    texts: list[str]
    interrupted: bool


class TranscriptFollower:
    def __init__(self, path: Path, offset: int | None = None):
        self._path = path
        self._offset = offset if offset is not None else _size(path)

    def read_new_texts(self) -> list[str]:
        return self.read_update().texts

    def read_update(self) -> TranscriptUpdate:
        try:
            with self._path.open("rb") as transcript:
                transcript.seek(self._offset)
                data = transcript.read()
        except FileNotFoundError:
            return TranscriptUpdate([], interrupted=False)
        complete = data[: data.rfind(b"\n") + 1]
        self._offset += len(complete)
        entries = [entry for line in complete.splitlines() if (entry := _parse(line))]
        return TranscriptUpdate(
            texts=[text for entry in entries for text in _assistant_texts(entry)],
            interrupted=any(_is_interrupt(entry) for entry in entries),
        )


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except FileNotFoundError:
        return 0


def _parse(line: bytes) -> dict | None:
    try:
        entry = json.loads(line)
    except ValueError:
        return None
    return entry if isinstance(entry, dict) else None


def _content_blocks(entry: dict) -> list:
    content = entry.get("message", {}).get("content")
    return content if isinstance(content, list) else []


def _is_interrupt(entry: dict) -> bool:
    return entry.get("type") == "user" and any(
        block.get("type") == "text" and block.get("text", "").startswith(INTERRUPT_MARKER)
        for block in _content_blocks(entry)
    )


def _assistant_texts(entry: dict) -> Iterator[str]:
    if entry.get("type") != "assistant" or entry.get("isSidechain"):
        return
    for block in _content_blocks(entry):
        if block.get("type") == "text" and block.get("text", "").strip():
            yield block["text"]


class Narrator:
    def __init__(self, on_text: OnText, on_interrupt: OnInterrupt):
        self._on_text = on_text
        self._on_interrupt = on_interrupt
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
        update = follower.read_update()
        if update.interrupted:
            self._followers.pop(session, None)
            self._on_interrupt(session)
            return
        for text in update.texts:
            self._on_text(session, text)
