"""Nonblocking command console and local Git operations using Qt processes."""

from __future__ import annotations

import codecs
import locale
import shutil
from pathlib import Path

from PySide6.QtCore import Property, QCoreApplication, QObject, QProcess, QProcessEnvironment, QTimer, QUrl, Signal, Slot
from PySide6.QtQml import QmlElement

QML_IMPORT_NAME = "Cipherpad"
QML_IMPORT_MAJOR_VERSION = 1
MAX_OUTPUT = 200_000
MAX_GIT_BYTES = 4_000_000


@QmlElement
class CommandConsole(QObject):
    changed = Signal()
    errorOccurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._output = ""
        self._busy = False
        self._stopping = False
        self._cwd = ""
        self._decoder = codecs.getincrementaldecoder(locale.getpreferredencoding(False))(errors="replace")
        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._read)
        self._process.finished.connect(self._finished)
        self._process.errorOccurred.connect(self._error)
        self._kill_timer = QTimer(self)
        self._kill_timer.setSingleShot(True)
        self._kill_timer.timeout.connect(self._process.kill)
        application = QCoreApplication.instance()
        if application is not None:
            application.aboutToQuit.connect(self.shutdown)

    @Property(str, notify=changed)
    def output(self) -> str:
        return self._output

    @Property(bool, notify=changed)
    def busy(self) -> bool:
        return self._busy

    @Property(str, notify=changed)
    def workingDirectory(self) -> str:
        return self._cwd

    @Property(str, constant=True)
    def homeDirectory(self) -> str:
        return str(Path.home())

    @Slot(str, result=str)
    def localDirectory(self, url: str) -> str:
        return QUrl(url).toLocalFile()

    def _append(self, text: str) -> None:
        combined = self._output + text
        prefix = "[Earlier output truncated]\n"
        self._output = combined if len(combined) <= MAX_OUTPUT else prefix + combined[-(MAX_OUTPUT - len(prefix)):]
        self.changed.emit()

    @Slot(str, str, result=bool)
    def runCommand(self, command: str, directory: str) -> bool:
        if self.busy:
            self.errorOccurred.emit("Stop the running command before starting another.")
            return False
        args = QProcess.splitCommand(command)
        if not args or not Path(directory).is_dir():
            self.errorOccurred.emit("Enter a command and an existing working directory.")
            return False
        program = args[0]
        if "/" in program or "\\" in program:
            program = str((Path(directory) / program).resolve())
        executable = shutil.which(program)
        if executable is None:
            self.errorOccurred.emit(f"Executable not found: {args[0]}")
            return False
        self._cwd = str(Path(directory).resolve())
        self._decoder.reset()
        self._stopping = False
        self._busy = True
        self._append(f"\n> {command}\n")
        self._process.setWorkingDirectory(self._cwd)
        self._process.start(executable, args[1:])
        return True

    @Slot(str, result=bool)
    def sendInput(self, text: str) -> bool:
        if not self.busy:
            self.errorOccurred.emit("No command is running.")
            return False
        data = (text + "\n").encode(locale.getpreferredencoding(False), errors="replace")
        if self._process.write(data) < 0:
            self.errorOccurred.emit("Could not write to the command's standard input.")
            return False
        return True

    @Slot()
    def closeInput(self) -> None:
        self._process.closeWriteChannel()

    @Slot()
    def clearOutput(self) -> None:
        self._output = ""
        self.changed.emit()

    @Slot()
    def stop(self) -> None:
        if self.busy:
            self._stopping = True
            self._process.terminate()
            self._kill_timer.start(1500)

    @Slot()
    def shutdown(self) -> None:
        self._kill_timer.stop()
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self._stopping = True
            self._process.kill()
            self._process.waitForFinished(2000)

    def _read(self) -> None:
        self._append(self._decoder.decode(bytes(self._process.readAllStandardOutput())))

    def _finished(self, code: int, status: QProcess.ExitStatus) -> None:
        self._kill_timer.stop()
        self._read()
        self._append(self._decoder.decode(b"", final=True))
        self._busy = False
        state = "Stopped" if self._stopping else "Crashed" if status == QProcess.ExitStatus.CrashExit else "Exited"
        self._append(f"\n[{state}: {code}]\n")

    def _error(self, error: QProcess.ProcessError) -> None:
        if self._stopping and error == QProcess.ProcessError.Crashed:
            return
        self.errorOccurred.emit("Command error: " + self._process.errorString())
        if error == QProcess.ProcessError.FailedToStart:
            self._busy = False
            self.changed.emit()


def parse_git_status(raw: bytes) -> tuple[str, list[dict]]:
    """Parse porcelain v1 -z without splitting filenames on whitespace."""
    records = raw.decode("utf-8", errors="strict").split("\0")
    branch = ""
    entries = []
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        if record.startswith("## "):
            branch = record[3:]
            continue
        if len(record) < 4 or record[2] != " ":
            raise ValueError("Unexpected Git status record.")
        status, path = record[:2], record[3:]
        old_path = ""
        if "R" in status or "C" in status:
            if index >= len(records) or not records[index]:
                raise ValueError("Incomplete Git rename record.")
            old_path = records[index]
            index += 1
        entries.append({"status": status, "path": path, "oldPath": old_path,
                        "staged": status[0] not in (" ", "?"),
                        "unstaged": status[1] != " "})
    return branch, entries


@QmlElement
class GitTools(QObject):
    changed = Signal()
    errorOccurred = Signal(str)
    diffReady = Signal(str, str)
    operationCompleted = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._root = ""
        self._branch = ""
        self._entries: list[dict] = []
        self._busy = False
        self._job = ""
        self._path = ""
        self._stdout = bytearray()
        self._stderr = bytearray()
        self._failure = ""
        self._process = QProcess(self)
        self._process.readyReadStandardOutput.connect(self._read)
        self._process.readyReadStandardError.connect(self._read)
        self._process.finished.connect(self._finished)
        self._process.errorOccurred.connect(self._error)
        self._timeout = QTimer(self)
        self._timeout.setSingleShot(True)
        self._timeout.timeout.connect(lambda: self._abort("Git operation timed out after 30 seconds."))
        application = QCoreApplication.instance()
        if application is not None:
            application.aboutToQuit.connect(self.shutdown)

    @Property(bool, notify=changed)
    def busy(self) -> bool:
        return self._busy

    @Property(str, notify=changed)
    def root(self) -> str:
        return self._root

    @Property(str, notify=changed)
    def branch(self) -> str:
        return self._branch

    @Property("QVariantList", notify=changed)
    def entries(self) -> list[dict]:
        return self._entries

    def _start(self, job: str, args: list[str], directory: str) -> bool:
        if self.busy:
            self.errorOccurred.emit("Wait for the current Git operation to finish.")
            return False
        executable = shutil.which("git")
        if executable is None:
            self.errorOccurred.emit("Git is not installed or is not on PATH.")
            return False
        if not Path(directory).is_dir():
            self.errorOccurred.emit("Select an existing repository directory.")
            return False
        self._job = job
        self._failure = ""
        self._stdout.clear()
        self._stderr.clear()
        environment = QProcessEnvironment.systemEnvironment()
        for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"):
            environment.remove(name)
        environment.insert("GIT_TERMINAL_PROMPT", "0")
        environment.insert("GIT_PAGER", "cat")
        environment.insert("GIT_LITERAL_PATHSPECS", "1")
        self._process.setProcessEnvironment(environment)
        self._process.setWorkingDirectory(directory)
        self._busy = True
        self.changed.emit()
        self._process.start(executable, ["--no-pager", "-c", "core.quotepath=false", *args])
        self._timeout.start(30000)
        return True

    @Slot(str, result=bool)
    def refresh(self, directory: str) -> bool:
        if self.busy:
            self.errorOccurred.emit("Wait for the current Git operation to finish.")
            return False
        self._root = ""
        self._branch = ""
        self._entries = []
        self.changed.emit()
        return self._start("root", ["rev-parse", "--show-toplevel"], directory)

    def _entry(self, path: str) -> dict | None:
        if self.busy:
            self.errorOccurred.emit("Wait for the current Git operation to finish.")
            return None
        entry = next((entry for entry in self._entries if entry["path"] == path), None)
        if entry is None or not self.root:
            self.errorOccurred.emit("Refresh Git status and select a changed file.")
        return entry

    @Slot(str, bool, result=bool)
    def stage(self, path: str, unstage: bool) -> bool:
        entry = self._entry(path)
        if entry is None:
            return False
        paths = [path] + ([entry["oldPath"]] if entry["oldPath"] else [])
        if not unstage and entry["status"][0] in ("R", "C"):
            paths = [path]
        # git restore --staged cannot unstage an initial commit; reset works there too.
        return self._start("unstage" if unstage else "stage",
                           ["reset", "-q", "--", *paths] if unstage else ["add", "--", *paths], self.root)

    @Slot(str, bool, result=bool)
    def diff(self, path: str, staged: bool) -> bool:
        entry = self._entry(path)
        if entry is None:
            return False
        if entry["status"] == "??":
            self.errorOccurred.emit("Stage this untracked file to inspect its staged diff.")
            return False
        self._path = path
        paths = [path] + ([entry["oldPath"]] if entry["oldPath"] else [])
        args = ["diff", "--no-ext-diff", "--no-textconv"]
        if staged:
            args.append("--cached")
        return self._start("diff", [*args, "--", *paths], self.root)

    @Slot(str, result=bool)
    def commit(self, message: str) -> bool:
        if not message.strip():
            self.errorOccurred.emit("Enter a commit message.")
            return False
        if not self.root or not any(entry["staged"] for entry in self._entries):
            self.errorOccurred.emit("Stage changes before committing.")
            return False
        return self._start("commit", ["commit", "-m", message], self.root)

    def _read(self) -> None:
        self._stdout.extend(bytes(self._process.readAllStandardOutput()))
        self._stderr.extend(bytes(self._process.readAllStandardError()))
        if len(self._stdout) + len(self._stderr) > MAX_GIT_BYTES:
            self._abort("Git output exceeds the 4 MB limit.")

    def _abort(self, message: str) -> None:
        if not self._failure:
            self._failure = message
            self._process.kill()

    def _error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self._timeout.stop()
            self._busy = False
            self.changed.emit()
            self.errorOccurred.emit("Could not start Git: " + self._process.errorString())

    def _finished(self, code: int, status: QProcess.ExitStatus) -> None:
        self._timeout.stop()
        self._read()
        self._busy = False
        self.changed.emit()
        if self._failure or code != 0 or status == QProcess.ExitStatus.CrashExit:
            detail = self._failure or self._stderr.decode("utf-8", errors="replace").strip() or f"Git exited with code {code}."
            self.errorOccurred.emit(detail)
            return
        try:
            if self._job == "root":
                self._root = self._stdout.decode("utf-8").rstrip("\r\n")
                self.changed.emit()
                self._start("status", ["status", "--porcelain=v1", "-z", "--branch"], self.root)
            elif self._job == "status":
                self._branch, self._entries = parse_git_status(bytes(self._stdout))
                self.changed.emit()
                self.operationCompleted.emit("Status refreshed")
            elif self._job == "diff":
                self.diffReady.emit(self._stdout.decode("utf-8", errors="replace"), self._path)
            else:
                self.operationCompleted.emit(self._job.capitalize() + " completed")
                self._start("status", ["status", "--porcelain=v1", "-z", "--branch"], self.root)
        except (ValueError, UnicodeError) as exc:
            self.errorOccurred.emit(f"Could not interpret Git output: {exc}")

    @Slot()
    def shutdown(self) -> None:
        self._timeout.stop()
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()
            self._process.waitForFinished(2000)
