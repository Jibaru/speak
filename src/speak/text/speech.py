import re
from dataclasses import dataclass
from typing import Literal

from speak.text import language
from speak.text.lexicon import Lexicon
from speak.text.markdown import Block, to_blocks
from speak.text.sentences import split_sentences

Mode = Literal["brief", "full"]
BRIEF_MAX_SENTENCES = 2
FIRST_CHUNK_MAX_CHARS = 60
FIRST_CHUNK_MIN_CHARS = 12
CLAUSE_BREAK = re.compile(r"[,;:]\s")


@dataclass(frozen=True)
class Segment:
    text: str
    lang: str


class SpeechPreparer:
    def __init__(self, lexicon: Lexicon):
        self._lexicon = lexicon

    def prepare(self, markdown: str, mode: Mode = "full") -> list[Segment]:
        blocks, dominant = to_blocks(markdown)
        sentences = _brief(blocks) if mode == "brief" else [s for b in blocks for s in split_sentences(b.text)]
        sentences = _split_first_clause(sentences)
        languages = language.assign_languages(sentences, default=dominant)
        return [
            Segment(self._lexicon.apply(sentence, lang), lang)
            for sentence, lang in zip(sentences, languages, strict=True)
        ]


def _split_first_clause(sentences: list[str]) -> list[str]:
    """A short first chunk lets audio start sooner on slow CPUs."""
    if not sentences or len(sentences[0]) <= FIRST_CHUNK_MAX_CHARS:
        return sentences
    first = sentences[0]
    for match in CLAUSE_BREAK.finditer(first):
        if FIRST_CHUNK_MIN_CHARS <= match.start() + 1 <= FIRST_CHUNK_MAX_CHARS:
            return [first[: match.start() + 1], first[match.end() :], *sentences[1:]]
    return sentences


def _brief(blocks: list[Block]) -> list[str]:
    first = next((block for block in blocks if block.kind == "prose"), None) or next(iter(blocks), None)
    if first is None:
        return []
    return split_sentences(first.text)[:BRIEF_MAX_SENTENCES]
