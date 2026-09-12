"""Shared pytest fixtures."""

from __future__ import annotations

import os

import pytest

# The tests never show a window; force the headless platform plugin before Qt
# is imported anywhere.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402


@pytest.fixture(scope="session")
def qt_app() -> QGuiApplication:
    app = QGuiApplication.instance()
    if app is None:
        QCoreApplication.setOrganizationName("CipherpadTests")
        QCoreApplication.setOrganizationDomain("tests.cipherpad.local")
        QCoreApplication.setApplicationName("CipherpadTests")
        app = QGuiApplication([])
    return app
