"""The run the app starts once it is on screen, and how it reports back.

Collecting a report before the app started would be a wait with nothing
drawn to explain it, so the run happens on a worker thread underneath a
live app. That costs a way in (`Collect`), a way back (three messages and
`Measured`), and a way out (`AbandonedError`); all of it lives here, leaving
the view module to turn `Row`s into cells.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias

from textual.message import Message
from textual.worker import get_current_worker

if TYPE_CHECKING:
    from collections.abc import Callable

    from tingle.pacts.diff import DiffReport
    from tingle.pacts.metrics import ProgressSink, RunProgress
    from tingle.pacts.report import RunReport

#: Starts the run and hands back what it came to, reporting its progress
#: to the sink it is given. The gate binds the selection and the base
#: before handing it over, so the app starts a run without knowing what
#: kind of run it is.
Collect: TypeAlias = "Callable[[ProgressSink], RunReport | DiffReport]"

#: How long the run gets to finish before anything is drawn to say it is
#: happening. A screen that flashes up and vanishes is worse than a beat
#: of stillness, and on a small project the whole run fits in here.
REVEAL_AFTER = 0.25


class AbandonedError(Exception):
    """Raised inside the worker to unwind a run nobody is waiting for.

    Textual asks a worker to stop when the app exits, but a thread cannot
    be made to; it has to notice and return. Nothing joins the walk in
    the meantime, so the interpreter waits on it after the app is gone --
    the terminal comes back and the shell does not.

    Noticing happens in the progress sink because that is already the one
    point the run passes through regularly: every so many files while the
    tree is read, and once before each metric.
    """


@dataclass
class Measured:
    """What the run inside the app has come to so far.

    One object rather than three attributes because they are one fact
    read at three moments: what the run last said, what it finally came
    to, and why it could not. The gate reads the last two after the app
    has closed, which is the only way a report leaves a terminal.
    """

    latest: RunProgress | None = None
    report: RunReport | DiffReport | None = None
    failure: Exception | None = None

    @property
    def over(self) -> bool:
        """Whether the run has stopped, whichever way it stopped."""
        return self.report is not None or self.failure is not None


def abandon_if_cancelled() -> None:
    """Raise `AbandonedError` once the app has asked this worker to stop."""
    if get_current_worker().is_cancelled:
        raise AbandonedError


class RunProgressed(Message):
    """How far the run inside the app has got."""

    def __init__(self, progress: RunProgress) -> None:
        """Carry one progress report across from the worker thread."""
        super().__init__()
        self.progress = progress


class RunFinished(Message):
    """The run is done, and this is what it came to."""

    def __init__(self, report: RunReport | DiffReport) -> None:
        """Carry the finished report across from the worker thread."""
        super().__init__()
        self.report = report


class RunFailed(Message):
    """The run could not be done, for a reason the command line knows."""

    def __init__(self, error: Exception) -> None:
        """Carry the failure across from the worker thread."""
        super().__init__()
        self.error = error
