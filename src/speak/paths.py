import os
from dataclasses import dataclass
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Paths:
    home: Path
    config: Path
    plugin_root: Path = SOURCE_ROOT

    @classmethod
    def from_env(cls) -> "Paths":
        return cls(
            home=Path(os.environ.get("SPEAK_HOME", Path.home() / ".cache" / "speak")),
            config=Path(os.environ.get("SPEAK_CONFIG_HOME", Path.home() / ".config" / "speak")),
            plugin_root=Path(os.environ.get("SPEAK_PLUGIN_ROOT", SOURCE_ROOT)),
        )

    @property
    def helper_binary(self) -> Path:
        return self.plugin_root / "bin" / "speak-helper"

    @property
    def socket(self) -> Path:
        return self.home / "daemon.sock"

    @property
    def lock(self) -> Path:
        return self.home / "daemon.lock"

    @property
    def log(self) -> Path:
        return self.home / "daemon.log"

    @property
    def sessions(self) -> Path:
        return self.home / "sessions"

    @property
    def models(self) -> Path:
        return self.home / "models"

    @property
    def huggingface(self) -> Path:
        return self.home / "hf"

    @property
    def model_ready_marker(self) -> Path:
        return self.home / "model-ready"

    @property
    def settings_file(self) -> Path:
        return self.config / "config.json"

    @property
    def lexicon_file(self) -> Path:
        return self.config / "lexicon.json"
