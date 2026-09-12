"""Cipherpad - a Qt Quick text editor with transparent file encryption."""

from __future__ import annotations

__version__ = "1.0.0"


def main() -> None:
    """Console/GUI script entry point."""
    from .app import run

    raise SystemExit(run())
