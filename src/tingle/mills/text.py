"""Turning the raw bytes an adapter hands over into text metrics can read.

Adapters read; they do not judge. The worktree and git blobs both pass
bytes across the boundary, so what counts as unreadable is decided once,
here -- otherwise the same file could be measured on one side of a diff
and skipped on the other.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tingle.specs.text import BINARY_SNIFF_BYTES

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import PurePath


def decode_text(data: bytes | None) -> str | None:
    """Decode file bytes as UTF-8; None if absent, binary, or undecodable.

    `None` in means `None` out, so a reader that could not find the file at
    all needs no separate branch at the call site.

    Binary is guessed the way git does: a NUL byte near the start.
    """
    if data is None:
        return None
    if b"\0" in data[:BINARY_SNIFF_BYTES]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def text_reader(
    read: Callable[[PurePath], bytes | None],
) -> Callable[[PurePath], str | None]:
    """Adapt a byte-returning reader into the text reader a metric is given."""

    def read_text(path: PurePath) -> str | None:
        return decode_text(read(path))

    return read_text
