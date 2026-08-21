"""What the reader looks at while the metrics run.

Two lines, and the split between them is the whole design: the flavour
line above the bar is nonsense on a timer, and the line below it always
says the true phase and what it is working on. The joke never stands in
for the fact, so a run that is stuck on one slow metric says so even
while something above it is still moving.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.containers import Center, Middle
from textual.screen import Screen
from textual.widgets import Label, ProgressBar

from tingle.gates.cli.textual import flavour
from tingle.pacts.metrics import RunPhase

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from tingle.pacts.metrics import RunProgress

#: How long one flavour line stays up. Long enough to read, short enough
#: that a wait with nothing else moving still looks alive.
LINE_SECONDS = 2.5


class LoadingScreen(Screen[None]):
    """The bar, the joke, and the sentence that means it."""

    CSS: ClassVar = """
    LoadingScreen { align: center middle; }
    LoadingScreen Label { width: auto; }
    #flavour { color: $text-muted; margin-bottom: 1; }
    #doing { color: $text-muted; margin-top: 1; }
    """

    def __init__(self, latest: RunProgress | None = None) -> None:
        """Take the first line, and catch up on whatever already happened.

        The run starts before this screen does -- that is the whole point
        of holding it back -- so by the time it appears the run may have
        said something already. Without `latest` the screen would open on
        "starting…" and stay there until the next report, which for a run
        stuck on one slow metric could be the rest of the wait.
        """
        super().__init__()
        self._lines = flavour.rotation()
        self._latest = latest
        self._phase: RunPhase | None = None

    def compose(self) -> ComposeResult:
        """Lay the three lines out, centred on an otherwise bare screen."""
        with Middle(), Center():
            yield Label(next(self._lines), id="flavour")
            # no total yet: the walk has no known size, and an indeterminate
            # bar says that where a percentage would have to invent one
            yield ProgressBar(total=None, show_eta=False)
            yield Label("starting…", id="doing")

    def on_mount(self) -> None:
        """Start the flavour turning over, showing where the run got to."""
        self.set_interval(LINE_SECONDS, self._turn_over)
        if self._latest is not None:
            self.advance(self._latest)

    def advance(self, progress: RunProgress) -> None:
        """Show how far the run has got, in both registers.

        A change of phase turns the flavour over as well as the sentence,
        so the screen visibly moves at the moments it has real news --
        the timer alone would leave the two out of step.
        """
        self.query_one(ProgressBar).update(total=progress.total, progress=progress.done)
        self.query_one("#doing", Label).update(plainly(progress))
        if progress.phase is not self._phase:
            self._phase = progress.phase
            self._turn_over()

    def _turn_over(self) -> None:
        self.query_one("#flavour", Label).update(next(self._lines))


def plainly(progress: RunProgress) -> str:
    """Say what is happening, in the words the run itself used.

    Counted rather than proportional while scanning, because there is no
    denominator to be a proportion of.
    """
    if progress.phase is RunPhase.SCANNING:
        return f"scanning — {progress.done} files"
    if progress.phase is RunPhase.DIFFING:
        return f"diffing — against {progress.label}"
    return f"measuring — {progress.label} ({progress.done + 1}/{progress.total})"
