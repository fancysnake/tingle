"""Pure range resolution: glob filtering of walked paths.

The matcher mirrors pathlib's full-match glob semantics (`*` and `?`
stay within a path segment, `**` spans any number of segments) and is
implemented here because PurePath.full_match only exists on 3.13+.
"""

from __future__ import annotations

import re
from functools import cache
from typing import TYPE_CHECKING

from tingle.specs.ranges import DEFAULT_EXCLUDES

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import PurePath

    from tingle.pacts.config import RangeSpec


def resolve(
    files: Iterable[PurePath], specs: Iterable[RangeSpec]
) -> tuple[PurePath, ...]:
    """Return the union of files matched by any spec, deduped and sorted."""
    spec_list = list(specs)
    return tuple(
        sorted(
            path for path in files if any(_matches(path, spec) for spec in spec_list)
        )
    )


def _matches(path: PurePath, spec: RangeSpec) -> bool:
    name = path.as_posix()
    if not any(_pattern(glob).match(name) for glob in spec.include):
        return False
    return not any(
        _pattern(glob).match(name) for glob in (*spec.exclude, *DEFAULT_EXCLUDES)
    )


@cache
def _pattern(glob: str) -> re.Pattern[str]:
    """Compile one glob into an anchored regex over posix-style paths."""
    segments = glob.split("/")
    pieces: list[str] = []
    for index, segment in enumerate(segments):
        last = index == len(segments) - 1
        if segment == "**":
            pieces.append(".*" if last else "(?:[^/]+/)*")
        else:
            pieces.append(_segment_regex(segment) + ("" if last else "/"))
    return re.compile("".join(pieces) + r"\Z")


def _segment_regex(segment: str) -> str:
    out: list[str] = []
    index = 0
    while index < len(segment):
        char = segment[index]
        if char == "*":
            out.append("[^/]*")
        elif char == "?":
            out.append("[^/]")
        elif char == "[":
            closing = segment.find("]", index + 1)
            if closing == -1:
                out.append(re.escape(char))
            else:
                inner = segment[index + 1 : closing]
                if inner.startswith("!"):
                    inner = "^" + inner[1:]
                out.append(f"[{inner}]")
                index = closing
        else:
            out.append(re.escape(char))
        index += 1
    return "".join(out)
