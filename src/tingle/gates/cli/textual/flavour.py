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
    "Aligning the tabs with the spaces…",
    "Asking what this class is responsible for…",
    "Asking whether this observer is observing anything…",
    "Asking which direction the dependencies point…",
    "Auditing the hexagon for extra sides…",
    "Calibrating spider-sense…",
    "Calling Uncle Bob…",
    "Checking where the classes go to hide…",
    "Checking whether the builder builds…",
    "Confirming that everything is a trade-off…",
    "Confirming that walking on water needs frozen specs…",
    "Confirming the square is still not a rectangle…",
    "Counting cyclomatic sheep…",
    "Counting how many people understand this file…",
    "Counting the abstractions nobody abstracted over…",
    "Counting the decorators on one function…",
    "Counting the magic numbers…",
    "Counting the reasons this class might change…",
    "Counting the singletons…",
    "Counting the things that import everything…",
    "Counting the ways this could break…",
    "Cutting the onion, trying not to cry…",
    "Deciding whether this is a visitor or a mistake…",
    "Deciding whether to ask forgiveness or permission…",
    "Estimating in ideal engineer-hours…",
    "Finding out it was us, three years ago…",
    'Grepping for the word "temporary"…',
    "Loading the loading bar…",
    "Looking for the boy scout who left this campsite…",
    "Looking for the L in your SOLID…",
    "Looking for the one obvious way to do it…",
    "Looking for the one thing this function does…",
    "Looking for the pattern this was named after…",
    "Looking for the service that is a repository in a hat…",
    "Measuring how easy the easy change would be…",
    "Measuring the blast radius…",
    "Measuring the drift between the doc and the code…",
    "Measuring the interest on the technical debt…",
    "Measuring the thickness of the thin layer…",
    "Meditating to understand the Zen of Python…",
    'Reading a docstring that says "does stuff"…',
    "Reading the code as the only honest documentation…",
    "Recalculating the bus factor…",
    "Reticulating code splines…",
    "Warming up the code smell detector…",
    "Weighing the god object…",
)


def rotation() -> Iterator[str]:
    """Endless lines, entered at a point that differs between runs.

    `secrets` rather than `random` because the pool needs no reproducible
    order and this is the stdlib source that is not a pseudo-random one;
    nothing here is a security claim.
    """
    start = secrets.randbelow(len(LINES))
    return cycle(LINES[start:] + LINES[:start])
