# Cipherpad

A desktop text editor built with **PySide6** and **Qt Quick (QML)** that edits ordinary text
files *and* passphrase-encrypted files transparently. Preferences — font, size, colours,
theme, editor behaviour, window geometry, recent files and session — are persisted between
runs.

The Python side owns everything that benefits from real code (encryption, file I/O,
syntax highlighting, search, text transformations, preferences); QML owns the UI.

---

## Features

### Files
- Multiple documents in tabs, with per-tab modified indicator and close buttons
- Open / Save / Save As / Reload from disk, recent-files list, optional session restore
- Multi-folder project explorer for browsing and managing files and folders
- Explorer right-click actions: create files/folders, rename, duplicate, cut/copy/paste,
  delete with confirmation, copy absolute/relative paths, and reveal in File Explorer.
  The explorer header also offers New File, New Folder and Paste for the selected folder
  (or the selected file's parent). Cut/copy/paste uses an app-local file clipboard.
  Existing destinations are never overwritten; cross-volume cut/paste reports an error.
  Delete uses Trash/Recycle Bin and closes clean open tabs, but refuses items with
  unsaved documents and workspace roots. Renaming/moving keeps open tabs and watchers in sync.
- Atomic saves (temp file + `os.replace`) so a crash never truncates your file
- External-change detection via `QFileSystemWatcher`
- Encoding and line-ending (LF / CRLF / CR) detection, preserved on save
- Refuses to open binary files instead of mangling them

### Workspace navigation
- **Quick Open** (`Ctrl+P`): fuzzy filename lookup across all workspace folders,
  including collapsed folders. Use Up/Down and Enter or click a result.
- **Search Workspace** (`Ctrl+Shift+F`): literal text search with filename globs
  (for example `*.py;*.qml`), case and whole-word options, and clickable line/column
  results. Searches saved files on disk, not unsaved editor buffers; stale results
  and modified tabs are reported rather than selecting an incorrect location.
- Cancellable background scans, capped at 20,000 entries and 1,000 search matches.
  Search skips binary files, encrypted containers (regardless of extension),
  `.enc`/`.aes` files and files above 2 MiB. Workspace discovery does not follow
  symlinks or directory junctions. Limits, skips and read failures are reported.
- **Command Palette** (`F1`): searchable file, editing, formatting, workspace and
  preferences commands. Unavailable commands are disabled. Accessible, along with
  Quick Open and workspace search, from menus and the toolbar.
- Explorer filename/path filtering (substring or filename glob) retains ancestor
  folders and leaves normal expansion state intact. Press Escape to clear.
- **Preferences > Files > Workspace files** controls hidden-file visibility and
  semicolon-separated ignore globs. Explicit ignores still apply when hidden files
  are visible; remove default exclusions to opt in. Explorer, Quick Open and
  workspace search share these settings. These are application globs, not `.gitignore`
  parsing rules.

### Encryption
- **Save Encrypted As…** writes an encrypted container; opening it prompts for the passphrase
- **Encrypt File…**, **Change Passphrase…** and **Remove Encryption** on an open document
- Live passphrase-strength feedback when choosing a new passphrase
- Encrypted documents are always stored as UTF-8 internally

### Editing
- Syntax highlighting for 25 languages (Python, JS/TS, QML, Groovy/Gradle, C/C++, Java, C#, Go, Rust,
  JSON, XML/HTML, CSS, Markdown, YAML, TOML, INI, shell, PowerShell, SQL, Dockerfile,
  diff, log, …), auto-detected from file name, shebang or content, and overridable from
  the toolbar
- Line numbers, current-line highlight, whitespace visualisation, word wrap
- Find / Replace bar with case-sensitive, whole-word and regular-expression modes,
  match counter, wrap-around, Replace and Replace All
- Go to line, duplicate / delete / move / join lines, sort (asc/desc), unique lines,
  reverse lines, trim trailing whitespace, indent / unindent, tabs↔spaces
- Case conversion (UPPER, lower, Title, tOGGLE), toggle comment (line **or** block
  comment depending on the language), insert timestamp
- **Format > Pretty Print** for JSON and XML: formats the whole document with the
  configured spaces/tab indentation and supports undo. Invalid input is reported
  without changing the document. XML mixed content, CDATA and `xml:space="preserve"`
  are preserved; XML with a DOCTYPE is not formatted.
  Also available via **Ctrl+Shift+P**, the **{}** toolbar button, and the editor's
  right-click menu. Disabled for other languages and read-only documents.
- Document statistics (characters, words, lines, paragraphs)
- All transformations go through an undoable range-replacement layer, so `Ctrl+Z` works

### Appearance & preferences
- Built-in themes plus fully editable colours, including a per-token syntax palette
- Font family, size, line height, tab width, insert-spaces, zoom in/out/reset
- Toggleable toolbar and status bar; status bar shows cursor position, selection,
  language, encoding, line ending and encryption state
- On-save clean-ups: trim trailing whitespace, ensure a final newline
- Window size/maximised state remembered
- Everything is stored with `QSettings` (registry on Windows, plist/ini elsewhere)

---

## Requirements

- Python **3.14+**
- [`uv`](https://docs.astral.sh/uv/)
- Dependencies: `pyside6 >= 6.9`, `cryptography >= 43`

## Install & run

```powershell
uv sync
uv run python -m cipherpad
```

Open files directly:

```powershell
uv run python -m cipherpad path\to\file.txt path\to\secret.enc
```

Installed entry points: `cipherpad` (console) and `cipherpad-gui` (no console window).

## Tests

```powershell
uv run pytest -q
```

The suite runs headless (`QT_QPA_PLATFORM=offscreen`, set in `tests/conftest.py`) and
covers crypto, documents, search, text operations, languages and preferences.

---

## Building a standalone executable

A distributable Windows build (no Python install required on the target machine) is
produced with [PyInstaller](https://pyinstaller.org/), configured via
[`packaging/cipherpad.spec`](packaging/cipherpad.spec). PyInstaller is a `dev` dependency, so
`uv sync` (or the build script below) pulls it in automatically.

```powershell
.\scripts\build_exe.ps1

# or, to wipe any previous build\ and dist\ output first:
.\scripts\build_exe.ps1 -Clean
```

This is equivalent to running `uv run pyinstaller packaging\cipherpad.spec --noconfirm`
directly. Either way, the output is a **onedir** build at `dist\cipherpad\`, containing
`cipherpad.exe` plus all bundled dependencies and QML sources. To distribute the app, zip
the entire `dist\cipherpad` folder — the executable relies on the other files next to it.

Notes:
- The spec builds a windowed app (no console window); QML files are bundled from
  `src/cipherpad/qml`, so no separate installation step is needed on the target machine.
- Rebuild whenever source or QML files change — nothing is done incrementally.
- If you'd rather use Nuitka (via `pyside6-deploy`), a C/C++ compiler toolchain (MSVC or
  MinGW) must be installed first; PyInstaller was chosen here specifically to avoid that
  requirement.

---

## Keyboard shortcuts

| Action | Shortcut |
| --- | --- |
| New / Open / Save / Save As | `Ctrl+N` / `Ctrl+O` / `Ctrl+S` / `Ctrl+Shift+S` |
| Close tab / Quit | `Ctrl+W` / `Ctrl+Q` |
| Undo / Redo | `Ctrl+Z` / `Ctrl+Y` |
| Cut / Copy / Paste / Select All | `Ctrl+X` / `Ctrl+C` / `Ctrl+V` / `Ctrl+A` |
| Find / Replace | `Ctrl+F` / `Ctrl+H` |
| Search workspace | `Ctrl+Shift+F` |
| Quick Open | `Ctrl+P` |
| Command Palette | `F1` |
| Find next / previous | `F3` / `Shift+F3` |
| Go to line | `Ctrl+G` |
| Duplicate line / Delete line | `Ctrl+D` / `Ctrl+Shift+K` |
| Move line up / down | `Alt+Up` / `Alt+Down` |
| Join lines | `Ctrl+J` |
| Toggle comment | `Ctrl+/` |
| Pretty Print JSON/XML | `Ctrl+Shift+P` |
| Toggle whitespace display | `Ctrl+Shift+E` |
| Zoom in / out / reset | `Ctrl++` / `Ctrl+-` / `Ctrl+0` |
| Next / previous tab | `Ctrl+Tab` / `Ctrl+Shift+Tab` |
| Preferences | `Ctrl+,` |

---

## Encryption details

Encrypted files use **AES-256-GCM** with a key derived from the passphrase by **scrypt**.

```
offset  size  field
0       8     magic  b"QMLENC\x01\x00"
8       1     KDF id (1 = scrypt)
9       1     log2(N)   default 15  (max 22)
10      1     r         default 8
11      1     p         default 1
12      16    salt      (random per save)
28      12    nonce     (random per save)
--------------------------------------------- 40-byte header
40      ..    AES-256-GCM ciphertext + 16-byte tag
```

> The `QMLENC` magic bytes are a fixed on-disk format tag, kept as-is (independent of the
> app's name) so files encrypted by earlier builds keep opening correctly.

The entire 40-byte header is fed to AES-GCM as **additional authenticated data**, so the
KDF parameters, salt and nonce cannot be tampered with. A fresh salt *and* nonce are
generated on every save. A wrong passphrase fails authentication and is reported as such —
never as corrupt plaintext.

> There is no passphrase recovery. If you lose it, the contents are gone.

---

## Project layout

```
src/cipherpad/
  app.py            application bootstrap, QML engine, context properties
  crypto.py         scrypt + AES-256-GCM container, passphrase strength
  document.py       Document / DocumentManager: load, save, encrypt, watch
  preferences.py    QSettings-backed properties, themes, recent files, session
  languages.py      language definitions, aliases, detection
  highlighter.py    QSyntaxHighlighter driving the QML text document
  search.py         stateless find / replace engine
  textops.py        all text transformations
  gutter.py         layout metrics shared by the editor and line-number gutter
  explorer.py       multi-folder project explorer model and file operations
  qml/              Main.qml, EditorPane.qml, dialogs and shared components
tests/              pytest suite
```

## License

Internal project — no license granted.
