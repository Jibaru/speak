import re
from collections.abc import Sequence

SUPPORTED = ("en", "es", "fr", "it", "pt")
FALLBACK = "en"
MIN_WORDS_TO_DETECT = 4

FUNCTION_WORDS = {
    "en": {
        "the", "and", "is", "are", "was", "were", "to", "of", "in", "it", "this", "that", "with",
        "for", "you", "i", "have", "has", "be", "on", "not", "all", "now", "just", "will", "can",
        "we", "my", "your", "there", "what", "which", "they", "from", "but", "so", "if", "done",
    },
    "es": {
        "el", "la", "los", "las", "de", "del", "que", "y", "en", "es", "un", "una", "por", "con",
        "para", "no", "se", "lo", "al", "ya", "está", "están", "son", "pero", "como", "más", "te",
        "tu", "yo", "esto", "eso", "listo", "también", "hay", "fue", "muy", "todo", "todos", "ahora",
    },
    "fr": {
        "le", "la", "les", "des", "du", "et", "est", "une", "un", "que", "qui", "dans", "pour",
        "pas", "avec", "sur", "ce", "cette", "je", "vous", "nous", "il", "sont", "fait", "très",
        "mais", "ou", "au",
    },
    "it": {
        "il", "lo", "gli", "della", "che", "di", "e", "è", "una", "un", "per", "con", "non",
        "sono", "questo", "anche", "più", "nel", "alla", "del", "ho", "hai", "ma",
    },
    "pt": {
        "o", "os", "as", "da", "do", "das", "dos", "que", "e", "é", "em", "um", "uma", "para",
        "com", "não", "se", "está", "são", "isso", "também", "mais", "foi", "pelo", "pela", "você",
    },
}

DISTINCTIVE_CHARACTERS = {"es": "ñ¿¡", "pt": "ãõ", "fr": "èêœù", "it": "ò"}

WORD = re.compile(r"[^\W\d_]+")


def words(text: str) -> list[str]:
    return WORD.findall(text.lower())


def detect(text: str, prefer: str | None = None) -> str | None:
    tokens = words(text)
    scores = {lang: sum(token in FUNCTION_WORDS[lang] for token in tokens) for lang in SUPPORTED}
    lowered = text.lower()
    for lang, characters in DISTINCTIVE_CHARACTERS.items():
        scores[lang] += 2 * sum(lowered.count(character) for character in characters)

    best = max(scores.values())
    if best == 0:
        return None
    leaders = [lang for lang, score in scores.items() if score == best]
    if prefer in leaders:
        return prefer
    return leaders[0]


def assign_languages(sentences: Sequence[str], default: str = FALLBACK) -> list[str]:
    dominant = detect(" ".join(sentences)) or default
    assigned: list[str] = []
    previous = dominant
    for sentence in sentences:
        detected = detect(sentence, prefer=previous) if len(words(sentence)) >= MIN_WORDS_TO_DETECT else None
        previous = detected or previous
        assigned.append(previous)
    return assigned
