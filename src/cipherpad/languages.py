"""Language definitions used for syntax highlighting and comment toggling."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

Rule = tuple[str, str]  # (regex pattern, style key)


@dataclass(frozen=True)
class MultiLineRule:
    """A construct that may span blocks, e.g. ``/* ... */``."""

    start: str
    end: str
    style: str


@dataclass(frozen=True)
class Language:
    id: str
    name: str
    extensions: tuple[str, ...] = ()
    filenames: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    types: tuple[str, ...] = ()
    builtins: tuple[str, ...] = ()
    line_comment: str = ""
    block_comment: tuple[str, str] | None = None
    rules: tuple[Rule, ...] = ()
    multiline: tuple[MultiLineRule, ...] = field(default_factory=tuple)
    case_insensitive_keywords: bool = False


_C_KEYWORDS = (
    "break continue case default do else for goto if return switch while sizeof "
    "struct union enum typedef static const volatile extern inline register auto"
).split()
_C_TYPES = "void char short int long float double signed unsigned bool size_t".split()

_JAVA_KEYWORDS = (
    "abstract assert break case catch class continue default do else enum extends final "
    "finally for if implements import instanceof interface native new package private "
    "protected public return static strictfp super switch synchronized this throw throws "
    "transient try volatile while var record sealed permits yield"
).split()

_JS_KEYWORDS = (
    "async await break case catch class const continue debugger default delete do else "
    "export extends finally for function if import in instanceof let new of return static "
    "super switch this throw try typeof var void while with yield"
).split()

_TS_TYPES = "any boolean never number object string symbol unknown void readonly keyof infer".split()

_PY_KEYWORDS = (
    "and as assert async await break class continue def del elif else except finally for "
    "from global if import in is lambda nonlocal not or pass raise return try while with yield match case"
).split()
_PY_BUILTINS = (
    "abs all any bool bytes callable chr dict dir enumerate eval filter float format "
    "frozenset getattr hasattr hash hex id input int isinstance issubclass iter len list "
    "map max min next object open ord pow print range repr reversed round set setattr "
    "slice sorted str sum super tuple type vars zip self cls True False None"
).split()

_SQL_KEYWORDS = (
    "select from where insert update delete create drop alter table index view join inner "
    "left right outer on group by order having limit offset union all distinct as and or "
    "not null values into set primary key foreign references default constraint case when "
    "then else end begin commit rollback transaction with exists between like in"
).split()

_SHELL_KEYWORDS = (
    "if then else elif fi for while until do done case esac function return in select "
    "break continue local export readonly declare source alias unset trap shift"
).split()

_NUMBER = (r"\b(?:0[xX][0-9a-fA-F_]+|0[bB][01_]+|0[oO][0-7_]+|\d[\d_]*(?:\.[\d_]+)?(?:[eE][+-]?\d+)?)\b", "number")
_OPERATOR = (r"[+\-*/%=!<>&|^~?:]+", "operator")
_DQ_STRING = (r'"(?:[^"\\\n]|\\.)*"', "string")
_SQ_STRING = (r"'(?:[^'\\\n]|\\.)*'", "string")
_BT_STRING = (r"`(?:[^`\\]|\\.)*`", "string")
_FUNC_CALL = (r"\b([A-Za-z_]\w*)\s*(?=\()", "function")

_C_BLOCK = (MultiLineRule(r"/\*", r"\*/", "comment"),)
# Skip quoted text before capturing //, so URLs do not become comments.
_C_LINE_COMMENT = (
    r"""^(?:"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`|[^"'`/]|/(?!/))*(//[^\n]*)""",
    "comment",
)


def _c_family(id_: str, name: str, exts: tuple[str, ...], keywords, types=(), extra: tuple[Rule, ...] = (),
              multiline: tuple[MultiLineRule, ...] = _C_BLOCK, filenames: tuple[str, ...] = ()) -> Language:
    return Language(
        id=id_,
        name=name,
        extensions=exts,
        filenames=filenames,
        keywords=tuple(keywords),
        types=tuple(types),
        line_comment="//",
        block_comment=("/*", "*/"),
        rules=(_C_LINE_COMMENT, _DQ_STRING, _SQ_STRING, _NUMBER, _FUNC_CALL, _OPERATOR, *extra),
        multiline=multiline,
    )


