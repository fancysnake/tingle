"""What the app shows while the run it started is still running.

The other TUI suites hand the app a run that is already over, so they
never see this. Here the run is held open on purpose: a collect that
waits on an event is the only way to look at a screen whose whole job is
to be temporary.
"""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING

import pytest
from textual.widgets import Label, ProgressBar
from textual_support import RUN_REPORT, collecting, labels, metrics_app

from tingle.gates.cli.textual.browse import MetricsApp
from tingle.gates.cli.textual.loading import LoadingScreen, plainly
from tingle.inits.services import Services
from tingle.links.editor import VsCodeCli
from tingle.pacts.config import SelectionError
from tingle.pacts.diff import DiffSourceError
from tingle.pacts.metrics import RunPhase, RunProgress

if TYPE_CHECKING:
    from collections.abc import Callable

    from textual.pilot import Pilot

    from tingle.pacts.metrics import ProgressSink
    from tingle.pacts.report import RunReport

#: Longer than the app waits before drawing the screen, so that a test
#: looking at the screen is looking at one that had its chance to appear.
PAST_THE_WAIT = 0.4

#: How long a test will wait for a run to land before giving up on it.
SETTLE_TIMEOUT = 5.0

#: How often it looks while waiting.
SETTLE_STEP = 0.02


async def settled(app: MetricsApp, pilot: Pilot[None]) -> None:
    """Wait until the run inside the app has landed, one way or the other.

    Waiting on the worker itself is no good here: an app that exits on a
    failure cancels its own worker, and a cancelled worker is what the
    test was about rather than an error in it.
    """
    for _ in range(int(SETTLE_TIMEOUT / SETTLE_STEP)):
        if app.measured.over:
            return
        await pilot.pause(SETTLE_STEP)


def held_app(
    hold: threading.Event, *, during: Callable[[ProgressSink], None] | None = None
) -> MetricsApp:
    """Build an app whose run does not finish until `hold` is set.

    `during` is the run's chance to report progress before it blocks,
    which is what a slow run does and what the screen is there for.
    """

    def collect(progress: ProgressSink) -> RunReport:
        if during is not None:
            during(progress)
        hold.wait(timeout=5)
        return RUN_REPORT

    return MetricsApp(
        RUN_REPORT.root, collect=collect, opener=VsCodeCli(), browse=Services().browse
    )


def failing_app(error: Exception) -> MetricsApp:
    """Build an app whose run raises instead of measuring anything."""

    def collect(_: ProgressSink) -> RunReport:
        raise error

    return MetricsApp(
        RUN_REPORT.root, collect=collect, opener=VsCodeCli(), browse=Services().browse
    )


def test_a_run_that_outlasts_the_wait_puts_the_screen_up() -> None:
    hold = threading.Event()
    app = held_app(hold)
    showing = False

    async def scenario() -> None:
        nonlocal showing
        async with app.run_test() as pilot:
            await pilot.pause(PAST_THE_WAIT)
            showing = isinstance(app.screen, LoadingScreen)
            hold.set()
            await settled(app, pilot)
            await pilot.pause()

    asyncio.run(scenario())

    assert showing


def test_a_run_that_beats_the_wait_never_draws_a_screen() -> None:
    """A screen that flashes up and vanishes is worse than a beat of stillness."""
    app = metrics_app(RUN_REPORT)
    drawn: list[str] = []
    showing = True

    async def scenario() -> None:
        nonlocal showing
        async with app.run_test() as pilot:
            await settled(app, pilot)
            await pilot.pause(PAST_THE_WAIT)
            showing = isinstance(app.screen, LoadingScreen)
            drawn.extend(labels(app))

    asyncio.run(scenario())

    assert not showing
    assert drawn == ["noqa-comments", "python-files"]


