"""PyInstaller entry point.

PyInstaller runs the analysis script as a bare top-level module (there is no
parent package), so ``src/cipherpad/__main__.py`` cannot be used directly there
-- its ``from .app import run`` relative import fails with "attempted
relative import with no known parent package" once frozen. This tiny shim
uses an absolute import instead (``src`` is on ``sys.path`` via the spec's
``pathex``) and is what the frozen executable actually launches.
"""

from cipherpad.app import run

if __name__ == "__main__":
    raise SystemExit(run())
