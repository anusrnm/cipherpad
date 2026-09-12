# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Cipherpad.
#
# Build (from the repo root, with the project's venv active or via `uv run`):
#     uv run pyinstaller packaging/cipherpad.spec
#
# The resulting one-folder distribution is written to dist/cipherpad/ with
# cipherpad.exe (Windows) / cipherpad (Linux/macOS) as the launcher, and the
# QML sources bundled alongside it under cipherpad/qml/.

import os

# SPECPATH is provided by PyInstaller and points at the directory containing
# this file; resolve everything relative to the repo root so the build works
# regardless of the current working directory it is invoked from.
ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
SRC = os.path.join(ROOT, "src")

a = Analysis(
    [os.path.join(SPECPATH, "entrypoint.py")],
    pathex=[SRC],
    binaries=[],
    # Ship the QML sources next to the frozen app; app.py locates them via
    # Path(__file__).parent / "qml", which resolves correctly under both a
    # normal install and a PyInstaller onedir bundle.
    datas=[(os.path.join(SRC, "cipherpad", "qml"), os.path.join("cipherpad", "qml"))],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='cipherpad',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='cipherpad',
)
