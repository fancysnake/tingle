"""Command-line gate for tingle (typer adapter)."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, NoReturn

import typer
from rich.console import Console
from rich.table import Table

from tingle import __version__
from tingle.gates.cli import render
from tingle.inits.wiring import (
    METRIC_TYPES,
    append_metric_to,
    config_edit_target,
    load_config,
    load_raw_config,
    project_files,
    write_starter_config,
)
from tingle.inits.wiring import diff_source as make_diff_source
from tingle.mills.add import build_metric
from tingle.mills.diff import DiffRunner
from tingle.mills.runner import run as run_metrics
from tingle.pacts.config import (
    Config,
    ConfigError,
    ConfigNotFoundError,
    MetricDraft,
)
from tingle.pacts.diff import DiffReport, DiffSourceError

if TYPE_CHECKING:
    from tingle.pacts.report import RunReport

app = typer.Typer(add_completion=False)
_stdout = Console()

ConfigOption = Annotated[
    Path | None, typer.Option("--config", help="Path to the config file.")
]
MetricOption = Annotated[
    list[str] | None,
    typer.Option("--metric", help="Run only the named metric (repeatable)."),
]
JsonOption = Annotated[
    bool, typer.Option("--json", help="Machine-readable JSON output.")
]
DiffOption = Annotated[
    bool,
    typer.Option("--diff", help="Measure the current branch's impact instead."),
]
BaseOption = Annotated[
    str | None,
    typer.Option(
        "--base",
        help="Base branch for --diff (default: [diff] base in the config,"
        " then 'main'). Implies --diff.",
    ),
]


def _show_version(value: bool) -> None:
    if value:
        typer.echo(f"tingle {__version__}")
        raise typer.Exit


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    _version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_show_version,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = False,
    diff: DiffOption = False,
    base: BaseOption = None,
    config: ConfigOption = None,
    metric: MetricOption = None,
) -> None:
    """Measure code metrics during constant refactoring.

    Without a subcommand: interactive mode on a terminal, the summary
    table otherwise.
    """
    if ctx.invoked_subcommand is not None:
        return
    if sys.stdout.isatty():
        _interactive(diff or base is not None, base, config, metric)
    else:
        _print_stat(diff or base is not None, base, config, metric, json_out=False)


@app.command("stat")
def stat_command(
    json_out: JsonOption = False,
    diff: DiffOption = False,
    base: BaseOption = None,
    config: ConfigOption = None,
    metric: MetricOption = None,
) -> None:
    """Print the metric summary (values only)."""
    _print_stat(diff or base is not None, base, config, metric, json_out=json_out)


@app.command("report")
def report_command(
    json_out: JsonOption = False,
    diff: DiffOption = False,
    base: BaseOption = None,
    config: ConfigOption = None,
    metric: MetricOption = None,
) -> None:
    """Print the full report: every occurrence with file and line."""
    if diff or base is not None:
        diff_report = _collect_diff(base, config, metric)
        if json_out:
            typer.echo(render.diff_json(diff_report))
        else:
            for line in render.diff_listing(diff_report):
                _stdout.print(line)
        _finish_diff(diff_report)
    else:
        run_report = _collect_run(config, metric)
        if json_out:
            typer.echo(render.run_json(run_report))
        else:
            for line in render.run_listing(run_report):
                _stdout.print(line)
        _finish_run(run_report)


@app.command("list")
def list_command(
    types: Annotated[
        bool, typer.Option("--types", help="List available metric types.")
    ] = False,
    config: ConfigOption = None,
) -> None:
    """List configured metrics, or available metric types with --types."""
    if types:
        _stdout.print(_types_table())
        return
    _stdout.print(_metrics_table(_load(config)))


@app.command("add")
def add_command(
    type_name: Annotated[str, typer.Argument(metavar="TYPE")],
    value: Annotated[str | None, typer.Argument(metavar="[VALUE]")] = None,
    name: Annotated[
        str | None,
        typer.Option("--name", help="Metric name (auto-generated if omitted)."),
    ] = None,
    range_names: Annotated[
        list[str] | None,
        typer.Option("--range", help="Target range (repeatable)."),
    ] = None,
    param: Annotated[
        list[str] | None,
        typer.Option("--param", help="Extra metric param as key=value (repeatable)."),
    ] = None,
) -> None:
    r"""Add a metric to the config, e.g.: tingle add regex_count '#\\s*noqa'."""
    cwd = Path.cwd()
    draft = MetricDraft(
        type_name=type_name,
        value=value,
        name=name,
        ranges=tuple(range_names or ()),
        params=_parse_params(param or []),
    )
    try:
        raw = load_raw_config(cwd)
        metric = build_metric(raw, METRIC_TYPES, draft)
    except ConfigError as exc:
        _config_failure(exc)
    target = config_edit_target(cwd)
    append_metric_to(target, metric)
    typer.echo(f'Added metric "{metric["name"]}" to {target}')


@app.command("init")
def init_command() -> None:
    """Create a starter tingle.toml in the current directory."""
    try:
        path = write_starter_config(Path.cwd())
    except FileExistsError as exc:
        typer.echo(f"config error: {exc.args[0]} already exists", err=True)
        raise typer.Exit(2) from None
    typer.echo(f"Created {path}")


def main() -> None:
    """Console-script entry point."""
    app()


def _interactive(
    diff: bool,
    base: str | None,
    config_path: Path | None,
    metrics: list[str] | None,
) -> None:
    """Interactive mode; falls back to the summary table until the TUI lands."""
    _print_stat(diff, base, config_path, metrics, json_out=False)


def _print_stat(
    diff: bool,
    base: str | None,
    config_path: Path | None,
    metrics: list[str] | None,
    *,
    json_out: bool,
) -> None:
    if diff:
        diff_report = _collect_diff(base, config_path, metrics)
        if json_out:
            typer.echo(render.diff_json(diff_report))
        else:
            _stdout.print(render.diff_table(diff_report))
        _finish_diff(diff_report)
    else:
        run_report = _collect_run(config_path, metrics)
        if json_out:
            typer.echo(render.run_json(run_report))
        else:
            _stdout.print(render.report_table(run_report))
        _finish_run(run_report)


def _collect_run(
    config_path: Path | None, metrics: list[str] | None
) -> RunReport:
    config = _load(config_path)
    try:
        return run_metrics(
            config, project_files(config.root), METRIC_TYPES, only=metrics
        )
    except ConfigError as exc:
        _config_failure(exc)


def _collect_diff(
    base: str | None, config_path: Path | None, metrics: list[str] | None
) -> DiffReport:
    config = _load(config_path)
    runner = DiffRunner(
        config=config,
        project=project_files(config.root),
        diff_source=make_diff_source(config.root),
        metric_types=METRIC_TYPES,
    )
    try:
        return runner.run(base or config.diff_base or "main", only=metrics)
    except ConfigError as exc:
        _config_failure(exc)
    except DiffSourceError as exc:
        typer.echo(f"diff error: {exc}", err=True)
        raise typer.Exit(2) from None


def _finish_run(report: RunReport) -> None:
    for outcome in report.outcomes:
        if outcome.error is not None:
            typer.echo(f"error: {outcome.spec.name}: {outcome.error}", err=True)
        elif outcome.result is not None:
            for warning in outcome.result.warnings:
                typer.echo(f"warning: {outcome.spec.name}: {warning}", err=True)
    if any(outcome.error for outcome in report.outcomes):
        raise typer.Exit(1)


def _finish_diff(report: DiffReport) -> None:
    for name in report.skipped:
        typer.echo(
            f"note: {name}: metric type does not support diff mode", err=True
        )
    for outcome in report.outcomes:
        if outcome.error is not None:
            typer.echo(f"error: {outcome.spec.name}: {outcome.error}", err=True)
        elif outcome.result is not None:
            for warning in outcome.result.warnings:
                typer.echo(f"warning: {outcome.spec.name}: {warning}", err=True)
    if any(outcome.error for outcome in report.outcomes):
        raise typer.Exit(1)


def _parse_params(pairs: list[str]) -> dict[str, str]:
    params: dict[str, str] = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep or not key:
            typer.echo(
                f'config error: invalid --param "{pair}" (expected key=value)',
                err=True,
            )
            raise typer.Exit(2)
        params[key] = value
    return params


def _load(config_path: Path | None) -> Config:
    try:
        return load_config(Path.cwd(), config_path)
    except (ConfigError, ConfigNotFoundError) as exc:
        _config_failure(exc)


def _config_failure(exc: Exception) -> NoReturn:
    if isinstance(exc, ConfigError):
        for line in exc.errors:
            typer.echo(f"config error: {line}", err=True)
    else:
        typer.echo(f"config error: {exc}", err=True)
    raise typer.Exit(2)


def _types_table() -> Table:
    table = Table("Type", "Required params", "Optional params", "Description")
    for metric_type in sorted(METRIC_TYPES.values(), key=lambda t: t.name):
        table.add_row(
            metric_type.name,
            ", ".join(metric_type.required_params),
            ", ".join(metric_type.optional_params),
            metric_type.description,
        )
    return table


def _metrics_table(config: Config) -> Table:
    table = Table("Metric", "Type", "Ranges")
    for spec in config.metrics:
        ranges = ", ".join(spec.ranges) if spec.ranges else config.default_range.name
        table.add_row(spec.name, spec.type, ranges)
    return table
