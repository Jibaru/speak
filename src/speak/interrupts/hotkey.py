import sys
from dataclasses import dataclass

MODIFIER_ALIASES = {
    "option": "alt", "alt": "alt",
    "ctrl": "ctrl", "control": "ctrl",
    "shift": "shift",
    "cmd": "super", "command": "super", "win": "super", "super": "super", "meta": "super",
}


@dataclass(frozen=True)
class Hotkey:
    modifiers: frozenset[str]
    key: str

    @classmethod
    def parse(cls, description: str) -> "Hotkey":
        *modifiers, key = [part.strip().lower() for part in description.split("+")]
        unknown = [modifier for modifier in modifiers if modifier not in MODIFIER_ALIASES]
        if unknown or not key:
            raise ValueError(f"invalid hotkey {description!r}")
        return cls(frozenset(MODIFIER_ALIASES[modifier] for modifier in modifiers), "escape" if key == "esc" else key)


def default_hotkey() -> str:
    return "option+escape" if sys.platform == "darwin" else "ctrl+alt+escape"
