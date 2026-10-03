# /// script
# requires-python = ">=3.12"
# dependencies = ["wordfreq"]
# ///
"""Build the lists of English-leaning words used to detect code-switching."""

from pathlib import Path

from wordfreq import top_n_list, zipf_frequency

TARGET_LANGUAGES = ("es", "fr", "it", "pt")
CANDIDATES = 60_000
MIN_ENGLISH_ZIPF = 2.5
MIN_ENGLISH_LEAD = 0.5
MAX_NATIVE_ZIPF = 3.8
OUTPUT = Path(__file__).resolve().parents[1] / "src" / "speak" / "text" / "data"


def english_leaning(word: str, lang: str) -> bool:
    english, native = zipf_frequency(word, "en"), zipf_frequency(word, lang)
    return english >= MIN_ENGLISH_ZIPF and english - native >= MIN_ENGLISH_LEAD and native < MAX_NATIVE_ZIPF


def main() -> None:
    candidates = [word for word in top_n_list("en", CANDIDATES) if word.isalpha() and word.isascii() and len(word) > 2]
    for lang in TARGET_LANGUAGES:
        words = sorted(word for word in candidates if english_leaning(word, lang))
        (OUTPUT / f"english_words.{lang}.txt").write_text("\n".join(words) + "\n")
        print(f"{lang}: {len(words)} words")


if __name__ == "__main__":
    main()
