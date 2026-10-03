from dataclasses import dataclass
from typing import Literal

from speak.text import language
from speak.text.lexicon import Lexicon
from speak.text.markdown import Block, to_blocks
from speak.text.sentences import split_sentences

Mode = Literal["brief", "full"]
BRIEF_MAX_SENTENCES = 2


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
        languages = language.assign_languages(sentences, default=dominant)
        return [
            Segment(self._lexicon.apply(sentence, lang), lang)
            for sentence, lang in zip(sentences, languages, strict=True)
        ]


def _brief(blocks: list[Block]) -> list[str]:
    first = next((block for block in blocks if block.kind == "prose"), None) or next(iter(blocks), None)
    if first is None:
        return []
    return split_sentences(first.text)[:BRIEF_MAX_SENTENCES]
