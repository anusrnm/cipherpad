"""Editor text transformations.

Each operation returns an :class:`EditSpan` describing the smallest replacement
that achieves the change, so the UI can apply it through ``TextArea.remove`` /
``TextArea.insert`` and keep Qt's native undo stack working.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from dataclasses import asdict, dataclass
from xml.dom import Node, minidom
from xml.parsers.expat import ExpatError

from PySide6.QtCore import QObject, Slot

from .languages import get_language

_WORD_RE = re.compile(r"\b\w[\w'-]*\b", re.UNICODE)
_OPEN_TO_CLOSE = {"(": ")", "[": "]", "{": "}", '"': '"', "'": "'", "`": "`"}
_CLOSERS = set(_OPEN_TO_CLOSE.values())
_INDENT_TRIGGERS = ("{", "[", "(", ":")


@dataclass(frozen=True)
class EditSpan:
    """A replacement plus the selection to restore afterwards."""

    start: int
    end: int
    text: str
    selection_start: int
    selection_end: int
    changed: bool = True

    def to_dict(self) -> dict:
        data = asdict(self)
        data["selectionStart"] = data.pop("selection_start")
        data["selectionEnd"] = data.pop("selection_end")
        return data


def _no_change(start: int, end: int) -> EditSpan:
    return EditSpan(start, start, "", start, end, changed=False)


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"{value} is not valid JSON")


def _pretty_json(text: str, indent: str) -> str:
    # Validate first, then format tokens so numbers, escapes and duplicate keys
    # survive unchanged instead of being round-tripped through Python values.
    json.loads(text, parse_int=str, parse_float=str, parse_constant=_reject_json_constant)
    tokens = re.findall(r'"(?:[^"\\]|\\.)*"|[{}\[\],:]|[^\s{}\[\],:]+', text)
    parts: list[str] = []
    depth = 0
    for index, token in enumerate(tokens):
        previous = tokens[index - 1] if index else ""
        following = tokens[index + 1] if index + 1 < len(tokens) else ""
        if token in ("{", "["):
            parts.append(token)
            depth += 1
            if following not in ("}", "]"):
                parts.append("\n" + indent * depth)
        elif token in ("}", "]"):
            depth -= 1
            if previous not in ("{", "["):
                parts.append("\n" + indent * depth)
            parts.append(token)
        elif token == ",":
            parts.append(",\n" + indent * depth)
        elif token == ":":
            parts.append(": ")
        else:
            parts.append(token)
    return "".join(parts)


def _pretty_xml(text: str, indent: str) -> str:
    with minidom.parseString(text) as document:
        if document.doctype is not None:
            raise ValueError("XML with a DOCTYPE is not supported by Pretty Print")

        def render(node: Node, depth: int) -> str:
            if not isinstance(node, minidom.Element):
                return node.toxml()
            children = list(node.childNodes)
            # Mixed content, CDATA and xml:space must not acquire new whitespace.
            if (
                node.getAttribute("xml:space") == "preserve"
                or any(child.nodeType == Node.CDATA_SECTION_NODE for child in children)
                or any(child.nodeType == Node.TEXT_NODE and child.nodeValue
                       and child.nodeValue.strip() for child in children)
                or not any(child.nodeType == Node.ELEMENT_NODE for child in children)
            ):
                return node.toxml()
            meaningful = [child for child in children if child.nodeType != Node.TEXT_NODE]
            opening = node.cloneNode(False).toxml()
            return (
                opening[:-2] + ">\n"
                + "\n".join(indent * (depth + 1) + render(child, depth + 1) for child in meaningful)
                + "\n" + indent * depth + f"</{node.tagName}>"
            )

        declaration = re.match(r"\s*(<\?xml\s+.*?\?>)", text, re.DOTALL)
        parts = [declaration.group(1)] if declaration else []
        parts.extend(render(child, 0) for child in document.childNodes)
        return "\n".join(parts)


def line_span(text: str, start: int, end: int) -> tuple[int, int]:
    """Expand a selection to cover whole lines."""
    start = max(0, min(start, len(text)))
    end = max(start, min(end, len(text)))
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end == -1:
        line_end = len(text)
    elif end > start and text[end - 1] == "\n" and end - 1 >= line_start:
        # A selection that already ends on a newline should not swallow the
        # following line as well.
        line_end = end - 1
    return line_start, line_end


def _replace_lines(text: str, start: int, end: int, transform) -> EditSpan:
    span_start, span_end = line_span(text, start, end)
    original = text[span_start:span_end]
    updated = transform(original)
    if updated == original:
        return _no_change(start, end)
    return EditSpan(span_start, span_end, updated, span_start, span_start + len(updated))


# ------------------------------------------------------------------ case ops
def transform_selection(text: str, start: int, end: int, func) -> EditSpan:
    if end <= start:
        return _no_change(start, end)
    original = text[start:end]
    updated = func(original)
    if updated == original:
        return _no_change(start, end)
    return EditSpan(start, end, updated, start, start + len(updated))


def to_title_case(value: str) -> str:
    return re.sub(r"\w+", lambda m: m.group(0).capitalize(), value)


def toggle_case(value: str) -> str:
    return "".join(c.lower() if c.isupper() else c.upper() for c in value)


# ----------------------------------------------------------------- line ops
def sort_lines(block: str, descending: bool = False, case_sensitive: bool = False, unique: bool = False) -> str:
    lines = block.split("\n")
    trailing = ""
    if lines and lines[-1] == "":
        lines.pop()
        trailing = "\n"
    key = (lambda s: s) if case_sensitive else (lambda s: s.lower())
    if unique:
        seen: dict[str, str] = {}
        for line in lines:
            seen.setdefault(key(line), line)
        lines = list(seen.values())
    lines.sort(key=key, reverse=descending)
    return "\n".join(lines) + trailing


def unique_lines(block: str) -> str:
    seen: set[str] = set()
    result = []
    for line in block.split("\n"):
        if line in seen:
            continue
        seen.add(line)
        result.append(line)
    return "\n".join(result)


def reverse_lines(block: str) -> str:
    lines = block.split("\n")
    trailing = ""
    if lines and lines[-1] == "":
        lines.pop()
        trailing = "\n"
    return "\n".join(reversed(lines)) + trailing


def trim_trailing_whitespace(block: str) -> str:
    return "\n".join(line.rstrip() for line in block.split("\n"))


def indent_block(block: str, indent: str) -> str:
    return "\n".join(indent + line if line.strip() else line for line in block.split("\n"))


def unindent_block(block: str, tab_width: int) -> str:
    result = []
    for line in block.split("\n"):
        if line.startswith("\t"):
            result.append(line[1:])
            continue
        removed = 0
        while removed < tab_width and removed < len(line) and line[removed] == " ":
            removed += 1
        result.append(line[removed:])
    return "\n".join(result)


def toggle_comment(block: str, marker: str) -> str:
    lines = block.split("\n")
    meaningful = [line for line in lines if line.strip()]
    if not meaningful:
        return block

    all_commented = all(line.lstrip().startswith(marker) for line in meaningful)
    if all_commented:
        result = []
        for line in lines:
            stripped = line.lstrip()
            if not stripped.startswith(marker):
                result.append(line)
                continue
            prefix = line[: len(line) - len(stripped)]
            body = stripped[len(marker) :]
            if body.startswith(" "):
                body = body[1:]
            result.append(prefix + body)
        return "\n".join(result)

    indent = min((len(line) - len(line.lstrip()) for line in meaningful), default=0)
    return "\n".join(
        line[:indent] + marker + " " + line[indent:] if line.strip() else line for line in lines
    )


def toggle_block_comment(block: str, opener: str, closer: str) -> str:
    """Comment toggle for languages without a line comment (HTML, CSS, ...)."""
    lines = block.split("\n")
    meaningful = [line for line in lines if line.strip()]
    if not meaningful:
        return block

    def wrapped(line: str) -> bool:
        stripped = line.strip()
        return stripped.startswith(opener) and stripped.endswith(closer)

    if all(wrapped(line) for line in meaningful):
        result = []
        for line in lines:
            if not wrapped(line):
                result.append(line)
                continue
            prefix = line[: len(line) - len(line.lstrip())]
            body = line.strip()[len(opener) : -len(closer)].strip()
            result.append(prefix + body)
        return "\n".join(result)

    indent = min(len(line) - len(line.lstrip()) for line in meaningful)
    return "\n".join(
        line[:indent] + f"{opener} {line[indent:].rstrip()} {closer}" if line.strip() else line
        for line in lines
    )


def convert_indentation(block: str, tab_width: int, to_spaces: bool) -> str:
    result = []
    for line in block.split("\n"):
        stripped = line.lstrip(" \t")
        indent = line[: len(line) - len(stripped)]
        columns = 0
        for char in indent:
            # A tab advances to the next tab stop rather than a fixed width.
            columns += (tab_width - columns % tab_width) if char == "\t" else 1
        if to_spaces:
            indent = " " * columns
        else:
            indent = "\t" * (columns // tab_width) + " " * (columns % tab_width)
        result.append(indent + stripped)
    return "\n".join(result)


# ------------------------------------------------------------- typing aids
def indent_for_newline(text: str, position: int, tab_width: int, use_spaces: bool) -> str:
    """Leading whitespace (plus one extra level after an opener) for a new line."""
    line_start = text.rfind("\n", 0, position) + 1
    line = text[line_start:position]
    stripped = line.lstrip(" \t")
    indent = line[: len(line) - len(stripped)]
    if line.rstrip().endswith(_INDENT_TRIGGERS):
        indent += " " * tab_width if use_spaces else "\t"
    return indent


def statistics(text: str, selection: str = "") -> dict:
    target = selection or text
    lines = target.count("\n") + 1 if target else 0
    return {
        "characters": len(target),
        "charactersNoSpaces": sum(1 for c in target if not c.isspace()),
        "words": len(_WORD_RE.findall(target)),
        "lines": lines,
        "paragraphs": len([p for p in re.split(r"\n\s*\n", target) if p.strip()]),
        "isSelection": bool(selection),
    }


class TextOps(QObject):
    """QML facade over the text transformations.

    Deliberately *not* decorated with ``@QmlElement``: this class is only ever
    exposed as the ``TextOps`` root context property (see ``app.py``), never
    instantiated from QML. Registering it as a QML type under the same name
    would make ``import Cipherpad`` shadow the context property with the bare
    type object, breaking every ``TextOps.<method>()`` call in QML with
    "Property '<method>' of object Cipherpad/TextOps is not a function".
    """

    @Slot(str, str, int, bool, result="QVariantMap")
    def prettyPrint(self, text: str, language_id: str, tab_width: int, use_spaces: bool) -> dict:
        indent = " " * max(1, tab_width) if use_spaces else "\t"
        try:
            language = get_language(language_id).id
            if language == "json":
                updated = _pretty_json(text, indent)
            elif language == "xml":
                updated = _pretty_xml(text, indent)
            else:
                raise ValueError("Pretty Print supports JSON and XML only")
        except (ValueError, ExpatError, RecursionError) as exc:
            return {"changed": False, "error": f"Pretty Print failed: {exc}"}
        if text.endswith("\n"):
            updated += "\n"
        if updated == text:
            return _no_change(0, 0).to_dict()
        # Qt cursor positions count UTF-16 code units, not Python characters.
        end = len(text.encode("utf-16-le")) // 2
        return EditSpan(0, end, updated, 0, 0).to_dict()

    # ------------------------------------------------------------ case ops
    @Slot(str, int, int, result="QVariantMap")
    def upperCase(self, text: str, start: int, end: int) -> dict:
        return transform_selection(text, start, end, str.upper).to_dict()

    @Slot(str, int, int, result="QVariantMap")
    def lowerCase(self, text: str, start: int, end: int) -> dict:
        return transform_selection(text, start, end, str.lower).to_dict()

    @Slot(str, int, int, result="QVariantMap")
    def titleCase(self, text: str, start: int, end: int) -> dict:
        return transform_selection(text, start, end, to_title_case).to_dict()

    @Slot(str, int, int, result="QVariantMap")
    def toggleCase(self, text: str, start: int, end: int) -> dict:
        return transform_selection(text, start, end, toggle_case).to_dict()

    # ------------------------------------------------------------ line ops
    @Slot(str, int, int, bool, bool, result="QVariantMap")
    def sortLines(self, text: str, start: int, end: int, descending: bool, unique: bool) -> dict:
        return _replace_lines(text, start, end, lambda b: sort_lines(b, descending, False, unique)).to_dict()

    @Slot(str, int, int, result="QVariantMap")
    def uniqueLines(self, text: str, start: int, end: int) -> dict:
        return _replace_lines(text, start, end, unique_lines).to_dict()

    @Slot(str, int, int, result="QVariantMap")
    def reverseLines(self, text: str, start: int, end: int) -> dict:
        return _replace_lines(text, start, end, reverse_lines).to_dict()

    @Slot(str, int, int, result="QVariantMap")
    def trimTrailingWhitespace(self, text: str, start: int, end: int) -> dict:
        return _replace_lines(text, start, end, trim_trailing_whitespace).to_dict()

    @Slot(str, int, int, result="QVariantMap")
    def duplicateLines(self, text: str, start: int, end: int) -> dict:
        span_start, span_end = line_span(text, start, end)
        block = text[span_start:span_end]
        return EditSpan(
            span_end, span_end, "\n" + block, span_end + 1, span_end + 1 + len(block)
        ).to_dict()

    @Slot(str, int, int, result="QVariantMap")
    def deleteLines(self, text: str, start: int, end: int) -> dict:
        span_start, span_end = line_span(text, start, end)
        if span_end < len(text) and text[span_end] == "\n":
            span_end += 1
        elif span_start > 0:
            span_start -= 1
        return EditSpan(span_start, span_end, "", span_start, span_start).to_dict()

    @Slot(str, int, int, result="QVariantMap")
    def moveLinesUp(self, text: str, start: int, end: int) -> dict:
        span_start, span_end = line_span(text, start, end)
        if span_start == 0:
            return _no_change(start, end).to_dict()
        previous_start = text.rfind("\n", 0, span_start - 1) + 1
        block = text[span_start:span_end]
        previous = text[previous_start : span_start - 1]
        merged = block + "\n" + previous
        return EditSpan(
            previous_start, span_end, merged, previous_start, previous_start + len(block)
        ).to_dict()

    @Slot(str, int, int, result="QVariantMap")
    def moveLinesDown(self, text: str, start: int, end: int) -> dict:
        span_start, span_end = line_span(text, start, end)
        if span_end >= len(text):
            return _no_change(start, end).to_dict()
        next_end = text.find("\n", span_end + 1)
        if next_end == -1:
            next_end = len(text)
        block = text[span_start:span_end]
        following = text[span_end + 1 : next_end]
        merged = following + "\n" + block
        new_start = span_start + len(following) + 1
        return EditSpan(span_start, next_end, merged, new_start, new_start + len(block)).to_dict()

    @Slot(str, int, int, result="QVariantMap")
    def joinLines(self, text: str, start: int, end: int) -> dict:
        span_start, span_end = line_span(text, start, end)
        block = text[span_start:span_end]
        if "\n" not in block:
            # Join the current line with the next one.
            next_end = text.find("\n", span_end + 1)
            if span_end >= len(text):
                return _no_change(start, end).to_dict()
            next_end = len(text) if next_end == -1 else next_end
            block = text[span_start:next_end]
            span_end = next_end
        merged = " ".join(part.strip() for part in block.split("\n") if part.strip())
        return EditSpan(span_start, span_end, merged, span_start, span_start + len(merged)).to_dict()

    # -------------------------------------------------------- indentation
    @Slot(str, int, int, int, bool, result="QVariantMap")
    def indent(self, text: str, start: int, end: int, tab_width: int, use_spaces: bool) -> dict:
        indent = " " * tab_width if use_spaces else "\t"
        return _replace_lines(text, start, end, lambda b: indent_block(b, indent)).to_dict()

    @Slot(str, int, int, int, result="QVariantMap")
    def unindent(self, text: str, start: int, end: int, tab_width: int) -> dict:
        return _replace_lines(text, start, end, lambda b: unindent_block(b, tab_width)).to_dict()

    @Slot(str, int, int, int, bool, result="QVariantMap")
    def convertIndentation(self, text: str, start: int, end: int, tab_width: int, to_spaces: bool) -> dict:
        return _replace_lines(
            text, start, end, lambda b: convert_indentation(b, tab_width, to_spaces)
        ).to_dict()

    @Slot(str, int, int, str, result="QVariantMap")
    def toggleComment(self, text: str, start: int, end: int, language_id: str) -> dict:
        language = get_language(language_id)
        marker = language.line_comment
        if not marker:
            block = language.block_comment
            if not block:
                return _no_change(start, end).to_dict()
            opener, closer = block
            return _replace_lines(
                text, start, end, lambda b: toggle_block_comment(b, opener, closer)
            ).to_dict()
        return _replace_lines(text, start, end, lambda b: toggle_comment(b, marker)).to_dict()

    # -------------------------------------------------------- typing aids
    @Slot(str, int, int, bool, result=str)
    def indentForNewline(self, text: str, position: int, tab_width: int, use_spaces: bool) -> str:
        return indent_for_newline(text, position, tab_width, use_spaces)

    @Slot(str, result=str)
    def closingBracket(self, character: str) -> str:
        return _OPEN_TO_CLOSE.get(character, "")

    @Slot(str, result=bool)
    def isClosingBracket(self, character: str) -> bool:
        return character in _CLOSERS

    # -------------------------------------------------------------- misc
    @Slot(str, result=str)
    def timestamp(self, fmt: str = "") -> str:
        now = _dt.datetime.now()
        if fmt == "iso":
            return now.isoformat(timespec="seconds")
        if fmt == "date":
            return now.strftime("%Y-%m-%d")
        if fmt == "time":
            return now.strftime("%H:%M:%S")
        return now.strftime("%Y-%m-%d %H:%M:%S")

    @Slot(str, str, result="QVariantMap")
    def statistics(self, text: str, selection: str = "") -> dict:
        return statistics(text, selection)

    @Slot(int, result=str)
    def indentString(self, tab_width: int) -> str:
        return " " * max(1, tab_width)

    @Slot(int, int, result=str)
    def tabFiller(self, column: int, tab_width: int) -> str:
        """Spaces needed to reach the next tab stop from *column* (0-based)."""
        width = max(1, tab_width)
        return " " * (width - column % width)
