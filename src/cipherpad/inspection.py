"""Portable, in-memory structured-document inspection and comparison."""

from __future__ import annotations

import difflib
import json
import re
from xml.parsers import expat

from jsonschema import validators
from jsonschema.exceptions import SchemaError
from referencing.exceptions import Unresolvable
from lxml import etree
from PySide6.QtCore import QByteArray, QObject, Slot, QUrl
from PySide6.QtGui import QTextDocument
from .document import read_disk_snapshot

MAX_INSPECTION_CHARS = 2_000_000
MAX_TREE_NODES = 10_000


def local_path(path: str) -> str:
    url = QUrl(path)
    return url.toLocalFile() if url.isLocalFile() else path


def reject_json_constant(value: str):
    raise ValueError(f"{value} is not a valid JSON number")


def strict_json(text: str):
    return json.loads(text, parse_constant=reject_json_constant)


def reject_doctype(*_args) -> None:
    raise ValueError("DOCTYPE declarations are not supported; external entities are never loaded.")


def parse_xml(text: str) -> None:
    parser = expat.ParserCreate()
    parser.StartDoctypeDeclHandler = reject_doctype
    parser.Parse(text, True)


def xml_bytes(text: str) -> bytes:
    # The editor already decoded the source, so its original declaration no
    # longer describes the UTF-8 byte stream passed to libxml.
    text = re.sub(r'^(\ufeff?\s*<\?xml\b[^>]*\bencoding\s*=\s*)(["\'])[^"\']*\2',
                  lambda match: match[1] + match[2] + "UTF-8" + match[2], text, count=1)
    return text.encode("utf-8")


def _reject_remote_refs(value) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in ("$ref", "$dynamicRef", "$recursiveRef") and (
                not isinstance(child, str) or not child.startswith("#")
            ):
                raise ValueError("Only same-document (#...) JSON schema references are supported.")
            _reject_remote_refs(child)
    elif isinstance(value, list):
        for child in value:
            _reject_remote_refs(child)


def _read_schema(path: str) -> str:
    with open(local_path(path), "rb") as stream:
        data = stream.read(MAX_INSPECTION_CHARS + 1)
    if len(data) > MAX_INSPECTION_CHARS:
        raise ValueError("Schema exceeds the 2 MB inspection limit.")
    return data.decode("utf-8-sig")


def validate_document(text: str, language: str, schema_path: str = "") -> dict:
    if len(text) > MAX_INSPECTION_CHARS:
        return {"valid": False, "error": "Document exceeds the 2 million character inspection limit.", "line": 0, "column": 0}
    reading_schema = False
    try:
        if language == "json":
            value = strict_json(text)
            if schema_path:
                reading_schema = True
                schema = strict_json(_read_schema(schema_path))
                _reject_remote_refs(schema)
                validator_type = validators.validator_for(schema)
                validator_type.check_schema(schema)
                reading_schema = False
                failure = next(validator_type(schema).iter_errors(value), None)
                if failure is not None:
                    return {
                        "valid": False, "error": failure.message,
                        "instancePath": "/" + "/".join(str(part).replace("~", "~0").replace("/", "~1") for part in failure.absolute_path),
                        "line": 0, "column": 0,
                    }
        elif language == "xml":
            parse_xml(text)
            if schema_path:
                reading_schema = True
                schema_text = _read_schema(schema_path)
                parse_xml(schema_text)
                parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
                schema_root = etree.fromstring(xml_bytes(schema_text), parser)
                for node in schema_root.iter():
                    if node.tag in ("{http://www.w3.org/2001/XMLSchema}include",
                                    "{http://www.w3.org/2001/XMLSchema}import",
                                    "{http://www.w3.org/2001/XMLSchema}redefine",
                                    "{http://www.w3.org/2001/XMLSchema}override"):
                        raise ValueError("XSD includes/imports are not supported; use a self-contained schema.")
                schema = etree.XMLSchema(schema_root)
                reading_schema = False
                document = etree.fromstring(xml_bytes(text), parser)
                if not schema.validate(document):
                    failure = schema.error_log.last_error
                    return {"valid": False, "error": str(failure.message), "line": failure.line,
                            "column": max(1, failure.column)}
        else:
            raise ValueError("Validation is available for JSON and XML only.")
    except json.JSONDecodeError as exc:
        if reading_schema:
            return {"valid": False, "error": f"Schema error at line {exc.lineno}, column {exc.colno}: {exc.msg}", "line": 0, "column": 0}
        return {"valid": False, "error": exc.msg, "line": exc.lineno, "column": exc.colno}
    except expat.ExpatError as exc:
        if reading_schema:
            return {"valid": False, "error": f"Schema error: {exc}", "line": 0, "column": 0}
        return {"valid": False, "error": str(exc), "line": exc.lineno, "column": exc.offset + 1}
    except (OSError, UnicodeError, ValueError, RecursionError, SchemaError, Unresolvable, etree.LxmlError) as exc:
        return {"valid": False, "error": str(exc), "line": 0, "column": 0}
    return {"valid": True, "error": "", "line": 0, "column": 0}


