"""Git CLI adapter implementing the DiffSource protocol.

All git invocations run with cwd at the tingle project root, hardened
against user diff configuration (external diff drivers, prefix and
quoting settings). Filenames containing newlines are unsupported.
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path, PurePath
from typing import TYPE_CHECKING

from tingle.pacts.diff import BranchDiff, DiffSourceError, FileDiff, FileStatus

if TYPE_CHECKING:
    from collections.abc import Iterable

_BINARY_SNIFF_BYTES = 8192

_DIFF_ARGS = (
    "-c",
    "core.quotepath=false",
    "diff",
    "--no-color",
    "--no-ext-diff",
    "--no-renames",
    "--ignore-submodules=all",
    "--src-prefix=a/",
    "--dst-prefix=b/",
    "--relative",
    "-U0",
)

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class GitCli:
    """DiffSource over the `git` executable.

    Stateful: read_base() serves blobs at the merge-base resolved by the
    last branch_diff() call.
    """

    def __init__(self, root: Path) -> None:
        """Anchor at the tingle project root (may be a repo subdirectory)."""
        self._root = root
        self._merge_base: str | None = None
        self._prefix = ""

    def branch_diff(self, base: str) -> BranchDiff:
        """Diff the working tree against merge-base(base, HEAD)."""
        base_ref = self._resolve_ref(base)
        merge_base = self._merge_base_of(base_ref)
        self._merge_base = merge_base
        self._prefix = self._run("rev-parse", "--show-prefix").strip()

        diff_files = _parse_diff(self._run(*_DIFF_ARGS, merge_base))
        untracked = self._untracked_files(seen={diff.path for diff in diff_files})
        return BranchDiff(
            base_ref=base_ref,
            merge_base=merge_base,
            files=(*diff_files, *untracked),
        )

    def read_base(self, path: PurePath) -> str | None:
        """Return the file's text at the merge-base, mirroring worktree read()."""
        if self._merge_base is None:
            msg = "read_base() called before branch_diff()"
            raise DiffSourceError(msg)
        blob_ref = f"{self._merge_base}:{self._prefix}{path.as_posix()}"
        result = self._git("show", blob_ref)
        if result.returncode != 0:
            return None
        return _decode_blob(result.stdout)

    def _resolve_ref(self, base: str) -> str:
        for candidate in (base, f"origin/{base}"):
            result = self._git(
                "rev-parse", "--verify", "--quiet", f"{candidate}^{{commit}}"
            )
            if result.returncode == 0:
                return candidate
        msg = (
            f'base ref "{base}" not found (also tried "origin/{base}");'
            " pick one with --base"
        )
        raise DiffSourceError(msg)

    def _merge_base_of(self, base_ref: str) -> str:
        result = self._git("merge-base", base_ref, "HEAD")
        if result.returncode == 0:
            return _decode(result.stdout).strip()
        if result.returncode == 1:
            msg = (
                f'no common ancestor between "{base_ref}" and HEAD'
                " (unrelated histories, or a shallow clone without enough history)"
            )
            raise DiffSourceError(msg)
        msg = f"git merge-base failed: {_stderr(result)}"
        raise DiffSourceError(msg)

    def _untracked_files(self, seen: set[PurePath]) -> list[FileDiff]:
        output = self._run("ls-files", "--others", "--exclude-standard", "-z")
        untracked: list[FileDiff] = []
        for name in output.split("\0"):
            path = PurePath(name)
            if not name or path in seen:
                continue
            untracked.append(
                FileDiff(
                    path=path,
                    status=FileStatus.ADDED,
                    added_lines=frozenset(self._worktree_line_numbers(path)),
                )
            )
        return untracked

    def _worktree_line_numbers(self, path: PurePath) -> Iterable[int]:
        try:
            data = (self._root / path).read_bytes()
        except OSError:
            return ()
        text = _decode_blob(data)
        if text is None:
            return ()
        return range(1, len(text.splitlines()) + 1)

    def _run(self, *args: str) -> str:
        result = self._git(*args)
        if result.returncode != 0:
            msg = f"git {args[0]} failed: {_stderr(result)}"
            raise DiffSourceError(msg)
        return _decode(result.stdout)

    def _git(self, *args: str) -> subprocess.CompletedProcess[bytes]:
        try:
            return subprocess.run(
                ("git", *args),
                cwd=self._root,
                capture_output=True,
                env={**os.environ, "LC_ALL": "C"},
                check=False,
            )
        except FileNotFoundError as exc:
            msg = "git executable not found"
            raise DiffSourceError(msg) from exc


@dataclass
class _Record:
    path: PurePath
    status: FileStatus = FileStatus.MODIFIED
    added: set[int] = field(default_factory=set)
    removed: set[int] = field(default_factory=set)

    def feed(self, line: str) -> None:
        """Update the record from one diff body line."""
        if line.startswith("new file mode"):
            self.status = FileStatus.ADDED
        elif line.startswith("deleted file mode"):
            self.status = FileStatus.DELETED
        elif line.startswith("--- ") and line != "--- /dev/null":
            self.path = PurePath(line.removeprefix("--- a/").rstrip("\t"))
        elif line.startswith("+++ ") and line != "+++ /dev/null":
            self.path = PurePath(line.removeprefix("+++ b/").rstrip("\t"))
        elif match := _HUNK_RE.match(line):
            base_start, base_count = int(match[1]), _count(match[2])
            new_start, new_count = int(match[3]), _count(match[4])
            self.removed.update(range(base_start, base_start + base_count))
            self.added.update(range(new_start, new_start + new_count))

    def to_file_diff(self) -> FileDiff:
        return FileDiff(
            path=self.path,
            status=self.status,
            added_lines=frozenset(self.added),
            removed_lines=frozenset(self.removed),
        )


def _parse_diff(output: str) -> tuple[FileDiff, ...]:
    files: list[FileDiff] = []
    record: _Record | None = None
    for line in output.splitlines():
        if line.startswith("diff --git "):
            if record is not None:
                files.append(record.to_file_diff())
            record = _Record(path=_header_path(line))
        elif record is not None:
            record.feed(line)
    if record is not None:
        files.append(record.to_file_diff())
    return tuple(files)


def _count(group: str | None) -> int:
    return 1 if group is None else int(group)


def _header_path(line: str) -> PurePath:
    """Best-effort path from `diff --git a/X b/X` (fallback for binary/mode-only).

    With renames disabled both sides are identical, so the midpoint of the
    remainder is the split; text diffs override this from the ---/+++ lines.
    """
    rest = line.removeprefix("diff --git a/")
    half = (len(rest) - len(" b/")) // 2
    return PurePath(rest[:half])


def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        msg = f"git produced non-UTF-8 output: {exc}"
        raise DiffSourceError(msg) from exc


def _decode_blob(data: bytes) -> str | None:
    if b"\0" in data[:_BINARY_SNIFF_BYTES]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _stderr(result: subprocess.CompletedProcess[bytes]) -> str:
    return result.stderr.decode("utf-8", errors="replace").strip()
