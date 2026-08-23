"""The seam between the TUI and the command line that launched it.

Four ways out of an interactive run used to happen before the app
existed, and three of them now happen inside it. What matters is that the
command line still reports them the same way: the app carries a failure
out, it does not decide what one means.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from tingle.gates.cli.typer import CliGate
from tingle.inits.services import Services
from tingle.mills.metrics.registry import METRIC_TYPES

if TYPE_CHECKING:
    from pathlib import Path

    from tingle.pacts.metrics import MetricContext, MetricResult

runner = CliRunner()
app = CliGate(Services()).app


@pytest.mark.usefixtures("repo", "headless")
def test_a_bad_metric_name_is_a_usage_error_not_a_report() -> None:
    """The selection is checked by the run, which now happens in the TUI."""
    result = runner.invoke(app, ["--metric", "nope"])

    assert result.exit_code == 2
    assert "usage error" in result.output
    assert "nope" in result.output


@pytest.mark.usefixtures("repo", "headless")
def test_a_base_that_does_not_exist_is_a_diff_error() -> None:
    result = runner.invoke(app, ["--base", "no-such-branch"])

    assert result.exit_code == 2
    assert "diff error" in result.output


@pytest.mark.usefixtures("repo", "headless")
def test_a_metric_that_raises_exits_one_and_says_which(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Metric isolation still holds: the table is browsed, then the error."""

    def boom(_: MetricContext) -> MetricResult:
        msg = "boom"
        raise RuntimeError(msg)

    monkeypatch.setitem(
        METRIC_TYPES, "regex_count", replace(METRIC_TYPES["regex_count"], func=boom)
    )

    result = runner.invoke(app, [])

    assert result.exit_code == 1
    assert "error: lint-escapes: RuntimeError: boom" in result.output


@pytest.mark.usefixtures("headless")
def test_a_broken_config_never_opens_a_terminal_app(workdir: Path) -> None:
    """Read before the app starts, so it fails as a command rather than a screen."""
    (workdir / "tingle.toml").write_text("[[metrics]]\nname = 1\n")

    result = runner.invoke(app, [])

    assert result.exit_code == 2
    assert "config error" in result.output


@pytest.mark.usefixtures("repo", "headless")
def test_a_clean_run_exits_zero_and_prints_no_table() -> None:
    """The report went to the TUI, so stdout carries none of it."""
    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "lint-escapes" not in result.output


@pytest.mark.usefixtures("repo", "headless")
def test_an_interactive_diff_reports_its_notes_after_the_table() -> None:
    """A branch run browsed and then finished, notes and exit code and all."""
    result = runner.invoke(app, ["--diff"])

    assert result.exit_code == 0
    # the config carries a metric with no diff variant, which is skipped
    assert "note: ruff-ignores" not in result.output
    assert "lint-escapes" not in result.output
