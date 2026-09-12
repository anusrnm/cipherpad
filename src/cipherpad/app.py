"""Application entry point: wires the Python backend to the QML front end."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

# Importing these registers the @QmlElement types with the Cipherpad module.
from . import crypto, document, gutter, highlighter, preferences, search, textops  # noqa: F401

ORGANISATION = "Cipherpad"
APPLICATION = "Cipherpad"
QML_DIR = Path(__file__).parent / "qml"


def _configure_application() -> QGuiApplication:
    QCoreApplication.setOrganizationName(ORGANISATION)
    QCoreApplication.setOrganizationDomain("cipherpad.local")
    QCoreApplication.setApplicationName(APPLICATION)
    QCoreApplication.setApplicationVersion("1.0.0")

    # Basic is the only built-in style that allows full visual customisation,
    # which the theming system relies on.
    QQuickStyle.setStyle("Basic")

    app = QGuiApplication(sys.argv)
    app.setWindowIcon(QIcon())
    return app


def run(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    app = _configure_application()

    prefs = preferences.Preferences()
    manager = document.DocumentManager()
    search_engine = search.SearchEngine()
    text_ops = textops.TextOps()
    crypto_info = crypto.CryptoInfo()
    engine = QQmlApplicationEngine()

    context = engine.rootContext()
    context.setContextProperty("Prefs", prefs)
    context.setContextProperty("Documents", manager)
    context.setContextProperty("Search", search_engine)
    context.setContextProperty("TextOps", text_ops)
    context.setContextProperty("Crypto", crypto_info)
    context.setContextProperty("appVersion", QCoreApplication.applicationVersion())

    engine.addImportPath(str(QML_DIR))
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        print("Failed to load QML interface.", file=sys.stderr)
        return 1

    paths = [str(Path(arg).resolve()) for arg in argv if not arg.startswith("-")]
    if paths:
        manager.openMany(paths)
    elif prefs.restoreSession and manager.openMany(prefs.sessionFiles()):
        pass
    else:
        manager.newDocument()

    exit_code = app.exec()
    prefs.saveSession(manager.openPaths())
    prefs.sync()
    return exit_code


def main() -> None:
    raise SystemExit(run())
