from __future__ import annotations

import asyncio
import json
from importlib import metadata
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from conftest import SETTLE_STEP, SETTLE_TRIES
from textual_support import column
from typer.testing import CliRunner

from tingle.gates.cli import typer as typer_gate
from tingle.gates.cli.textual.browse import BrowseTable, MetricsApp
from tingle.gates.cli.typer import CliGate
from tingle.inits.services import Services
from tingle.mills.metrics.registry import METRIC_TYPES
from tingle.pacts.metrics import MetricContext, MetricResult, MetricType

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()
app = CliGate(Services()).app


#: Two groups over three metrics, so that selecting one group is neither
#: every metric nor a single one.
GROUPED_CONFIG = """
[ranges.python]
include = ["src/**/*.py"]
default = true

[[metrics]]
name = "lint-escapes"
type = "regex_count"
pattern = '#\\s*noqa'
group = "lint"

[[metrics]]
name = "debug-comments"
type = "regex_count"
pattern = '#\\s*debug'
group = "lint"

[[metrics]]
name = "python-files"
type = "file_count"
group = "size"
"""


@pytest.fixture
def project(workdir: Path, counting_config_text: str) -> Path:
    (workdir / "tingle.toml").write_text(counting_config_text)
    src = workdir / "src"
    src.mkdir()
    (src / "a.py").write_text("x = 1  # noqa\ny = 2  # noqa\n")
    (src / "b.py").write_text("z = 3  # noqa\n")
    return workdir


@pytest.fixture
def grouped_project(workdir: Path) -> Path:
    (workdir / "tingle.toml").write_text(GROUPED_CONFIG)
    src = workdir / "src"
    src.mkdir()
    (src / "a.py").write_text("x = 1  # noqa\ny = 2  # debug\n")
    return workdir


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == f"tingle {metadata.version('tingle')}"


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


@pytest.mark.usefixtures("project")
def test_bare_invocation_prints_summary_when_not_a_tty() -> None:
    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "lint-escapes" in result.output
    assert "3" in result.output
    assert "python-files" in result.output


@pytest.mark.usefixtures("project")
def test_stat_table() -> None:
    result = runner.invoke(app, ["stat"])

    assert result.exit_code == 0
    assert "lint-escapes" in result.output
    assert "3" in result.output


