"""Turning raw bytes into text the metrics can read.

Every adapter that hands file contents to mills — the worktree, git
blobs — must agree on what counts as unreadable, or the same file would
be measured on one side of a diff and skipped on the other.
"""

from __future__ import annotations

_BINARY_SNIFF_BYTES = 8192


def decode_text(data: bytes) -> str | None:
    """Decode file bytes as UTF-8, or None if binary or undecodable.

    Binary is guessed the way git does: a NUL byte near the start.
    """
    if b"\0" in data[:_BINARY_SNIFF_BYTES]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None
