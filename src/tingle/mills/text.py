"""Turning the raw bytes an adapter hands over into text metrics can read.

Adapters read; they do not judge. The worktree and git blobs both pass
bytes across the boundary, so what counts as unreadable is decided once,
here -- otherwise the same file could be measured on one side of a diff
and skipped on the other.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import PurePath
from typing import TypeAlias

from tingle.pacts.metrics import sniffed_binary

#: What a metric is handed in place of a port's raw bytes: the same lookup,
#: with the readability rule already applied to what comes back.
TextReader: TypeAlias = Callable[[PurePath], "str | None"]


def decode_text(data: bytes | None) -> str | None:
    """Decode file bytes as UTF-8; None if absent, binary, or undecodable.

    `None` in means `None` out, so a reader that could not find the file at
    all needs no separate branch at the call site.

    Binary is guessed the way git does, and then the decode gate on top of
    it is tingle's own: git diffs a latin-1 file, a metric cannot read one.
    That extra gate is the whole difference between this question and the
    adapter's, which is why only the sniff underneath it is shared.
    """
    if data is None:
        return None
    if sniffed_binary(data):
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def text_reader(read: Callable[[PurePath], bytes | None]) -> TextReader:
    """Adapt a port's byte reader into the text reader a metric is given.

    Called at the seam, where the port is picked up, and never at a call
    site: one reader per source is what makes the rule applied once rather
    than remembered five times.
    """

    def read_text(path: PurePath) -> str | None:
        return decode_text(read(path))

    return read_text