class _JsonObject(list):
    pass


class _JsonNumber(str):
    pass


def json_nodes(text: str, limit: int = MAX_TREE_NODES) -> dict:
    if len(text) > MAX_INSPECTION_CHARS:
        return {"error": "Document exceeds the 2 million character inspection limit.", "nodes": []}
    try:
        value = json.loads(text, parse_int=_JsonNumber, parse_float=_JsonNumber,
                           parse_constant=reject_json_constant,
                           object_pairs_hook=_JsonObject)
    except (ValueError, RecursionError) as exc:
        return {"error": str(exc), "nodes": []}
    nodes: list[dict] = []
    limited = False
    pending = [("$", value, 0, "", -1)]
    while pending:
        name, value, depth, pointer, parent = pending.pop()
        if len(nodes) >= limit:
            return {"error": "", "nodes": nodes, "limited": True}
        container = isinstance(value, list)
        kind = ("object" if isinstance(value, _JsonObject) else "array" if isinstance(value, list)
                else "null" if value is None else "boolean" if isinstance(value, bool)
                else "number" if isinstance(value, _JsonNumber) else "string")
        label = f"{name}: {kind}"
        label += f" ({len(value)})" if container else " = " + (
            str(value) if isinstance(value, _JsonNumber) else json.dumps(value, ensure_ascii=False)
        )
        index = len(nodes)
        nodes.append({"label": label[:500], "depth": depth, "pointer": pointer,
                      "parent": parent, "container": container, "index": index})
        if container:
            capacity = max(0, limit - len(nodes) - len(pending))
            child_count = len(value)
            limited |= child_count > capacity
            children = value[:capacity] if isinstance(value, _JsonObject) else list(enumerate(value[:capacity]))
            for key, child in reversed(children):
                escaped = str(key).replace("~", "~0").replace("/", "~1")
                pending.append((str(key), child, depth + 1, pointer + "/" + escaped, index))
    return {"error": "", "nodes": nodes, "limited": limited}


def compare_text(left: str, right: str, left_name: str, right_name: str) -> dict:
    if max(len(left), len(right)) > MAX_INSPECTION_CHARS:
        return {"error": "Comparison exceeds the 2 million character inspection limit."}
    left_lines, right_lines = left.splitlines(keepends=True), right.splitlines(keepends=True)
    if max(len(left_lines), len(right_lines)) > 20_000:
        return {"error": "Comparison is limited to 20,000 lines per side."}
    lines = list(difflib.unified_diff(left_lines, right_lines, fromfile=left_name, tofile=right_name))
    # A newline marker is required to distinguish a final-newline-only change.
    output: list[str] = []
    for line in lines:
        output.append(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n")
    return {"error": "", "equal": left == right, "diff": "".join(output),
            "left": left, "right": right, "leftName": left_name, "rightName": right_name}


class _OfflineDocument(QTextDocument):
    def loadResource(self, resource_type: int, url: QUrl):
        return QByteArray()


class InspectionTools(QObject):
    @Slot(str, result="QVariantMap")
    def readFile(self, path: str) -> dict:
        return read_disk_snapshot(local_path(path))

    @Slot(str, str, str, result="QVariantMap")
    def validate(self, text: str, language: str, schema_path: str) -> dict:
        return validate_document(text, language, schema_path)

    @Slot(str, result="QVariantMap")
    def jsonTree(self, text: str) -> dict:
        return json_nodes(text)

    @Slot(str, str, str, str, result="QVariantMap")
    def compare(self, left: str, right: str, left_name: str, right_name: str) -> dict:
        return compare_text(left, right, left_name, right_name)

    @Slot(str, result="QVariantMap")
    def markdown(self, text: str) -> dict:
        if len(text) > MAX_INSPECTION_CHARS:
            return {"error": "Markdown exceeds the 2 million character preview limit."}
        document = _OfflineDocument()
        document.setMarkdown(text, QTextDocument.MarkdownFeature.MarkdownDialectGitHub)
        html = re.sub(r"<img\b[^>]*>", "[Image omitted]", document.toHtml(), flags=re.IGNORECASE)
        return {"error": "", "html": html}
