import re

BOUNDARY = re.compile(r"(?<=[.!?…])\s+(?=[\"'(¿¡]?[\w])")
SOFT_BOUNDARY = re.compile(r"(?<=[;:])\s+|(?<=,)\s+")
ABBREVIATIONS = ("e.g.", "i.e.", "etc.", "vs.", "p.ej.", "Sr.", "Sra.", "Dr.", "approx.")
MAX_SENTENCE_CHARS = 220


def split_sentences(paragraph: str) -> list[str]:
    sentences: list[str] = []
    for piece in BOUNDARY.split(paragraph.strip()):
        if sentences and sentences[-1].endswith(ABBREVIATIONS):
            sentences[-1] = f"{sentences[-1]} {piece}"
        else:
            sentences.append(piece)
    return [chunk for sentence in sentences for chunk in _split_long(sentence) if chunk]


def _split_long(sentence: str) -> list[str]:
    if len(sentence) <= MAX_SENTENCE_CHARS:
        return [sentence]
    chunks: list[str] = []
    current = ""
    for piece in SOFT_BOUNDARY.split(sentence):
        candidate = f"{current} {piece}".strip()
        if current and len(candidate) > MAX_SENTENCE_CHARS:
            chunks.append(current)
            current = piece
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks
