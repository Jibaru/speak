import pytest

from speak.text.codeswitch import CodeSwitcher, Run


@pytest.fixture
def switcher():
    return CodeSwitcher()


def test_splits_english_jargon_out_of_spanish(switcher):
    assert switcher.runs("Listo, hice el deploy del hook en TypeScript.", "es") == [
        Run("es", "Listo, hice el "),
        Run("en", "deploy "),
        Run("es", "del "),
        Run("en", "hook "),
        Run("es", "en "),
        Run("en", "TypeScript."),
    ]


def test_adjacent_english_words_form_one_run(switcher):
    assert Run("en", "pull request ") in switcher.runs("Revisa el pull request ahora.", "es")


@pytest.mark.parametrize("word", ["come", "once", "has", "red", "real", "leer", "creer", "acción", "API", "JSON", "el", "y"])
def test_spanish_words_and_acronyms_stay_native(switcher, word):
    assert not switcher.is_english(word, "es")


@pytest.mark.parametrize("word", ["deploy", "hook", "staging", "useEffect", "GitHub", "link", "click", "online", "setting", "user's"])
def test_english_words_are_detected(switcher, word):
    assert switcher.is_english(word, "es")


def test_english_sentences_are_a_single_run(switcher):
    assert switcher.runs("All the tests pass.", "en") == [Run("en", "All the tests pass.")]


def test_user_overrides_win():
    switcher = CodeSwitcher(english=["Kubernetes"], native=["hook"])
    assert switcher.is_english("kubernetes", "es")
    assert not switcher.is_english("hook", "es")


def test_unknown_language_falls_back_to_spelling_rules(switcher):
    assert switcher.is_english("thread", "de")
    assert not switcher.is_english("Haus", "de")
