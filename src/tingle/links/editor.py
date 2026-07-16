"""Opening files in a running VS Code window from its integrated terminal.

The integrated terminal puts `code` on PATH and points it at the open window
through `VSCODE_IPC_HOOK_CLI`, so `code --goto file:line` jumps the editor
straight there. Outside that terminal there is no window to talk to, and the
opener reports itself unavailable rather than launching a stray instance.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence


class VsCodeCli:
    """The `code --goto` adapter, its environment probes injectable for tests."""

    def __init__(
        self,
        *,
        environ: Mapping[str, str] | None = None,
        which: Callable[[str], str | None] | None = None,
        spawn: Callable[[Sequence[str]], None] | None = None,
    ) -> None:
        """Take the environment, PATH lookup, and spawner, defaulting to real ones."""
        self._environ = os.environ if environ is None else environ
        self._which = shutil.which if which is None else which
        self._spawn = self._popen if spawn is None else spawn

    @property
    def available(self) -> bool:
        """True only inside a VS Code terminal with the `code` shim on PATH."""
        return (
            self._environ.get("TERM_PROGRAM") == "vscode"
            and self._which("code") is not None
        )

    def open(self, path: str, line: int | None) -> None:
        """Hand VS Code a `file:line` target (or a bare file) to jump to."""
        if (code := self._which("code")) is None:
            return
        target = f"{path}:{line}" if line is not None else path
        self._spawn([code, "--goto", target])

    @staticmethod
    def _popen(args: Sequence[str]) -> None:
        """Fire `code` and return at once; it is a thin client that exits fast."""
        subprocess.run(  # the argv is a resolved path plus fixed flags, no shell
            list(args),
            check=False,
            timeout=5,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
