import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from importlib import resources

ENGLISH = "en"
WORD = re.compile(r"[^\W\d_](?:[\w'’-]*\w)?")
CAMEL_CASE = re.compile(r"[a-z][A-Z]")
FOREIGN_SPELLING = re.compile(r"[kw]|ck|sh|th|([bdfgpstz])\1|ing$|tion$")
MIN_ENGLISH_LENGTH = 3

TECH_TERMS = frozenset(
    {
        "app", "apps", "chat", "chats", "click", "email", "emails", "hardware", "link", "links",
        "offline", "online", "software", "test", "tests", "web", "wifi",
    }
)


@dataclass(frozen=True)
class Run:
    lang: str
    text: str


class CodeSwitcher:
    def __init__(self, english: Iterable[str] = (), native: Iterable[str] = ()):
        self._forced_english = {word.lower() for word in english}
        self._forced_native = {word.lower() for word in native}

    def runs(self, sentence: str, lang: str) -> list[Run]:
        if lang == ENGLISH:
            return [Run(lang, sentence)] if sentence.strip() else []
        runs: list[Run] = []
        start, current = 0, lang
        for match in WORD.finditer(sentence):
            word_lang = ENGLISH if self.is_english(match.group(0), lang) else lang
            if word_lang != current and match.start() > start:
                runs.append(Run(current, sentence[start : match.start()]))
                start = match.start()
            current = word_lang
        runs.append(Run(current, sentence[start:]))
        return [run for run in _merge(runs) if run.text.strip()]

    def is_english(self, word: str, lang: str) -> bool:
        lowered = word.lower().replace("’", "'").removesuffix("'s")
        if lowered in self._forced_native:
            return False
        if lowered in self._forced_english or CAMEL_CASE.search(word):
            return True
        if word.isupper() or len(lowered) < MIN_ENGLISH_LENGTH or not lowered.isascii():
            return False
        return lowered in TECH_TERMS or lowered in _english_leaning(lang) or bool(FOREIGN_SPELLING.search(lowered))


def _merge(runs: list[Run]) -> list[Run]:
    merged: list[Run] = []
    for run in runs:
        if merged and merged[-1].lang == run.lang:
            merged[-1] = Run(run.lang, merged[-1].text + run.text)
        else:
            merged.append(run)
    return merged


@cache
def _english_leaning(lang: str) -> frozenset[str]:
    try:
        data = resources.files("speak.text.data").joinpath(f"english_words.{lang}.txt").read_text()
    except FileNotFoundError:
        return frozenset()
    return frozenset(data.split())
