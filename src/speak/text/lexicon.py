import json
import re
from collections.abc import Mapping
from pathlib import Path

SPANISH_TERMS = {
    "API": "a pe i",
    "APIs": "a pe is",
    "CLI": "ce ele i",
    "URL": "u erre ele",
    "URLs": "u erre eles",
    "JSON": "yéison",
    "README": "ridmi",
    "TTS": "te te ese",
    "MLX": "eme ele equis",
    "macOS": "mac o ese",
    "npm": "ene pe eme",
    "OK": "okey",
    "Next.js": "next yei es",
    "Node.js": "noud yei es",
}

DEFAULTS: Mapping[str, Mapping[str, str]] = {"es": SPANISH_TERMS}


class Lexicon:
    def __init__(self, entries: Mapping[str, Mapping[str, str]]):
        self._patterns = {lang: _compile(terms) for lang, terms in entries.items() if terms}
        self._replacements = {lang: {term.lower(): spoken for term, spoken in terms.items()} for lang, terms in entries.items()}

    @classmethod
    def load(cls, user_file: Path | None = None) -> "Lexicon":
        merged = {lang: dict(terms) for lang, terms in DEFAULTS.items()}
        if user_file and user_file.exists():
            for lang, terms in json.loads(user_file.read_text()).items():
                if isinstance(terms, dict):
                    merged.setdefault(lang, {}).update(terms)
        return cls(merged)

    def apply(self, text: str, lang: str) -> str:
        pattern = self._patterns.get(lang)
        if pattern is None:
            return text
        replacements = self._replacements[lang]
        return pattern.sub(lambda match: replacements[match.group(0).lower()], text)


def _compile(terms: Mapping[str, str]) -> re.Pattern[str]:
    alternatives = "|".join(re.escape(term) for term in sorted(terms, key=len, reverse=True))
    return re.compile(rf"(?<![\w.])(?:{alternatives})(?![\w])", re.IGNORECASE)
