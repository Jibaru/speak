import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from speak.text import language, phrases

BlockKind = Literal["prose", "placeholder"]


@dataclass(frozen=True)
class Block:
    kind: BlockKind
    text: str


FENCE = re.compile(r"^\s*(```|~~~)\s*([\w+#.-]*)")
TABLE_ROW = re.compile(r"^\s*\|")
HEADING = re.compile(r"^\s{0,3}#{1,6}\s+")
BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s+)?")
BLOCKQUOTE = re.compile(r"^\s*>\s?")
RULE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")

IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
URL = re.compile(r"https?://\S+")
INLINE_CODE = re.compile(r"`([^`]+)`")
PATH = re.compile(r"(?<![\w.])(?:~|\.{1,2})?(?:/[\w.@-]+){2,}/?")
STRONG = re.compile(r"(\*\*|__)(.+?)\1")
EMPHASIS = re.compile(r"(?<![\w*])[*_](?!\s)(.+?)(?<!\s)[*_](?![\w*])")
STRIKE = re.compile(r"~~(.+?)~~")
HTML_TAG = re.compile(r"</?[a-zA-Z][^>]*>")
ARROW = re.compile(r"\s*(?:→|⟶|->|=>|➡️?)\s*")
SPACES = re.compile(r"\s+")
TERMINAL = ".!?:;…"


@dataclass(frozen=True)
class _RawBlock:
    kind: Literal["prose", "code", "table"]
    text: str
    standalone_line: bool = False


def to_blocks(markdown: str) -> tuple[list[Block], str]:
    raw = _parse(markdown)
    lang = language.detect(" ".join(block.text for block in raw if block.kind == "prose")) or language.FALLBACK
    rendered = (_render(block, lang) for block in raw)
    return [block for block in rendered if block.text], lang


def _parse(markdown: str) -> list[_RawBlock]:
    blocks: list[_RawBlock] = []
    paragraph: list[str] = []
    fence: str | None = None
    fence_info = ""
    in_table = False

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append(_RawBlock("prose", " ".join(paragraph)))
            paragraph.clear()

    for line in markdown.splitlines():
        fence_match = FENCE.match(line)
        if fence is not None:
            if fence_match and fence_match.group(1) == fence:
                blocks.append(_RawBlock("code", fence_info))
                fence = None
            continue
        if fence_match:
            flush_paragraph()
            fence, fence_info = fence_match.group(1), fence_match.group(2)
            continue

        if TABLE_ROW.match(line):
            flush_paragraph()
            if not in_table:
                blocks.append(_RawBlock("table", ""))
            in_table = True
            continue
        in_table = False

        if not line.strip() or RULE.match(line):
            flush_paragraph()
            continue
        if HEADING.match(line) or BULLET.match(line):
            flush_paragraph()
            blocks.append(_RawBlock("prose", _strip_line_markers(line), standalone_line=True))
            continue
        paragraph.append(_strip_line_markers(line))

    if fence is not None:
        blocks.append(_RawBlock("code", fence_info))
    flush_paragraph()
    return blocks


def _render(block: _RawBlock, lang: str) -> Block:
    if block.kind == "code":
        return Block("placeholder", phrases.code_block(lang, block.text))
    if block.kind == "table":
        return Block("placeholder", phrases.phrase("table", lang))
    text = clean_inline(block.text, lang)
    return Block("prose", _ensure_terminal(text) if block.standalone_line else text)


def _strip_line_markers(line: str) -> str:
    for pattern in (HEADING, BULLET, BLOCKQUOTE):
        line = pattern.sub("", line, count=1)
    return line.strip()


def _ensure_terminal(text: str) -> str:
    if text and text[-1] not in TERMINAL:
        return text + "."
    return text


def clean_inline(text: str, lang: str) -> str:
    text = IMAGE.sub(r"\1", text)
    text = LINK.sub(r"\1", text)
    text = URL.sub(phrases.phrase("link", lang), text)
    text = INLINE_CODE.sub(lambda match: _speakable_code(match.group(1)), text)
    text = PATH.sub(lambda match: _basename(match.group(0)), text)
    text = STRONG.sub(r"\2", text)
    text = STRIKE.sub(r"\1", text)
    text = EMPHASIS.sub(r"\1", text)
    text = HTML_TAG.sub("", text)
    text = ARROW.sub(", ", text)
    text = _strip_symbols(text)
    return SPACES.sub(" ", text).strip(" ,")


def _speakable_code(code: str) -> str:
    if " " not in code and "/" in code:
        return _basename(code)
    return code


def _basename(path: str) -> str:
    return path.rstrip("/").rsplit("/", 1)[-1]


def _strip_symbols(text: str) -> str:
    return "".join(
        character
        for character in text
        if unicodedata.category(character) not in ("So", "Sk", "Cs", "Co") and character != "️"
    )
