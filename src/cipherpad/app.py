"""Application entry point: wires the Python backend to the QML front end."""

from __future__ import annotations

import gc
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QLoggingCategory, QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

# Importing these registers the @QmlElement types with the Cipherpad module.
from . import crypto, document, explorer, gutter, highlighter, preferences, search, textops  # noqa: F401
from .workspace import WorkspaceTools

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
    # Windows clipboard contention produces harmless retry noise on copy.
    QLoggingCategory.setFilterRules("qt.qpa.mime=false")

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
    project_explorer = explorer.ProjectExplorer()
    project_explorer.bind_documents(manager)
    workspace_tools = WorkspaceTools(project_explorer)
    app.aboutToQuit.connect(workspace_tools.shutdown)
    engine = QQmlApplicationEngine()

    context = engine.rootContext()
    context.setContextProperty("Prefs", prefs)
    context.setContextProperty("Documents", manager)
    context.setContextProperty("Search", search_engine)
    context.setContextProperty("TextOps", text_ops)
    context.setContextProperty("Crypto", crypto_info)
    context.setContextProperty("Explorer", project_explorer)
    context.setContextProperty("Workspace", workspace_tools)
    context.setContextProperty("appVersion", QCoreApplication.applicationVersion())

    engine.addImportPath(str(QML_DIR))
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        print("Failed to load QML interface.", file=sys.stderr)
        return 1

    if prefs.restoreSession:
        project_explorer.loadFolders(prefs.projectFolders())

    paths = [str(Path(arg).resolve()) for arg in argv if not arg.startswith("-")]
    folder_paths = [p for p in paths if Path(p).is_dir()]
    file_paths = [p for p in paths if not Path(p).is_dir()]

    for folder in folder_paths:
        project_explorer.addFolder(folder)

    if file_paths:
        manager.openMany(file_paths)
    elif prefs.restoreSession and manager.openMany(prefs.sessionFiles()):
        pass
    elif not folder_paths:
        manager.newDocument()

    app.setQuitOnLastWindowClosed(True)
    exit_code = app.exec()
    prefs.saveSession(manager.openPaths())
    prefs.saveProjectFolders(project_explorer.openFolders())
    prefs.sync()

    # Tear down QML before the application object so interpreter shutdown
    # doesn't destroy them in arbitrary GC order (which can hang the process).
    del engine
    gc.collect()
    return exit_code


def main() -> None:
    raise SystemExit(run())
