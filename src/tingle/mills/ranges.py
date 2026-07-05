"""Pure range resolution: glob filtering of walked paths."""

from collections.abc import Iterable
from pathlib import PurePath

from tingle.pacts.config import RangeSpec
from tingle.specs.ranges import DEFAULT_EXCLUDES


def resolve(
    files: Iterable[PurePath], specs: Iterable[RangeSpec]
) -> tuple[PurePath, ...]:
    """Return the union of files matched by any spec, deduped and sorted."""
    spec_list = list(specs)
    return tuple(
        sorted(
            path
            for path in files
            if any(_matches(path, spec) for spec in spec_list)
        )
    )


def _matches(path: PurePath, spec: RangeSpec) -> bool:
    if not any(path.full_match(pattern) for pattern in spec.include):
        return False
    return not any(
        path.full_match(pattern) for pattern in (*spec.exclude, *DEFAULT_EXCLUDES)
    )