def test_progress_reaches_the_bar_and_the_sentence_under_it() -> None:
    hold = threading.Event()
    seen: list[object] = []

    def report(progress: ProgressSink) -> None:
        progress(RunProgress(RunPhase.MEASURING, done=6, total=15, label="any-uses"))

    app = held_app(hold, during=report)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await pilot.pause(PAST_THE_WAIT)
            screen = app.screen
            assert isinstance(screen, LoadingScreen)
            shown = screen.query_one(ProgressBar)
            seen.extend(
                [
                    shown.progress,
                    shown.total,
                    str(screen.query_one("#doing", Label).content),
                ]
            )
            hold.set()
            await settled(app, pilot)
            await pilot.pause()

    asyncio.run(scenario())

    assert seen == [6, 15, "measuring — any-uses (7/15)"]


def test_the_screen_goes_away_and_leaves_the_table_filled() -> None:
    hold = threading.Event()
    app = held_app(hold)
    drawn: list[str] = []
    showing = True

    async def scenario() -> None:
        nonlocal showing
        async with app.run_test() as pilot:
            await pilot.pause(PAST_THE_WAIT)
            assert isinstance(app.screen, LoadingScreen)
            hold.set()
            await settled(app, pilot)
            await pilot.pause()
            showing = isinstance(app.screen, LoadingScreen)
            drawn.extend(labels(app))

    asyncio.run(scenario())

    assert not showing
    assert drawn == ["noqa-comments", "python-files"]
    assert app.measured.report is RUN_REPORT


@pytest.mark.parametrize(
    "error",
    (SelectionError(["no metric named 'nope'"]), DiffSourceError("no such base")),
)
def test_a_failed_run_leaves_the_error_for_the_gate(error: Exception) -> None:
    """The TUI carries a failure out; the command line decides what it means."""
    app = failing_app(error)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await settled(app, pilot)
            await pilot.pause()

    asyncio.run(scenario())

    assert app.measured.failure is error
    assert app.measured.report is None


def test_the_flavour_line_turns_over_when_the_phase_does() -> None:
    """A phase change is real news, so the joke moves with the sentence."""
    hold = threading.Event()
    lines: list[str] = []

    def report(progress: ProgressSink) -> None:
        progress(RunProgress(RunPhase.SCANNING, done=500))

    app = held_app(hold, during=report)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await pilot.pause(PAST_THE_WAIT)
            screen = app.screen
            assert isinstance(screen, LoadingScreen)
            lines.append(str(screen.query_one("#flavour", Label).content))
            screen.advance(RunProgress(RunPhase.MEASURING, done=0, total=3, label="a"))
            await pilot.pause()
            lines.append(str(screen.query_one("#flavour", Label).content))
            hold.set()
            await settled(app, pilot)
            await pilot.pause()

    asyncio.run(scenario())

    assert lines[0] != lines[1]


def test_a_quit_during_the_run_leaves_no_report_and_no_failure() -> None:
    """Nothing measured and nothing wrong: the gate has nothing to print."""
    hold = threading.Event()
    app = held_app(hold)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await pilot.pause(PAST_THE_WAIT)
            app.exit()
        hold.set()

    asyncio.run(scenario())

    assert app.measured.report is None
    assert app.measured.failure is None


def test_the_table_is_answerable_before_the_report_lands() -> None:
    """Every gesture acts on an empty outline rather than on nothing at all."""
    hold = threading.Event()
    app = held_app(hold)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await pilot.pause(PAST_THE_WAIT)
            await pilot.press("v", "f", "0")
            await pilot.pause()
            app.exit()
        hold.set()

    asyncio.run(scenario())

    assert app.measured.failure is None


def test_scanning_is_counted_rather_than_proportional() -> None:
    """There is no denominator to be a proportion of until the walk ends."""
    assert plainly(RunProgress(RunPhase.SCANNING, done=1200)) == "scanning — 1200 files"


def test_diffing_names_the_base_it_is_measuring_against() -> None:
    assert plainly(RunProgress(RunPhase.DIFFING, label="main")) == (
        "diffing — against main"
    )


def test_collecting_hands_the_report_straight_back() -> None:
    """The helper the other suites lean on is a run that is already over."""
    collect = collecting(RUN_REPORT)

    assert collect(lambda _: None) is RUN_REPORT
