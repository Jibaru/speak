import json
import re
from collections.abc import Mapping
from pathlib import Path

SPANISH_TECH_TERMS = {
    "Claude Code": "clod cod",
    "Claude": "clod",
    "pull request": "pul request",
    "pull requests": "pul requests",
    "TypeScript": "táip escript",
    "JavaScript": "yava escript",
    "Next.js": "next yei es",
    "Node.js": "noud yei es",
    "useEffect": "ius ifect",
    "useState": "ius steit",
    "GitHub": "guit jab",
    "README": "ridmi",
    "hook": "juk",
    "hooks": "juks",
    "deploy": "diplói",
    "deploys": "diplóis",
    "staging": "stéiying",
    "endpoint": "éndpoint",
    "endpoints": "éndpoints",
    "bug": "bag",
    "bugs": "bags",
    "debug": "dibág",
    "commit": "cómit",
    "commits": "cómits",
    "merge": "merch",
    "feature": "fícher",
    "features": "fíchers",
    "frontend": "frontend",
    "backend": "bákend",
    "build": "bild",
    "script": "escript",
    "scripts": "escripts",
    "plugin": "pláguin",
    "plugins": "pláguins",
    "daemon": "dímon",
    "token": "tóken",
    "tokens": "tókens",
    "workflow": "uórkflou",
    "workflows": "uórkflous",
    "issue": "íshu",
    "issues": "íshus",
    "cache": "cach",
    "React": "riáct",
    "hotkey": "jótqui",
    "listener": "lísener",
    "update": "ápdeit",
    "upload": "áploud",
    "download": "dáunloud",
    "framework": "fréimuork",
    "query": "cuéri",
    "queries": "cuéris",
    "string": "estrin",
    "JSON": "yéison",
    "API": "a pe i",
    "APIs": "a pe is",
    "CLI": "ce ele i",
    "URL": "u erre ele",
    "TTS": "te te ese",
    "MLX": "eme ele equis",
    "macOS": "mac o ese",
    "npm": "ene pe eme",
    "OK": "okey",
}

DEFAULTS: Mapping[str, Mapping[str, str]] = {"es": SPANISH_TECH_TERMS}


class Lexicon:
    def __init__(self, entries: Mapping[str, Mapping[str, str]]):
        self._patterns = {lang: _compile(terms) for lang, terms in entries.items() if terms}
        self._replacements = {lang: {term.lower(): spoken for term, spoken in terms.items()} for lang, terms in entries.items()}

    @classmethod
    def load(cls, user_file: Path | None = None) -> "Lexicon":
        merged = {lang: dict(terms) for lang, terms in DEFAULTS.items()}
        if user_file and user_file.exists():
            for lang, terms in json.loads(user_file.read_text()).items():
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
