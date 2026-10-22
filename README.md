# Cipherpad

A desktop text editor built with **PySide6** and **Qt Quick (QML)** that edits ordinary text
files *and* passphrase-encrypted files transparently. Preferences — font, size, colours,
theme, editor behaviour, window geometry, recent files and session — are persisted between
runs.

The Python side owns everything that benefits from real code (encryption, file I/O,
syntax highlighting, search, text transformations, preferences); QML owns the UI.
Confirmation and message dialogs focus a default button for keyboard use (Enter
activates it); destructive confirmations default to Cancel or No. Text-entry
prompts keep their input field focused.

---

## Features

### Files
- Multiple documents in tabs, with per-tab modified indicator and close buttons
- Modified indicators clear when undo or manual edits restore the last loaded or
  saved text, provided encoding and line endings are also unchanged; redo updates
  them again.
- Open / Save / Save As / Reload from disk, recent-files list, optional session restore
- Multi-folder project explorer for browsing and managing files and folders
- Explorer right-click actions: create files/folders, rename, duplicate, cut/copy/paste,
  delete with confirmation, copy absolute/relative paths, and reveal in File Explorer.
  The explorer header also offers New File, New Folder and Paste for the selected folder
  (or the selected file's parent). Cut/copy/paste uses an app-local file clipboard.
  Existing destinations are never overwritten; cross-volume cut/paste reports an error.
  Delete uses Trash/Recycle Bin and closes clean open tabs, but refuses items with
  unsaved documents and workspace roots. Renaming/moving keeps open tabs and watchers in sync.
- **Explorer multi-selection**: Ctrl-click toggles files or folders; Shift-click
  and Shift+Up/Down/Home/End select a visible range. Ctrl+A selects all visible
  non-root items; Escape clears the selection. Right-click preserves an existing
  selection. Cut/copy/paste (`Ctrl+X/C/V`), **Move Selected Items To...**, and
  confirmed Delete operate on the selection, including folders. **Shift+Delete**
  skips confirmation (still using Trash/Recycle Bin and the same safety checks).
  Selecting a folder
  and its children processes the folder only once. Bulk operations preflight root
  protections, destination conflicts and (for deletion) unsaved/pinned tabs before
  starting. An I/O failure stops the batch and reports partial completion; completed
  items are not rolled back, and failed/unprocessed cut items remain available to paste.
- Atomic saves (temp file + `os.replace`) so a crash never truncates your file
- External-change detection via `QFileSystemWatcher`
- Explorer watches visible directories, including empty collapsed folders, so files
  added inside newly created directories appear without a manual refresh.
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
- Selecting text highlights all exact, case-sensitive occurrences in that pane.
  A narrow overview beside the vertical scrollbar marks their document positions;
  click a marker to jump to the nearest occurrence. Clearing the selection clears
  the highlights; whitespace-only selections are ignored. Find highlighting remains
  independent and takes precedence where matches overlap.
  Qt Quick TextArea does not provide a built-in document minimap.
- **Code folding**: click the arrow beside a line number or use `Ctrl+Shift+[`
  to toggle a fold starting on the current line. The editor's right-click menu
  also offers **Toggle Fold**, **Fold All**, and **Unfold All**. Folding recognises
  bracketed blocks, multiline strings/comments, Python/YAML indentation,
  XML/HTML tags, Markdown headings/fences, TOML/INI sections, shell/SQL blocks,
  Dockerfile stages and diff sections. Plain text has no folds; other modes offer
  folds where their structure permits. Folding does not change saved text,
  modification state or undo history. Nested folds are preserved when an outer fold
  is reopened; navigating into hidden text reveals it. Folds are local to each pane
  and reset when text is edited, reloaded or the language changes.
- Find / Replace bar with case-sensitive, whole-word and regular-expression modes,
  match counter, wrap-around, Replace and Replace All
- Go to line, duplicate / delete / move / join lines, sort (asc/desc), unique lines,
  reverse lines, trim trailing whitespace, indent / unindent, tabs↔spaces
- **Page Up / Page Down** moves the caret and viewport by one visible page,
  including wrapped lines. Hold **Shift** to extend or shrink the selection.
  Navigation also works in read-only documents and targets the focused split pane.
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

### Command console, local Git & tab navigation
- **View > Command Console** (``Ctrl+` ``) opens a docked command input/output
  panel. Select a working directory, run an executable with double-quoted
  arguments, watch streamed stdout/stderr, send standard input, send EOF, stop
  the process, or clear output. Output history is bounded to 200,000 characters.
  Hiding the panel does not stop its command; exiting stops the directly managed
  process. Independently spawned/detached child processes are not managed.
- This is a portable **command console**, not a PTY or terminal emulator.
  Shell pipes, redirection and built-ins require explicitly invoking an installed
  shell. ANSI terminal controls and full-screen terminal programs are not supported.
  Commands run with your user permissions. Editor buffers are never automatically
  exported to the console.
- **View > Local Git** (`Ctrl+Alt+G`) displays repository branch and changed
  files. Refresh status, inspect working/staged unified diffs, stage/unstage a
  selected file, or enter a message and confirm a commit. Git must be installed
  on PATH. These operations use saved files, not unsaved editor buffers.
  Commits include **all staged repository changes**, including changes staged
  outside Cipherpad, and run configured hooks. Git operations have a 30-second
  timeout and a 4 MB output limit. Fetch, pull, push and discard are not offered.
- **Pin Tab / Unpin Tab** in the tab context menu, View menu or command palette
  protects against close-button, middle-click, `Ctrl+W` and bulk closure.
  Pinned tabs display `[P]` and must be unpinned before closing. Explorer deletion
  also refuses items containing pinned documents. Pins are session-only;
  application quit still uses the normal unsaved-changes confirmation.
- **Line bookmarks**: `Ctrl+F2` toggles the current line, `F2` jumps to the next,
  and `Shift+F2` to the previous bookmark, wrapping within the current tab.
  Click the left edge of the gutter to toggle its line marker. The View >
  Bookmarks menu and command palette also expose toggle/navigation/clear.
  Bookmark cursor anchors follow edits, including lines inserted above them.
  Deleting a bookmarked line moves its marker to the surviving line at that
  position. Markers are session-only and clear on reload or encrypted-tab locking;
  normal saves and split-editor changes preserve them.
- **Explorer comparison**: use Ctrl-click to select exactly two files, then
  press `Ctrl+D` while the explorer has focus, or choose **Compare Selected
  Files** from a selected file's right-click menu. Ctrl-click does not open files.
  Ordinary clicks continue to open a file. The diff uses saved disk contents;
  binary, encrypted, missing and oversized files report errors without changing
  editor buffers. `Ctrl+D` in the editor retains Duplicate Line behavior.
- Implemented with portable Qt process and text-document APIs; no new dependency
  is needed beyond an installed Git CLI. Windows execution is tested; macOS/Linux
  execution has not been verified here.

### Split editors, inspection & previews
- **View > Split Editors** (`Ctrl+Alt+S`, or the **||** toolbar button) shows two
  different open documents side by side. If only one document is open, a new empty
  tab is created for the other side. Clicking an editor makes it the target for
  save, undo, find, formatting and status information. Selecting a different tab
  replaces the active side; dragging the divider resizes the panes. Turning split
  off preserves both buffers, selections and undo histories. Closing either
  displayed tab returns to a single editor.
- **Tools > Compare with Disk / Compare with File / Compare with Open Tab**
  offers a syntax-coloured unified diff and read-only side-by-side versions.
  Open-tab comparison includes unsaved buffers. A final-newline-only change is
  shown explicitly. Comparisons are limited to 2 million characters and 20,000
  lines per side; disk reads are capped at 8 MB.
- External file changes open a comparison instead of silently replacing edits.
  **Reload Disk Version** and **File > Reload from Disk** require confirmation
  before discarding unsaved edits. Atomic file replacements re-establish the
  file watcher. Identical disk/editor content does not open a change dialog.
- Unlocked encrypted documents can be compared with disk or another unlocked
  tab. Decrypted snapshots, diffs and previews stay in memory, and closing a
  comparison clears its snapshots. Comparing a separate encrypted file requires
  opening/unlocking it first, then using **Compare with Open Tab**.
- **Tools > Validate JSON / XML** reports syntax errors with line/column and
  **Go to Error** navigation. Optionally select a UTF-8 JSON Schema or XSD:
  JSON schema failures identify the instance's JSON pointer; XSD failures include
  line information. Schema syntax errors are distinguished from document errors.
  Only self-contained schemas and same-document JSON references are supported;
  remote references, DTDs and XSD imports/includes are rejected.
- **View > JSON Tree** browses objects, arrays and scalar values with collapsible
  branches and copyable JSON pointers. Duplicate keys and original number lexemes
  are retained. Views are capped at 10,000 nodes; long row labels are truncated.
- **View > Markdown Preview** renders a live, read-only preview beside the editor,
  including headings, lists, tables and code blocks supported by Qt's GitHub
  Markdown dialect. It is offline: image resources are never loaded, images are
  replaced with an omission label, and links do not launch a browser.
- Validation, JSON viewing and Markdown preview are limited to 2 million source
  characters. All these commands are also searchable in the command palette.
- These features use Qt/Python APIs on Windows, macOS and Linux; no OS-specific
  commands or external preview tools are required.

### Crash recovery, locking & clipboard protection
- Modified ordinary tabs (including untitled tabs) are snapshotted **every 30
  seconds**, without saving over the original files. Recovery is enabled by
  default and can be disabled in **Preferences > Files**. Snapshots contain
  **plaintext** and are stored in Qt's per-user application-data directory,
  under `recovery`. Each snapshot is limited to 8 MB.
- After an interrupted session, a recovery dialog offers **Restore** or
  confirmed **Discard** for each snapshot. Restore creates a modified untitled
  tab, preserving text, language, encoding and line endings. It never overwrites
  the original file, which may have changed meanwhile. The dialog is also
  available under **Tools > Recover Interrupted Session** and in the command
  palette. Other running Cipherpad instances are excluded using Qt session locks.
- Successful saves, explicit tab closure/discard, disabling recovery and normal
  application exit remove the current session's snapshots. Closing the recovery
  dialog leaves older snapshots available for a later decision.
- **Encrypted tabs never write persistent recovery snapshots**, and therefore
  their unsaved edits cannot be recovered after a process crash.
- **Tools > Lock Encrypted Tab** / **Unlock Tab** (`Ctrl+Alt+L`, toolbar,
  editor right-click menu or command palette) locks the current encrypted tab.
  Unsaved edits are encrypted in memory using its existing passphrase. The
  editor and inspection views are cleared and saving/reloading is blocked until
  that passphrase is entered again. Locking resets undo history and cursor
  position, but retains text, modified state and document settings. Locking is
  **manual only**; there is no automatic idle locking.
- Text copied/cut from encrypted editors, comparisons and Markdown previews,
  and pointers copied from encrypted JSON trees, expires from the system
  clipboard after **30 seconds** by default. **Preferences > Files** allows
  0 (off) through 3600 seconds. Clipboard ownership is tagged, so content
  subsequently copied by another application is not cleared, even if the text
  is identical. Ordinary-tab copies do not expire. Outstanding protected
  clipboard content is also cleared on normal exit.
- Locking cannot guarantee zeroisation of Python/Qt allocations or protection
  from OS swap, crash dumps or clipboard-history services. Clipboard expiry
  does not remove copies retained by other applications or clipboard history.
- Recovery, locking and clipboard protection use portable Qt/Python APIs, with
  no platform-specific commands or external key storage.

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
- Dependencies: `pyside6 >= 6.9`, `cryptography >= 43`, `jsonschema >= 4.23`,
  `lxml >= 6` (portable JSON Schema and XSD validation)

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
covers crypto, documents, search, text operations, languages, preferences,
inspection, crash recovery, encrypted-tab locking and clipboard protection.

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
| Toggle split editors | `Ctrl+Alt+S` |
| Lock / unlock encrypted tab | `Ctrl+Alt+L` |
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