LANGUAGES: dict[str, Language] = {
    "plain": Language(id="plain", name="Plain Text"),
    "python": Language(
        id="python",
        name="Python",
        extensions=(".py", ".pyw", ".pyi"),
        keywords=tuple(_PY_KEYWORDS),
        builtins=tuple(_PY_BUILTINS),
        line_comment="#",
        rules=(
            (r"#[^\n]*", "comment"),
            (r"@\s*[A-Za-z_][\w.]*", "decorator"),
            (r"\b(?:def|class)\s+([A-Za-z_]\w*)", "function"),
            (r"[rbfuRBFU]{0,3}\"(?:[^\"\\\n]|\\.)*\"", "string"),
            (r"[rbfuRBFU]{0,3}'(?:[^'\\\n]|\\.)*'", "string"),
            _NUMBER,
            _OPERATOR,
        ),
        multiline=(
            MultiLineRule(r'[rbfuRBFU]{0,3}"""', r'"""', "string"),
            MultiLineRule(r"[rbfuRBFU]{0,3}'''", r"'''", "string"),
        ),
    ),
    "javascript": _c_family(
        "javascript",
        "JavaScript",
        (".js", ".jsx", ".mjs", ".cjs"),
        _JS_KEYWORDS,
        ("null", "undefined", "true", "false", "NaN", "Infinity"),
        extra=(_BT_STRING, (r"/\*\*[^\n]*", "comment")),
    ),
    "typescript": _c_family(
        "typescript",
        "TypeScript",
        (".ts", ".tsx", ".mts", ".cts"),
        (*_JS_KEYWORDS, "interface", "type", "enum", "implements", "declare", "namespace", "abstract", "public", "private", "protected"),
        _TS_TYPES,
        extra=(_BT_STRING,),
    ),
    "qml": _c_family(
        "qml", "QML", (".qml",),
        (*_JS_KEYWORDS, "property", "signal", "readonly", "alias", "component", "required", "enum", "as", "on"),
        ("int", "real", "double", "string", "bool", "var", "color", "url", "list", "date",
         "point", "rect", "size", "vector2d", "vector3d", "vector4d", "quaternion", "Qt", "true", "false", "null"),
        extra=(
            (r"\b([A-Z]\w*(?:\.[A-Z]\w*)*)\s*(?=\{)", "type"),
            (r"\b([a-zA-Z_]\w*(?:\.\w+)*)\s*(?=:)", "attribute"),
            _BT_STRING,
        ),
    ),
    "c": _c_family("c", "C", (".c", ".h"), _C_KEYWORDS, _C_TYPES, extra=((r"^\s*#\s*\w+", "preprocessor"),)),
    "cpp": _c_family(
        "cpp",
        "C++",
        (".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx"),
        (*_C_KEYWORDS, "class", "namespace", "template", "typename", "public", "private", "protected",
         "virtual", "override", "new", "delete", "try", "catch", "throw", "using", "constexpr", "nullptr", "friend", "operator"),
        (*_C_TYPES, "wchar_t", "uint8_t", "int32_t", "int64_t", "std"),
        extra=((r"^\s*#\s*\w+", "preprocessor"),),
    ),
    "java": _c_family("java", "Java", (".java",), _JAVA_KEYWORDS, (*_C_TYPES, "String", "Object", "List", "Map")),
    "groovy": _c_family(
        "groovy", "Groovy", (".groovy", ".gvy", ".gy", ".gsh", ".gradle"),
        (*_JAVA_KEYWORDS, "as", "def", "in", "trait"),
        (*_C_TYPES, "String", "Object", "List", "Map", "Set", "Closure", "BigDecimal", "BigInteger",
         "true", "false", "null"),
        extra=((r"@\s*[A-Za-z_][\w.]*", "decorator"),),
        multiline=(
            *_C_BLOCK,
            MultiLineRule(r'"""', r'(?<!\\)"""', "string"),
            MultiLineRule(r"'''", r"(?<!\\)'''", "string"),
            MultiLineRule(r"\$/", r"/\$", "string"),
        ),
        filenames=("Jenkinsfile",),
    ),
    "csharp": _c_family(
        "csharp",
        "C#",
        (".cs",),
        ("abstract as base break case catch checked class const continue default delegate do else enum event "
         "explicit extern finally fixed for foreach goto if implicit in interface internal is lock namespace "
         "new operator out override params private protected public readonly ref return sealed sizeof stackalloc "
         "static struct switch this throw try typeof unchecked unsafe using virtual volatile while var async await").split(),
        (*_C_TYPES, "string", "decimal", "object", "byte", "sbyte", "uint", "ulong", "ushort"),
    ),
    "go": _c_family(
        "go",
        "Go",
        (".go",),
        "break case chan const continue default defer else fallthrough for func go goto if import interface map package range return select struct switch type var".split(),
        "bool byte complex64 complex128 error float32 float64 int int8 int16 int32 int64 rune string uint uintptr".split(),
        extra=(_BT_STRING,),
    ),
    "rust": _c_family(
        "rust",
        "Rust",
        (".rs",),
        "as async await break const continue crate dyn else enum extern fn for if impl in let loop match mod move mut pub ref return self Self static struct super trait type unsafe use where while".split(),
        "bool char f32 f64 i8 i16 i32 i64 i128 isize str u8 u16 u32 u64 u128 usize String Vec Option Result".split(),
    ),
    "json": Language(
        id="json",
        name="JSON",
        extensions=(".json", ".jsonc", ".geojson"),
        rules=(
            (r'"(?:[^"\\]|\\.)*"\s*(?=:)', "attribute"),
            (r'"(?:[^"\\]|\\.)*"', "string"),
            (r"\b(?:true|false|null)\b", "keyword"),
            _NUMBER,
        ),
    ),
    "xml": Language(
        id="xml",
        name="XML / HTML",
        extensions=(".xml", ".html", ".htm", ".xhtml", ".svg", ".xsd", ".xsl", ".ui", ".plist"),
        rules=(
            (r"</?\s*[\w:.-]+", "tag"),
            (r"/?>", "tag"),
            (r"\b[\w:.-]+(?=\s*=)", "attribute"),
            (_DQ_STRING[0], "string"),
            (_SQ_STRING[0], "string"),
            (r"&[a-zA-Z#][\w]*;", "preprocessor"),
        ),
        multiline=(MultiLineRule(r"<!--", r"-->", "comment"),),
        block_comment=("<!--", "-->"),
    ),
    "css": Language(
        id="css",
        name="CSS",
        extensions=(".css", ".scss", ".sass", ".less"),
        line_comment="//",
        block_comment=("/*", "*/"),
        rules=(
            (r"[.#]?[\w-]+(?=[^{}]*\{)", "tag"),
            (r"\b[\w-]+(?=\s*:)", "attribute"),
            (_DQ_STRING[0], "string"),
            (_SQ_STRING[0], "string"),
            (r"#[0-9a-fA-F]{3,8}\b", "number"),
            (r"\b\d+(?:\.\d+)?(?:px|em|rem|%|vh|vw|pt|s|ms)?\b", "number"),
            (r"@[\w-]+", "preprocessor"),
        ),
        multiline=_C_BLOCK,
    ),
    "markdown": Language(
        id="markdown",
        name="Markdown",
        extensions=(".md", ".markdown", ".mdown"),
        rules=(
            (r"^\s{0,3}#{1,6}\s.*$", "heading"),
            (r"\*\*[^*\n]+\*\*", "keyword"),
            (r"(?<!\*)\*[^*\n]+\*(?!\*)", "type"),
            (r"`[^`\n]+`", "string"),
            (r"\[[^\]\n]*\]\([^)\n]*\)", "link"),
            (r"^\s*(?:[-*+]|\d+\.)\s", "operator"),
            (r"^\s*>.*$", "comment"),
        ),
        multiline=(MultiLineRule(r"^\s*```", r"^\s*```", "string"),),
    ),
    "yaml": Language(
        id="yaml",
        name="YAML",
        extensions=(".yaml", ".yml"),
        filenames=(".clang-format",),
        line_comment="#",
        rules=(
            (r"#[^\n]*", "comment"),
            (r"^\s*[-\s]*([\w.\-/ ]+)(?=\s*:)", "attribute"),
            (_DQ_STRING[0], "string"),
            (_SQ_STRING[0], "string"),
            (r"\b(?:true|false|null|yes|no|on|off)\b", "keyword"),
            _NUMBER,
            (r"^\s*-\s", "operator"),
        ),
    ),
    "toml": Language(
        id="toml",
        name="TOML",
        extensions=(".toml",),
        filenames=("Cargo.lock",),
        line_comment="#",
        rules=(
            (r"#[^\n]*", "comment"),
            (r"^\s*\[.*\]\s*$", "tag"),
            (r"^\s*[\w.\-\"]+(?=\s*=)", "attribute"),
            (_DQ_STRING[0], "string"),
            (_SQ_STRING[0], "string"),
            (r"\b(?:true|false)\b", "keyword"),
            _NUMBER,
        ),
    ),
    "ini": Language(
        id="ini",
        name="INI",
        extensions=(".ini", ".cfg", ".conf", ".properties", ".editorconfig"),
        line_comment="#",
        rules=(
            (r"[#;][^\n]*", "comment"),
            (r"^\s*\[[^\]\n]+\]", "tag"),
            (r"^\s*[\w.\-]+(?=\s*[=:])", "attribute"),
            (_DQ_STRING[0], "string"),
            _NUMBER,
        ),
    ),
    "shell": Language(
        id="shell",
        name="Shell",
        extensions=(".sh", ".bash", ".zsh", ".ksh"),
        filenames=(".bashrc", ".zshrc", ".profile"),
        keywords=tuple(_SHELL_KEYWORDS),
        line_comment="#",
        rules=(
            (r"#[^\n]*", "comment"),
            (r"\$\{[^}\n]*\}|\$\w+", "builtin"),
            (_DQ_STRING[0], "string"),
            (_SQ_STRING[0], "string"),
            _NUMBER,
            _OPERATOR,
        ),
    ),
    "powershell": Language(
        id="powershell",
        name="PowerShell",
        extensions=(".ps1", ".psm1", ".psd1"),
        keywords=("if else elseif switch foreach for while do until break continue return function param begin "
                  "process end try catch finally throw class enum filter in").split(),
        line_comment="#",
        block_comment=("<#", "#>"),
        rules=(
            (r"#[^\n]*", "comment"),
            (r"\$[\w:]+", "builtin"),
            (r"-\w+", "attribute"),
            (_DQ_STRING[0], "string"),
            (_SQ_STRING[0], "string"),
            _NUMBER,
        ),
        multiline=(MultiLineRule(r"<#", r"#>", "comment"),),
        case_insensitive_keywords=True,
    ),
    "sql": Language(
        id="sql",
        name="SQL",
        extensions=(".sql", ".ddl"),
        keywords=tuple(_SQL_KEYWORDS),
        line_comment="--",
        block_comment=("/*", "*/"),
        rules=(
            (r"--[^\n]*", "comment"),
            (_SQ_STRING[0], "string"),
            (_DQ_STRING[0], "string"),
            _NUMBER,
        ),
        multiline=_C_BLOCK,
        case_insensitive_keywords=True,
    ),
    "dockerfile": Language(
        id="dockerfile",
        name="Dockerfile",
        extensions=(".dockerfile",),
        filenames=("Dockerfile", "Containerfile"),
        keywords=("FROM RUN CMD LABEL MAINTAINER EXPOSE ENV ADD COPY ENTRYPOINT VOLUME USER "
                  "WORKDIR ARG ONBUILD STOPSIGNAL HEALTHCHECK SHELL AS").split(),
        line_comment="#",
        rules=((r"#[^\n]*", "comment"), (_DQ_STRING[0], "string"), (_SQ_STRING[0], "string"), _NUMBER),
    ),
    "diff": Language(
        id="diff",
        name="Diff",
        extensions=(".diff", ".patch"),
        rules=(
            (r"^\+.*$", "string"),
            (r"^-.*$", "error"),
            (r"^@@.*$", "function"),
            (r"^(?:diff|index|---|\+\+\+).*$", "keyword"),
        ),
    ),
    "log": Language(
        id="log",
        name="Log",
        extensions=(".log",),
        rules=(
            (r"\b(?:ERROR|FATAL|CRITICAL|SEVERE)\b", "error"),
            (r"\b(?:WARN|WARNING)\b", "preprocessor"),
            (r"\b(?:INFO|NOTICE)\b", "builtin"),
            (r"\b(?:DEBUG|TRACE)\b", "comment"),
            (r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?", "number"),
            (_DQ_STRING[0], "string"),
        ),
    ),
}

_EXTENSION_INDEX: dict[str, str] = {}
_FILENAME_INDEX: dict[str, str] = {}
for _lang in LANGUAGES.values():
    for _ext in _lang.extensions:
        _EXTENSION_INDEX[_ext.lower()] = _lang.id
    for _name in _lang.filenames:
        _FILENAME_INDEX[_name.lower()] = _lang.id

_SHEBANG_HINTS = (
    ("groovy", "groovy"),
    ("python", "python"),
    ("bash", "shell"),
    ("sh", "shell"),
    ("zsh", "shell"),
    ("node", "javascript"),
    ("pwsh", "powershell"),
)


def detect_language(path: str, sample: str = "") -> str:
    """Guess a language id from a file name, falling back to content sniffing."""
    base = os.path.basename(path)
    if base.lower() in _FILENAME_INDEX:
        return _FILENAME_INDEX[base.lower()]

    _, ext = os.path.splitext(base)
    if ext.lower() in _EXTENSION_INDEX:
        return _EXTENSION_INDEX[ext.lower()]

    stripped = sample.lstrip()
    if stripped.startswith("#!"):
        first_line = stripped.splitlines()[0].lower()
        for needle, lang in _SHEBANG_HINTS:
            if needle in first_line:
                return lang
    if stripped.startswith(("<?xml", "<!DOCTYPE html", "<html")):
        return "xml"
    if stripped[:1] in ("{", "[") and stripped.rstrip()[-1:] in ("}", "]"):
        return "json"
    return "plain"


def language_names() -> list[tuple[str, str]]:
    """(id, display name) pairs sorted for menus, with Plain Text first."""
    rest = sorted((lang.id, lang.name) for lang in LANGUAGES.values() if lang.id != "plain")
    return [("plain", "Plain Text"), *rest]


ALIASES: dict[str, str] = {
    "gradle": "groovy",
    "gvy": "groovy",
    "gy": "groovy",
    "gsh": "groovy",
    "html": "xml",
    "htm": "xml",
    "xhtml": "xml",
    "svg": "xml",
    "js": "javascript",
    "jsx": "javascript",
    "node": "javascript",
    "ts": "typescript",
    "tsx": "typescript",
    "py": "python",
    "python3": "python",
    "c++": "cpp",
    "cxx": "cpp",
    "c#": "csharp",
    "cs": "csharp",
    "golang": "go",
    "rs": "rust",
    "md": "markdown",
    "yml": "yaml",
    "sh": "shell",
    "bash": "shell",
    "zsh": "shell",
    "ps1": "powershell",
    "pwsh": "powershell",
    "scss": "css",
    "sass": "css",
    "less": "css",
    "text": "plain",
    "txt": "plain",
}


def get_language(language_id: str) -> Language:
    """Look up a language by id, display name or alias (case-insensitive)."""
    if not language_id:
        return LANGUAGES["plain"]
    language = LANGUAGES.get(language_id)
    if language is not None:
        return language
    key = language_id.strip().lower()
    language = LANGUAGES.get(key)
    if language is not None:
        return language
    alias = ALIASES.get(key)
    if alias is not None:
        return LANGUAGES[alias]
    for candidate in LANGUAGES.values():
        if candidate.name.lower() == key:
            return candidate
    return LANGUAGES["plain"]
