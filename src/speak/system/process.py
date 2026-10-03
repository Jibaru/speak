import os
import subprocess
import sys
from pathlib import Path


def spawn_detached(command: list[str], log_file: Path) -> None:
    with open(log_file, "ab") as log:
        options: dict = {"stdin": subprocess.DEVNULL, "stdout": log, "stderr": log, "env": os.environ.copy()}
        if sys.platform == "win32":
            options["creationflags"] = (
                subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
            )
        else:
            options["start_new_session"] = True
        subprocess.Popen(command, **options)


def background_python() -> str:
    """On Windows, pythonw avoids flashing a console window for the daemon."""
    if sys.platform == "win32":
        windowless = Path(sys.executable).with_name("pythonw.exe")
        if windowless.exists():
            return str(windowless)
    return sys.executable
