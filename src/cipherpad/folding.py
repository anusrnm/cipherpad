"""Language-aware, 1-based inclusive folding ranges without changing text."""

from __future__ import annotations

import re
from bisect import bisect_right

from .languages import get_language


def fold_ranges(text: str, language: str) -> dict[int, int]:
    definition = get_language(language)
    if definition.id == "plain":
        return {}
    lines = text.split("\n")
    ranges: dict[int, int] = {}
    newlines = [match.start() for match in re.finditer("\n", text)]

    def line_at(position: int) -> int:
        return bisect_right(newlines, position) + 1

    def add(start: int, end: int) -> None:
        if end > start:
            ranges[start] = max(end, ranges.get(start, end))

    # Consume strings/comments before structural delimiters. Keep newlines so
    # masked text has exactly the same line coordinates as the source.
    patterns: list[str] = []
    for rule in definition.multiline:
        start = rule.start.replace(r"\s", r"[^\S\n]")
        end = rule.end.replace(r"\s", r"[^\S\n]")
        patterns.append(f"(?:{start})[\\s\\S]*?(?:{end}|\\Z)")
    if definition.line_comment:
        patterns.append(re.escape(definition.line_comment) + r"[^\n]*")
    patterns.extend(
        pattern for pattern, style in definition.rules
        if style == "string" or (style == "comment" and not definition.line_comment)
    )
    if definition.id == "ini":
        patterns.append(r";[^\n]*")
    masked = text
    if patterns:
        def mask(match: re.Match[str]) -> str:
            start = line_at(match.start())
            add(start, start + match.group().count("\n"))
            return re.sub(r"[^\n]", " ", match.group())

        masked = re.sub("|".join(f"(?:{pattern})" for pattern in patterns), mask, text, flags=re.MULTILINE)
    clean = masked.split("\n")
    stack: list[tuple[str, int]] = []
    pairs = {")": "(", "]": "[", "}": "{"}
    for number, line in enumerate(clean, 1):
        for char in line:
            if char in "([{":
                stack.append((char, number))
            elif char in pairs and stack and stack[-1][0] == pairs[char]:
                _, start = stack.pop()
                add(start, number)

    if definition.id in {"python", "yaml"}:
        indentation: list[tuple[int, int]] = []
        last = 0
        for number, line in enumerate(clean, 1):
            if not line.strip():
                continue
            indent = len(line.expandtabs(8)) - len(line.expandtabs(8).lstrip())
            while indentation and indent <= indentation[-1][0]:
                _, start = indentation.pop()
                add(start, last)
            if line.rstrip().endswith(":") or (definition.id == "yaml" and line.rstrip().endswith(("|", ">"))):
                indentation.append((indent, number))
            last = number
        for _, start in indentation:
            add(start, last)

    if definition.id == "xml":
        tags: list[tuple[str, int]] = []
        # Attribute values may contain '>'; don't terminate a tag inside quotes.
        for match in re.finditer(r"<(/?)([\w:.-]+)\b(?:\"[^\"]*\"|'[^']*'|[^'\">])*>", masked):
            closing, name = match.group(1, 2)
            name = name.lower()
            number = line_at(match.start())
            if closing:
                if tags and tags[-1][0] == name:
                    _, start = tags.pop()
                    add(start, number)
            elif not match.group().endswith("/>") and name not in {
                "area", "base", "br", "col", "embed", "hr", "img", "input",
                "link", "meta", "param", "source", "track", "wbr",
            }:
                tags.append((name, number))

    section_pattern = {
        "markdown": r"^(#{1,6})\s+",
        "toml": r"^\s*(\[)[^\n]*\]\s*$",
        "ini": r"^\s*(\[)[^\n]*\]\s*$",
        "diff": r"^((?:diff |@@))[^\n]*",
        "dockerfile": r"^((?i:FROM))\s+",
    }.get(definition.id)
    if section_pattern:
        sections: list[tuple[int, int]] = []
        for number, line in enumerate(clean if definition.id == "markdown" else lines, 1):
            match = re.match(section_pattern, line)
            if match:
                level = len(match.group(1)) if definition.id == "markdown" else 1
                while sections and level <= sections[-1][0]:
                    _, start = sections.pop()
                    add(start, number - 1)
                sections.append((level, number))
        for _, start in sections:
            add(start, len(lines))

    if definition.id in {"shell", "sql"}:
        starts: list[int] = []
        pattern = r"\b(if|case|do|fi|esac|done)\b" if definition.id == "shell" else r"\b(begin|case|end)\b"
        closing = {"fi", "esac", "done", "end"}
        for number, line in enumerate(clean, 1):
            for token in re.findall(pattern, line, re.IGNORECASE):
                if token.lower() in closing:
                    if starts:
                        add(starts.pop(), number)
                else:
                    starts.append(number)
    return ranges
