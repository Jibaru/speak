import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path

from speak.paths import Paths


class Level(StrEnum):
    OFF = "off"
    BRIEF = "brief"
    FULL = "full"
    NARRATE = "narrate"


DEFAULT_VOICES = {"en": "af_heart", "es": "ef_dora", "fr": "ff_siwis", "it": "if_sara", "pt": "pf_dora"}
DEFAULT_SAY_VOICES = {"en": "Samantha", "es": "Paulina", "fr": "Thomas", "it": "Alice", "pt": "Luciana"}


@dataclass
class Settings:
    level: Level = Level.BRIEF
    engine: str = "auto"
    rate: float = 1.15
    voices: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_VOICES))
    say_voices: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_SAY_VOICES))
    hotkey: str = "option+escape"
    stop_on_mic: bool = True
    idle_minutes: int = 30

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        defaults = cls()
        return cls(
            level=Level(data.get("level", defaults.level)),
            engine=str(data.get("engine", defaults.engine)),
            rate=float(data.get("rate", defaults.rate)),
            voices={**defaults.voices, **data.get("voices", {})},
            say_voices={**defaults.say_voices, **data.get("say_voices", {})},
            hotkey=data.get("hotkey", defaults.hotkey),
            stop_on_mic=bool(data.get("stop_on_mic", defaults.stop_on_mic)),
            idle_minutes=int(data.get("idle_minutes", defaults.idle_minutes)),
        )


class SettingsStore:
    def __init__(self, paths: Paths):
        self._paths = paths

    def load(self) -> Settings:
        return Settings.from_dict(_read_json(self._paths.settings_file))

    def save(self, settings: Settings) -> None:
        _write_json(self._paths.settings_file, asdict(settings))

    def update(self, **changes) -> Settings:
        settings = self.load()
        for key, value in changes.items():
            setattr(settings, key, value)
        self.save(settings)
        return settings

    def session_level(self, session_id: str) -> Level | None:
        level = _read_json(self._session_file(session_id)).get("level")
        return Level(level) if level else None

    def set_session_level(self, session_id: str, level: Level) -> None:
        _write_json(self._session_file(session_id), {"level": level})

    def clear_session(self, session_id: str) -> None:
        self._session_file(session_id).unlink(missing_ok=True)

    def effective_level(self, session_id: str | None) -> Level:
        return (session_id and self.session_level(session_id)) or self.load().level

    def _session_file(self, session_id: str) -> Path:
        safe_id = "".join(character for character in session_id if character.isalnum() or character in "-_")
        return self._paths.sessions / f"{safe_id}.json"


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2))
    temporary.replace(path)
