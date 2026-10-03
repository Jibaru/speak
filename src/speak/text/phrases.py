CODE_LANGUAGE_NAMES = {
    "ts": "TypeScript", "tsx": "TypeScript", "typescript": "TypeScript",
    "js": "JavaScript", "jsx": "JavaScript", "javascript": "JavaScript",
    "py": "Python", "python": "Python",
    "sh": "shell", "bash": "shell", "zsh": "shell", "shell": "shell", "console": "shell",
    "json": "JSON", "yaml": "YAML", "yml": "YAML", "toml": "TOML",
    "go": "Go", "rs": "Rust", "rust": "Rust", "swift": "Swift", "sql": "SQL",
    "html": "HTML", "css": "CSS", "md": "Markdown", "markdown": "Markdown",
    "rb": "Ruby", "ruby": "Ruby", "java": "Java", "kt": "Kotlin", "c": "C", "cpp": "C++",
}

PHRASES = {
    "code": {
        "en": "There's a code block{language}.",
        "es": "Te dejé un bloque de código{language}.",
        "fr": "Il y a un bloc de code{language}.",
        "it": "C'è un blocco di codice{language}.",
        "pt": "Deixei um bloco de código{language}.",
    },
    "code_language": {
        "en": " in {name}", "es": " en {name}", "fr": " en {name}", "it": " in {name}", "pt": " em {name}",
    },
    "table": {
        "en": "There's a table.",
        "es": "Te dejé una tabla.",
        "fr": "Il y a un tableau.",
        "it": "C'è una tabella.",
        "pt": "Deixei uma tabela.",
    },
    "link": {"en": "a link", "es": "un enlace", "fr": "un lien", "it": "un link", "pt": "um link"},
}


def phrase(key: str, lang: str, **values: str) -> str:
    options = PHRASES[key]
    return options.get(lang, options["en"]).format(**values)


def code_block(lang: str, info: str) -> str:
    name = CODE_LANGUAGE_NAMES.get(info.lower())
    language = phrase("code_language", lang, name=name) if name else ""
    return phrase("code", lang, language=language)
