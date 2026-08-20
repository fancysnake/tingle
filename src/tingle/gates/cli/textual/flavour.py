"""The nonsense shown while the metrics run.

Copy, not logic: one flat tuple, read in order from wherever the run
happened to start. There are deliberately no per-phase buckets -- a line
chosen to suit the phase would be a second, worse version of the honest
one already on screen beneath it, and the whole point of the pair is that
only one of them is pretending.
"""

from __future__ import annotations

import secrets
from itertools import cycle
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

#: Read in order from a starting point that moves, so that the line most
#: often seen -- the first one -- is not always the same line.
LINES = (
    "Reticulating code splines…",
    "Counting the noqa…",
    "Negotiating with the linter…",
    "Untangling circular imports…",
    "Interviewing legacy classes…",
    "Alphabetising the spaghetti…",
    "Rehydrating technical debt…",
    "Asking mypy to reconsider…",
    "Adjusting emotional weight of TODOs…",
    "Calibrating the code smell detector…",
    "Warming up spider-sense…",
    "Weighing the god object…",
    "Shaving the yak…",
    "Extracting method from method…",
    "Measuring the blast radius…",
    "Deprecating the deprecation warnings…",
    "Consulting the strangler fig…",
    "Recalculating the bus factor…",
    "Sorting imports by regret…",
    "Reading the comments, believing none of them…",
    "Grepping for the word “temporary”…",
    "Dating the TODO that says before launch…",
    "Refactoring the refactor…",
    "Loading the loading bar…",
    "Auditing the audit log…",
    "Counting cyclomatic sheep…",
    "Aligning the tabs with the spaces…",
    "Estimating in ideal engineer-hours…",
    "Rebasing feelings onto main…",
    "Composing over inheriting…",
    "Defrosting the frozen dataclasses…",
    "Renaming data to something meaningful…",
    "Draining the swamp of helpers…",
    "Feeding the mocks…",
    "Polishing the happy path…",
    "Enumerating the utils…",
    "Applying pressure to the abstraction layer…",
    "Reconciling docstring with function…",
    "Waking the sleeping tests…",
    "Bribing continuous integration…",
    "Sharpening the razor…",
    "Simmering the boilerplate…",
    "Cross-referencing the tribal knowledge…",
    "Averaging the review nitpicks…",
    "Counting the ways this could break…",
    "Buffing the surface area…",
    "Untangling the one-liner…",
    "Justifying the exception…",
    "Explaining the clever bit…",
    "Rounding the technical debt up…",
)


def rotation() -> Iterator[str]:
    """Endless lines, entered at a point that differs between runs.

    `secrets` rather than `random` because the pool needs no reproducible
    order and this is the stdlib source that is not a pseudo-random one;
    nothing here is a security claim.
    """
    start = secrets.randbelow(len(LINES))
    return cycle(LINES[start:] + LINES[:start])
