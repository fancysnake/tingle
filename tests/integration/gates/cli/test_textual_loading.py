"""What the app shows while the run it started is still running.

The other TUI suites hand the app a run that is already over, so they
never see this. Here the run is held open on purpose: a collect that
waits on an event is the only way to look at a screen whose whole job is
to be temporary.
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import TYPE_CHECKING

import pytest
from textual.widgets import Label, ProgressBar
from textual_support import RUN_REPORT, collecting, labels, metrics_app

from tingle.gates.cli.textual.browse import MetricsApp
from tingle.gates.cli.textual.loading import LoadingScreen, plainly
from tingle.gates.cli.textual.run import AbandonedError
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
#: about the screen *not* appearing has given it every chance to.
PAST_THE_WAIT = 0.4

#: How long a test will wait for a run to land before giving up on it.
SETTLE_TIMEOUT = 5.0

#: How often it looks while waiting.
SETTLE_STEP = 0.02


async def until(check: Callable[[], bool], pilot: Pilot[None]) -> None:
    """Wait for something to become true, rather than for a length of time.

    A fixed pause is a guess about how slow the machine is, and under
    coverage it guesses wrong. Giving up quietly is deliberate: whatever
    the test was waiting for is what it goes on to assert, so a wait that
    runs out fails there, with a message about the behaviour rather than
    about the waiting.
    """
    for _ in range(int(SETTLE_TIMEOUT / SETTLE_STEP)):
        if check():
            return
        await pilot.pause(SETTLE_STEP)


def _drawn(app: MetricsApp) -> bool:
    """Whether the loading screen is up *and* has put its widgets out."""
    screen = app.screen
    return isinstance(screen, LoadingScreen) and bool(screen.query("#flavour"))


async def loading(app: MetricsApp, pilot: Pilot[None]) -> LoadingScreen:
    """Wait for the loading screen to be drawn, and hand it over."""
    await until(lambda: _drawn(app), pilot)
    screen = app.screen
    assert isinstance(screen, LoadingScreen)
    return screen


async def settled(app: MetricsApp, pilot: Pilot[None]) -> None:
    """Wait until the run inside the app has landed, one way or the other.

    Waiting on the worker itself is no good here: an app that exits on a
    failure cancels its own worker, and a cancelled worker is what the
    test was about rather than an error in it.
    """
    await until(lambda: app.measured.over, pilot)


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
            await loading(app, pilot)
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
            screen = await loading(app, pilot)
            await until(lambda: screen.query_one(ProgressBar).total is not None, pilot)
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
            await loading(app, pilot)
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
            screen = await loading(app, pilot)
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
            await loading(app, pilot)
            app.exit()
        hold.set()

    asyncio.run(scenario())

    assert app.measured.report is None
    assert app.measured.failure is None


def test_a_quit_stops_the_run_rather_than_waiting_it_out() -> None:
    """A thread cannot be stopped, so the run has to notice and return.

    Nothing joins the walk while the app shuts down, so a run that kept
    going would still be waited on once the app was gone: the terminal
    comes back and the shell does not, for as long as the walk had left.

    The run here reports the way a walk does, so what it notices, a walk
    notices in the same place.
    """
    started = threading.Event()
    stopped = threading.Event()

    def walking(progress: ProgressSink) -> None:
        # bounded, so that a run which never notices fails this test
        # rather than hanging the suite on it
        for _ in range(int(SETTLE_TIMEOUT / SETTLE_STEP)):
            started.set()
            progress(RunProgress(RunPhase.SCANNING, done=500))
            time.sleep(SETTLE_STEP)

    def collect(progress: ProgressSink) -> RunReport:
        try:
            walking(progress)
        except AbandonedError:
            stopped.set()
            raise
        return RUN_REPORT

    app = MetricsApp(
        RUN_REPORT.root, collect=collect, opener=VsCodeCli(), browse=Services().browse
    )

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await until(started.is_set, pilot)
            app.exit()

    asyncio.run(scenario())

    assert stopped.wait(timeout=SETTLE_TIMEOUT)
    assert app.measured.report is None
    assert app.measured.failure is None


def test_the_table_is_answerable_before_the_report_lands() -> None:
    """Every gesture acts on an empty outline rather than on nothing at all."""
    hold = threading.Event()
    app = held_app(hold)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await loading(app, pilot)
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


def test_progress_arriving_after_the_screen_reaches_it_too() -> None:
    """The screen catches up on the way in, and keeps up once it is there."""
    up, hold = threading.Event(), threading.Event()
    doing: list[str] = []

    def collect(progress: ProgressSink) -> RunReport:
        up.wait(timeout=5)
        progress(RunProgress(RunPhase.MEASURING, done=2, total=4, label="later"))
        hold.wait(timeout=5)
        return RUN_REPORT

    app = MetricsApp(
        RUN_REPORT.root, collect=collect, opener=VsCodeCli(), browse=Services().browse
    )

    async def scenario() -> None:
        async with app.run_test() as pilot:
            screen = await loading(app, pilot)
            up.set()
            await until(lambda: screen.query_one(ProgressBar).total is not None, pilot)
            doing.append(str(screen.query_one("#doing", Label).content))
            hold.set()
            await settled(app, pilot)

    asyncio.run(scenario())

    assert doing == ["measuring — later (3/4)"]
