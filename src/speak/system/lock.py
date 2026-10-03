import os
import sys
from pathlib import Path
from typing import IO


class InstanceLock:
    """An exclusive, non-blocking lock held for the lifetime of the process."""

    def __init__(self, path: Path):
        self._path = path
        self._file: IO | None = None

    def acquire(self) -> bool:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self._path, "a+")
        try:
            _lock(self._file)
        except OSError:
            self._file.close()
            self._file = None
            return False
        return True

    def release(self) -> None:
        if self._file:
            self._file.close()
            self._file = None


def _lock(file: IO) -> None:
    if sys.platform == "win32":
        import msvcrt

        file.seek(0)
        msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)


def write_private(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as file:
        file.write(text)
    temporary.replace(path)
