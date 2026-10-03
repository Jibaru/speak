import json

import pytest

from speak.text import language
from speak.text.lexicon import Lexicon
from speak.text.markdown import clean_inline, to_blocks
from speak.text.sentences import split_sentences
from speak.text.speech import Segment, SpeechPreparer


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Listo, los tests pasan y el hook ya está configurado.", "es"),
        ("Corrí el deploy en staging y el endpoint responde bien.", "es"),
        ("Done. I refactored the parser and all tests are green.", "en"),
        ("Il y a un problème dans le fichier de configuration.", "fr"),
        ("Deploy staging endpoint.", None),
    ],
)
def test_detect(text, expected):
    assert language.detect(text) == expected


def test_short_sentences_inherit_previous_language():
    sentences = ["Encontré el bug en el parser del proyecto.", "Fixed.", "All the tests are passing now."]
    assert language.assign_languages(sentences) == ["es", "es", "en"]


def test_code_blocks_and_tables_become_placeholders():
    markdown = "Listo, ya está el cambio.\n\n```ts\nconst a = 1;\n```\n\n| a | b |\n|---|---|\n| 1 | 2 |\n"
    blocks, lang = to_blocks(markdown)
    assert lang == "es"
    assert [block.text for block in blocks] == [
        "Listo, ya está el cambio.",
        "Te dejé un bloque de código en TypeScript.",
        "Te dejé una tabla.",
    ]
    assert [block.kind for block in blocks] == ["prose", "placeholder", "placeholder"]


def test_unterminated_fence_is_still_a_placeholder():
    blocks, _ = to_blocks("Here it is:\n```python\nprint(1)\n")
    assert blocks[-1].text == "There's a code block in Python."


def test_headings_and_bullets_become_sentences():
    blocks, _ = to_blocks("## Summary\n- **Fixed** the parser\n- Added `tests/test_cli.py`\n1. Ship it!")
    assert [block.text for block in blocks] == ["Summary.", "Fixed the parser.", "Added test_cli.py.", "Ship it!"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("See [the docs](https://example.com) now", "See the docs now"),
        ("Open https://example.com/x?y=1 please", "Open a link please"),
        ("Edited /Users/me/project/src/app.py today", "Edited app.py today"),
        ("Use `npm run build` here", "Use npm run build here"),
        ("Done ✅ and **bold** and _soft_ and snake_case_name", "Done and bold and soft and snake_case_name"),
        ("A → B", "A, B"),
    ],
)
def test_clean_inline(raw, expected):
    assert clean_inline(raw, "en") == expected


def test_split_sentences_keeps_abbreviations_and_splits_long_ones():
    assert split_sentences("Use tools, e.g. grep. Then run it! Done?") == ["Use tools, e.g. grep.", "Then run it!", "Done?"]
    long_sentence = ", ".join(["this clause is long enough"] * 12) + "."
    chunks = split_sentences(long_sentence)
    assert len(chunks) > 1
    assert all(len(chunk) <= 220 for chunk in chunks)


def test_lexicon_replaces_whole_words_case_insensitively(tmp_path):
    user_file = tmp_path / "lexicon.json"
    user_file.write_text(json.dumps({"es": {"Kokoro": "cocoro"}}))
    lexicon = Lexicon.load(user_file)
    assert lexicon.apply("El Hook de Claude Code usa Kokoro y hookah", "es") == "El juk de clod cod usa cocoro y hookah"
    assert lexicon.apply("The hook works", "en") == "The hook works"


def test_prepare_brief_reads_only_first_prose_paragraph():
    preparer = SpeechPreparer(Lexicon({}))
    markdown = "```sh\nls\n```\n\nListo, arreglé el bug. Los tests pasan. Y algo más.\n\nDetalles largos aquí."
    assert preparer.prepare(markdown, "brief") == [
        Segment("Listo, arreglé el bug.", "es"),
        Segment("Los tests pasan.", "es"),
    ]


def test_prepare_full_switches_language_per_sentence():
    preparer = SpeechPreparer(Lexicon.load())
    segments = preparer.prepare("Ya corrí el deploy del proyecto. The error message says that the file is missing.")
    assert segments == [
        Segment("Ya corrí el diplói del proyecto.", "es"),
        Segment("The error message says that the file is missing.", "en"),
    ]


def test_prepare_empty_text():
    assert SpeechPreparer(Lexicon({})).prepare("", "brief") == []
