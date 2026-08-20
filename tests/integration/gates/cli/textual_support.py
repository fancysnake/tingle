"""Reports and readers shared by the TUI's test modules.

The suite is split by feature -- the table itself, sorting, search -- and
all three drive the same app over the same handful of reports, so the
arrangement lives here once. The readers pull what is actually drawn out
of the table rather than reaching into the app's own state, so a test
asserts what a reader would see.

Named `textual_support` rather than `support` because the unit suite
already has a module by that name, and pytest puts each test file's own
directory on `sys.path` -- two modules called `support` would shadow each
other.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from tingle.gates.cli.textual.browse import BrowseTable, MetricsApp, SearchBar, SortBar
from tingle.inits.services import Services
from tingle.links.editor import VsCodeCli
from tingle.mills.display import outcome_emoji, sections
from tingle.pacts.config import MetricSpec
from tingle.pacts.diff import DiffOutcome, DiffReport, DiffResult
from tingle.pacts.metrics import MetricResult, Occurrence
from tingle.pacts.report import MetricOutcome, RunReport

ROOT = Path("/proj")
SOURCE = Path("/proj/tingle.toml")


def summed_report(*outcomes: MetricOutcome) -> RunReport:
    """Wrap outcomes in a report shaped the way the mill hands one over.

    The emoji and the sections are ranked here rather than by hand, so a
    fixture cannot pass a test that a real report would fail.
    """
    ranked = tuple(replace(o, emoji=outcome_emoji(o.result, o.guide)) for o in outcomes)
    return RunReport(root=ROOT, source=SOURCE, sections=sections(ranked))


def diffed_report(*outcomes: DiffOutcome) -> DiffReport:
    """Do the same for a branch diff, which is ranked by its standing total."""
    ranked = tuple(replace(o, emoji=outcome_emoji(o.total, o.guide)) for o in outcomes)
    return DiffReport(
        root=ROOT,
        source=SOURCE,
        base_ref="main",
        merge_base="abc123",
        sections=sections(ranked),
    )


def grouped(name: str, group: str | None, *, value: int = 1) -> MetricOutcome:
    """Build one metric with a single located hit, in `group`."""
    return MetricOutcome(
        spec=MetricSpec(name=name, type="file_count", group=group),
        range_names=(),
        emoji="",
        result=MetricResult(
            value=value, occurrences=(Occurrence(path="x.py", line=1),)
        ),
    )


def valued(name: str, group: str, *, value: int, guide: int = 100) -> MetricOutcome:
    """Build a metric with a value and no hits: nothing to fold, only a number."""
    return MetricOutcome(
        spec=MetricSpec(name=name, type="file_count", group=group),
        range_names=(),
        emoji="",
        result=MetricResult(value=value),
        guide=guide,
    )


RUN_REPORT = summed_report(
    MetricOutcome(
        spec=MetricSpec(name="noqa-comments", type="regex_count"),
        range_names=("python",),
        emoji="",
        result=MetricResult(
            value=2,
            occurrences=(
                Occurrence(path="src/a.py", line=1),
                Occurrence(path="src/b.py", line=9),
            ),
        ),
    ),
    MetricOutcome(
        spec=MetricSpec(name="python-files", type="file_count"),
        range_names=("python",),
        emoji="",
        result=MetricResult(value=5),
    ),
)

DIFF_REPORT = diffed_report(
    DiffOutcome(
        spec=MetricSpec(name="noqa-comments", type="regex_count"),
        range_names=("python",),
        emoji="",
        result=DiffResult(
            net=1,
            added=2,
            removed=1,
            added_occurrences=(
                Occurrence(path="src/a.py", line=3),
                Occurrence(path="src/new.py", line=1),
            ),
            removed_occurrences=(Occurrence(path="src/b.py", line=9),),
        ),
        total=MetricResult(value=7),
    )
)

#: One group the branch moved and one it did not, for the folding rule.
QUIET_DIFF_REPORT = diffed_report(
    DiffOutcome(
        spec=MetricSpec(name="still", type="file_count", group="quiet"),
        range_names=(),
        emoji="",
        result=DiffResult(net=0, added=0, removed=0),
        total=MetricResult(value=12),
    ),
    DiffOutcome(
        spec=MetricSpec(name="moved", type="file_count", group="loud"),
        range_names=(),
        emoji="",
        result=DiffResult(net=2, added=2, removed=0),
        total=MetricResult(value=9),
    ),
)

GROUPED_REPORT = summed_report(
    grouped("type-ignores", "typing"),
    grouped("mypy-overrides", "typing"),
    grouped("noqa-comments", "lint"),
    grouped("python-files", None),
)


def metrics_app(
    report: RunReport | DiffReport, opener: VsCodeCli | None = None
) -> MetricsApp:
    """Build the app the way inits does, browse service and all.

    A test that is not about opening a hit gets an opener with nothing to
    open, which is a state the app already has to handle -- rather than
    the absence of one, which production never passes.
    """
    if opener is None:
        opener, _calls = recording_opener(available=False)
    return MetricsApp(report, opener, browse=Services().browse)


def column(app: MetricsApp, index: int) -> list[str]:
    """Read one column of the table exactly as it is drawn."""
    table = app.query_one(BrowseTable)
    return [str(table.get_row_at(row)[index]) for row in range(table.row_count)]


def outline(app: MetricsApp) -> list[str]:
    """Read the first column: indentation, fold marker and label, verbatim."""
    return column(app, 0)


def labels(app: MetricsApp) -> list[str]:
    """Read just the labels, with the outline's indent and marker stripped off."""
    return [text.strip().lstrip("▾▸ ").strip() for text in outline(app)]


def cursor(app: MetricsApp) -> str:
    """Read the label of the row the cursor is on."""
    return labels(app)[app.query_one(BrowseTable).cursor_row]


def headers(app: MetricsApp) -> list[str]:
    """Read the column headings, which carry the sort marker when one is set.

    The room a heading keeps for a marker it does not currently carry is
    trailing space, and reads as the heading alone.
    """
    table = app.query_one(BrowseTable)
    return [str(heading.label).rstrip() for heading in table.columns.values()]


def drawn_headers(app: MetricsApp) -> str:
    """Read the heading row as it reaches the screen, truncation and all.

    A heading is set on the column and drawn from the column's width, which
    are two different things: a marker the column has no room for is stored
    and then cut off, so only the drawn line proves the reader can see it.
    """
    return app.query_one(BrowseTable).render_line(0).text


def status(app: MetricsApp) -> str:
    """Read the line under the table: the sort stack, or the live query."""
    return str(app.query_one(SortBar).render())


def search_box(app: MetricsApp) -> SearchBar:
    """Find the `/` query box, hidden until search mode is entered."""
    return app.query_one(SearchBar)


def recording_opener(*, available: bool = True) -> tuple[VsCodeCli, list[list[str]]]:
    """Build the real VS Code adapter with its `code` spawn captured, not run."""
    calls: list[list[str]] = []
    opener = VsCodeCli(
        environ={"TERM_PROGRAM": "vscode"} if available else {},
        which=lambda name: "/usr/bin/code" if name == "code" else None,
        spawn=lambda args: calls.append(list(args)),
    )
    return opener, calls
