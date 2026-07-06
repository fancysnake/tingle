"""Command-line gate for tingle (typer adapter)."""

import json
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, NoReturn

import typer
from rich.console import Console
from rich.table import Table

from tingle import __version__
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
from tingle.pacts.diff import DiffSourceError

if TYPE_CHECKING:
    from tingle.pacts.diff import DiffReport, DiffResult
    from tingle.pacts.report import RunReport

app = typer.Typer(add_completion=False)
_stdout = Console()


class OutputFormat(StrEnum):
    """Report renderings selectable via --format."""

    TABLE = "table"
    JSON = "json"


FormatOption = Annotated[
    OutputFormat, typer.Option("--format", help="Output format.")
]
ConfigOption = Annotated[
    Path | None, typer.Option("--config", help="Path to the config file.")
]
MetricOption = Annotated[
    list[str] | None,
    typer.Option("--metric", help="Run only the named metric (repeatable)."),
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
    output_format: FormatOption = OutputFormat.TABLE,
    config: ConfigOption = None,
    metric: MetricOption = None,
) -> None:
    """Measure code metrics during constant refactoring."""
    if ctx.invoked_subcommand is None:
        _execute_run(output_format, config, metric)


@app.command("run")
def run_command(
    output_format: FormatOption = OutputFormat.TABLE,
    config: ConfigOption = None,
    metric: MetricOption = None,
) -> None:
    """Run the configured metrics and print a report."""
    _execute_run(output_format, config, metric)


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


@app.command("diff")
def diff_command(
    base: Annotated[
        str | None,
        typer.Option(
            "--base",
            help="Base branch to compare against"
            " (default: [diff] base in the config, then 'main').",
        ),
    ] = None,
    output_format: FormatOption = OutputFormat.TABLE,
    config: ConfigOption = None,
    metric: MetricOption = None,
) -> None:
    """Measure the impact of the current branch, diff-cover style."""
    loaded = _load(config)
    runner = DiffRunner(
        config=loaded,
        project=project_files(loaded.root),
        diff_source=make_diff_source(loaded.root),
        metric_types=METRIC_TYPES,
    )
    try:
        report = runner.run(base or loaded.diff_base or "main", only=metric)
    except ConfigError as exc:
        _config_failure(exc)
    except DiffSourceError as exc:
        typer.echo(f"diff error: {exc}", err=True)
        raise typer.Exit(2) from None

    if output_format is OutputFormat.JSON:
        typer.echo(_diff_to_json(report))
    else:
        _stdout.print(_diff_table(report))
    _print_diff_diagnostics(report)

    if any(outcome.error for outcome in report.outcomes):
        raise typer.Exit(1)


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


def _execute_run(
    output_format: OutputFormat,
    config_path: Path | None,
    metrics: list[str] | None,
) -> None:
    config = _load(config_path)
    try:
        report = run_metrics(
            config, project_files(config.root), METRIC_TYPES, only=metrics
        )
    except ConfigError as exc:
        _config_failure(exc)

    if output_format is OutputFormat.JSON:
        typer.echo(_to_json(report))
    else:
        _stdout.print(_report_table(report))
    _print_diagnostics(report)

    if any(outcome.error for outcome in report.outcomes):
        raise typer.Exit(1)


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


def _report_table(report: RunReport) -> Table:
    table = Table(title=str(report.root))
    table.add_column("Metric")
    table.add_column("Type")
    table.add_column("Ranges")
    table.add_column("Value", justify="right")
    for outcome in report.outcomes:
        value = (
            "[red]ERROR[/]"
            if outcome.result is None
            else str(outcome.result.value)
        )
        table.add_row(
            outcome.spec.name,
            outcome.spec.type,
            ", ".join(outcome.range_names),
            value,
        )
    return table


def _to_json(report: RunReport) -> str:
    return json.dumps(
        {
            "root": str(report.root),
            "config": str(report.source),
            "metrics": [
                {
                    "name": outcome.spec.name,
                    "type": outcome.spec.type,
                    "ranges": list(outcome.range_names),
                    "value": outcome.result.value if outcome.result else None,
                    "details": dict(outcome.result.details) if outcome.result else {},
                    "warnings": (
                        list(outcome.result.warnings) if outcome.result else []
                    ),
                    "error": outcome.error,
                }
                for outcome in report.outcomes
            ],
        },
        indent=2,
    )


def _print_diagnostics(report: RunReport) -> None:
    for outcome in report.outcomes:
        if outcome.error is not None:
            typer.echo(f"error: {outcome.spec.name}: {outcome.error}", err=True)
        elif outcome.result is not None:
            for warning in outcome.result.warnings:
                typer.echo(f"warning: {outcome.spec.name}: {warning}", err=True)


def _diff_table(report: DiffReport) -> Table:
    table = Table(title=f"{report.root} vs {report.base_ref}")
    table.add_column("Metric")
    table.add_column("Type")
    table.add_column("Added", justify="right")
    table.add_column("Removed", justify="right")
    table.add_column("Net", justify="right")
    table.add_column("Total", justify="right")
    for outcome in report.outcomes:
        if outcome.result is None:
            cells = ("", "", "[red]ERROR[/]", "")
        else:
            cells = (
                _added_cell(outcome.result.added),
                _removed_cell(outcome.result.removed),
                _net_cell(outcome.result.net),
                str(outcome.total.value) if outcome.total else "",
            )
        table.add_row(outcome.spec.name, outcome.spec.type, *cells)
    return table


def _added_cell(added: int | None) -> str:
    if added is None:
        return ""
    return f"[red]+{added}[/]" if added > 0 else "0"


def _removed_cell(removed: int | None) -> str:
    if removed is None:
        return ""
    return f"[green]-{removed}[/]" if removed > 0 else "0"


def _net_cell(net: int) -> str:
    if net > 0:
        return f"[red]+{net}[/]"
    if net < 0:
        return f"[green]{net}[/]"
    return "0"


def _diff_to_json(report: DiffReport) -> str:
    return json.dumps(
        {
            "root": str(report.root),
            "config": str(report.source),
            "base": report.base_ref,
            "merge_base": report.merge_base,
            "metrics": [
                {
                    "name": outcome.spec.name,
                    "type": outcome.spec.type,
                    "ranges": list(outcome.range_names),
                    **_diff_values(outcome.result),
                    "total": outcome.total.value if outcome.total else None,
                    "warnings": (
                        list(outcome.result.warnings) if outcome.result else []
                    ),
                    "error": outcome.error,
                }
                for outcome in report.outcomes
            ],
            "skipped": list(report.skipped),
        },
        indent=2,
    )


def _diff_values(result: DiffResult | None) -> dict[str, object]:
    if result is None:
        return {"added": None, "removed": None, "net": None, "details": {}}
    return {
        "added": result.added,
        "removed": result.removed,
        "net": result.net,
        "details": dict(result.details),
    }


def _print_diff_diagnostics(report: DiffReport) -> None:
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