@pytest.mark.usefixtures("project")
def test_stat_json_is_values_only() -> None:
    result = runner.invoke(app, ["stat", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["config"].endswith("tingle.toml")
    metrics = {entry["name"]: entry for entry in payload["metrics"]}
    noqa = metrics["lint-escapes"]
    assert noqa["value"] == 3
    assert "occurrences" not in noqa
    assert "details" not in noqa
    assert metrics["python-files"]["value"] == 2


@pytest.mark.usefixtures("project")
def test_report_lists_occurrences() -> None:
    result = runner.invoke(app, ["report"])

    assert result.exit_code == 0
    # The value is led by how bad it is against its guide, and with none set the
    # guide is derived from the size of the codebase. This fixture is a handful
    # of lines, so three noqa comments really are a dense pile of debt.
    assert "lint-escapes (regex_count): 🔥 3" in result.output
    assert "src/a.py:1" in result.output
    assert "src/a.py:2" in result.output
    assert "src/b.py:1" in result.output
    assert "python-files (file_count): 🔥 2" in result.output


@pytest.mark.usefixtures("project")
def test_report_json_includes_occurrences() -> None:
    result = runner.invoke(app, ["report", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    metrics = {entry["name"]: entry for entry in payload["metrics"]}
    noqa = metrics["lint-escapes"]
    assert noqa["value"] == 3
    assert noqa["details"] == {"src/a.py": 2, "src/b.py": 1}
    assert noqa["occurrences"] == [
        {"file": "src/a.py", "line": 1, "note": None},
        {"file": "src/a.py", "line": 2, "note": None},
        {"file": "src/b.py", "line": 1, "note": None},
    ]


@pytest.mark.usefixtures("project")
def test_metric_filter() -> None:
    result = runner.invoke(app, ["stat", "--json", "--metric", "python-files"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert [entry["name"] for entry in payload["metrics"]] == ["python-files"]


@pytest.mark.usefixtures("project")
def test_unknown_metric_filter_exits_2() -> None:
    result = runner.invoke(app, ["stat", "--metric", "nope"])

    assert result.exit_code == 2
    # the config is valid; the typo is on the command line, so the user
    # must not be sent to tingle.toml to look for it
    assert 'usage error: unknown metric "nope"' in result.stderr
    assert "config error" not in result.stderr


@pytest.mark.usefixtures("grouped_project")
def test_group_filter_takes_every_metric_under_the_group() -> None:
    result = runner.invoke(app, ["report", "--json", "--group", "lint"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert [entry["name"] for entry in payload["metrics"]] == [
        "lint-escapes",
        "debug-comments",
    ]


@pytest.mark.usefixtures("grouped_project")
def test_group_and_metric_filters_are_a_union() -> None:
    result = runner.invoke(
        app, ["stat", "--json", "--group", "size", "--metric", "lint-escapes"]
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert [entry["name"] for entry in payload["metrics"]] == [
        "lint-escapes",
        "python-files",
    ]


@pytest.mark.usefixtures("grouped_project")
def test_unknown_group_filter_exits_2() -> None:
    result = runner.invoke(app, ["report", "--group", "nope"])

    assert result.exit_code == 2
    assert 'usage error: unknown group "nope"' in result.stderr
    assert "config error" not in result.stderr


def test_missing_config_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["stat"])

    assert result.exit_code == 2
    assert "config error" in result.stderr


def test_invalid_config_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "tingle.toml").write_text('[[metrics]]\nname = "x"\ntype = "nope"\n')
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["stat"])

    assert result.exit_code == 2
    assert "unknown type 'nope'" in result.stderr


@pytest.mark.usefixtures("project")
def test_raising_metric_exits_1_but_others_run(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_: MetricContext) -> MetricResult:
        msg = "boom"
        raise RuntimeError(msg)

    monkeypatch.setitem(
        METRIC_TYPES, "file_count", MetricType(name="file_count", func=boom)
    )

    result = runner.invoke(app, ["stat", "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    metrics = {entry["name"]: entry for entry in payload["metrics"]}
    assert metrics["python-files"]["error"] == "RuntimeError: boom"
    assert metrics["python-files"]["value"] is None
    assert metrics["lint-escapes"]["value"] == 3
    assert "error: python-files: RuntimeError: boom" in result.stderr


@pytest.mark.usefixtures("project")
def test_run_command_is_gone() -> None:
    result = runner.invoke(app, ["run"])

    assert result.exit_code != 0


@pytest.mark.usefixtures("project")
def test_list_shows_configured_metrics() -> None:
    result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert "lint-escapes" in result.output
    assert "regex_count" in result.output


@pytest.mark.usefixtures("grouped_project")
def test_list_names_the_groups_that_group_takes() -> None:
    """Otherwise the only way to learn a valid --group value is the config file."""
    result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert "Group" in result.output
    assert "lint" in result.output
    assert "size" in result.output


def test_list_types_works_without_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["list", "--types"])

    assert result.exit_code == 0
    for name in METRIC_TYPES:
        assert name in result.output


@pytest.mark.usefixtures("project")
def test_a_terminal_gets_the_interactive_table(interactive: list[MetricsApp]) -> None:
    """The only path that builds the TUI, and so the only one that wires it.

    The real app is built, not a stand-in: `browse` is keyword-only and has
    no default, so reaching this assertion is itself the wiring check.
    """
    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert len(interactive) == 1
    assert isinstance(interactive[0], MetricsApp)
    assert "python-files" not in result.output  # the table was not printed instead


@pytest.mark.usefixtures("repo")
def test_a_terminal_asking_for_a_diff_gets_one(interactive: list[MetricsApp]) -> None:
    """What the app was handed, not merely that it was handed something.

    A regression collecting a whole-tree run here would build a
    `MetricsApp` all the same, so the table is read for the one thing
    only a branch report can say: what the branch moved.
    """
    result = runner.invoke(app, ["--diff"])

    assert result.exit_code == 0
    assert len(interactive) == 1
    assert "lint-escapes" not in result.output
    assert all("net " in cell for cell in _drawn_values(interactive[0]))


def _drawn_values(built: MetricsApp) -> list[str]:
    """Run the app the gate built, and read its value column.

    The app starts the run rather than being handed one, so the table is
    read once the worker has finished and the message it posted has been
    taken off the loop -- not merely once the app is up.
    """

    async def scenario() -> list[str]:
        async with built.run_test() as pilot:
            for _ in range(SETTLE_TRIES):
                if (
                    built.measured.report is not None
                    and built.query_one(BrowseTable).row_count
                ):
                    break
                await pilot.pause(SETTLE_STEP)
            return column(built, 2)

    values = asyncio.run(scenario())
    assert values, "the app drew no rows to read"
    return values


@pytest.mark.usefixtures("project")
def test_a_pipe_gets_the_summary_table_instead(
    interactive: list[MetricsApp], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The tty check is the whole switch: without one, nothing interactive runs."""
    monkeypatch.setattr(
        typer_gate, "sys", SimpleNamespace(stdout=SimpleNamespace(isatty=lambda: False))
    )

    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert not interactive
    assert "lint-escapes" in result.output
