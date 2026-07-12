"""Command-line gate for tingle (typer adapter)."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, NoReturn

import typer
from rich.console import Console
from rich.table import Table

from tingle.gates.cli import render
from tingle.mills.metrics.registry import METRIC_TYPES
from tingle.pacts.config import (
    CheckPolicy,
    Config,
    ConfigError,
    ConfigNotFoundError,
    MetricDraft,
)
from tingle.pacts.diff import DiffReport, DiffSourceError

if TYPE_CHECKING:
    from tingle.pacts.check import CheckVerdict
    from tingle.pacts.report import RunReport
    from tingle.pacts.services import ServicesProtocol

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
    bool, typer.Option("--diff", help="Measure the current branch's impact instead.")
]
BaseOption = Annotated[
    str | None,
    typer.Option(
        "--base",
        # rich reads [diff] as a markup tag and swallows it; \[ escapes it
        help="Base branch for --diff (default: \\[diff] base in the config,"
        " then 'main'). Implies --diff.",
    ),
]
PolicyOption = Annotated[
    str | None,
    typer.Option(
        "--policy",
        help="Override \\[check] policy: 'sum' fails when the metrics grow in"
        " total, 'any' fails when a single metric grows.",
    ),
]


def _show_version(value: bool) -> None:
    if value:
        # importlib.metadata pulls in the email parser, so it is imported here
        # rather than at module level: only --version pays for it.
        from importlib import metadata  # pylint: disable=import-outside-toplevel

        typer.echo(f"tingle {metadata.version('tingle')}")
        raise typer.Exit


VersionOption = Annotated[
    bool,
    typer.Option(
        "--version",
        callback=_show_version,
        is_eager=True,
        help="Show version and exit.",
    ),
]


@dataclass(frozen=True)
class _MetricRequest:
    """The selection options every metric command carries down to collection."""

    diff: bool
    base: str | None
    config: Path | None
    metrics: list[str] | None


class CliGate:
    """The `tingle` command line, driven by the services it is handed."""

    def __init__(self, services: ServicesProtocol) -> None:
        """Build the typer app, binding every command to these services."""
        self._services = services
        self._stdout = Console()
        self.app = typer.Typer(add_completion=False)
        self.app.callback(invoke_without_command=True)(self._root)
        self.app.command("stat")(self.stat)
        self.app.command("check")(self.check)
        self.app.command("report")(self.report)
        self.app.command("list")(self.list_metrics)
        self.app.command("add")(self.add)
        self.app.command("init")(self.init)

    def run(self) -> None:
        """Parse the command line and dispatch."""
        self.app()

    def _root(
        self,
        ctx: typer.Context,
        *,
        _version: VersionOption = False,
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
        request = _MetricRequest(
            diff=diff or base is not None, base=base, config=config, metrics=metric
        )
        if sys.stdout.isatty():
            self._interactive(request)
        else:
            self._print_stat(request, json_out=False)

    def stat(
        self,
        *,
        json_out: JsonOption = False,
        diff: DiffOption = False,
        base: BaseOption = None,
        config: ConfigOption = None,
        metric: MetricOption = None,
    ) -> None:
        """Print the metric summary (values only)."""
        request = _MetricRequest(
            diff=diff or base is not None, base=base, config=config, metrics=metric
        )
        self._print_stat(request, json_out=json_out)

    def check(
        self,
        *,
        policy: PolicyOption = None,
        base: BaseOption = None,
        config: ConfigOption = None,
        metric: MetricOption = None,
    ) -> None:
        """Fail (exit 1) if the branch worsened the metrics. For CI.

        Prints only what the branch added, under the metrics that grew.
        """
        request = _MetricRequest(diff=True, base=base, config=config, metrics=metric)
        loaded = self._load(config)
        report, verdict = self._collect_check(
            loaded, request, policy=self._parse_policy(policy)
        )
        for line in render.check_listing(verdict):
            self._stdout.print(line)
        self._finish_diff(report)
        if verdict.failed:
            typer.echo(render.check_reason(verdict), err=True)
            raise typer.Exit(1)
        # say so: silence would be indistinguishable from a step that never ran
        self._stdout.print(render.check_success(verdict, report.base_ref))

    def report(
        self,
        *,
        json_out: JsonOption = False,
        cobertura: Annotated[
            bool,
            typer.Option(
                "--cobertura",
                help="Cobertura XML for CI consumers (line-scoped metrics only).",
            ),
        ] = False,
        diff: DiffOption = False,
        base: BaseOption = None,
        config: ConfigOption = None,
        metric: MetricOption = None,
    ) -> None:
        """Print the full report: every occurrence with file and line."""
        if cobertura and (json_out or diff or base is not None):
            typer.echo(
                "usage error: --cobertura cannot be combined with --json or --diff",
                err=True,
            )
            raise typer.Exit(2)
        request = _MetricRequest(
            diff=diff or base is not None, base=base, config=config, metrics=metric
        )
        if cobertura:
            run_report = self._collect_run(request)
            xml, excluded = render.cobertura(run_report)
            typer.echo(xml)
            for name in excluded:
                typer.echo(
                    f"note: {name}: not representable in cobertura"
                    " (no line locations)",
                    err=True,
                )
            self._finish_run(run_report)
            return
        if request.diff:
            diff_report = self._collect_diff(request)
            if json_out:
                typer.echo(render.diff_json(diff_report))
            else:
                for line in render.diff_listing(diff_report):
                    self._stdout.print(line)
            self._finish_diff(diff_report)
        else:
            run_report = self._collect_run(request)
            if json_out:
                typer.echo(render.run_json(run_report))
            else:
                for line in render.run_listing(run_report):
                    self._stdout.print(line)
            self._finish_run(run_report)

    def list_metrics(
        self,
        types: Annotated[
            bool, typer.Option("--types", help="List available metric types.")
        ] = False,
        config: ConfigOption = None,
    ) -> None:
        """List configured metrics, or available metric types with --types."""
        if types:
            self._stdout.print(_types_table())
            return
        self._stdout.print(_metrics_table(self._load(config)))

    def add(
        self,
        type_name: Annotated[str, typer.Argument(metavar="TYPE")],
        value: Annotated[str | None, typer.Argument(metavar="[VALUE]")] = None,
        *,
        name: Annotated[
            str | None,
            typer.Option("--name", help="Metric name (auto-generated if omitted)."),
        ] = None,
        range_names: Annotated[
            list[str] | None, typer.Option("--range", help="Target range (repeatable).")
        ] = None,
        group: Annotated[
            str | None,
            typer.Option("--group", help="Group heading to show this metric under."),
        ] = None,
        param: Annotated[
            list[str] | None,
            typer.Option(
                "--param", help="Extra metric param as key=value (repeatable)."
            ),
        ] = None,
    ) -> None:
        r"""Add a metric to the config, e.g.: tingle add regex_count '#\\s*noqa'."""
        draft = MetricDraft(
            type_name=type_name,
            value=value,
            name=name,
            ranges=tuple(range_names or ()),
            params=self._parse_params(param or []),
            group=group,
        )
        try:
            target, metric_name = self._services.config.add_metric(Path.cwd(), draft)
        except ConfigError as exc:
            self._config_failure(exc)
        typer.echo(f'Added metric "{metric_name}" to {target}')

    def init(self) -> None:
        """Create a starter tingle.toml in the current directory."""
        try:
            path = self._services.config.write_starter(Path.cwd())
        except FileExistsError as exc:
            typer.echo(f"config error: {exc.args[0]} already exists", err=True)
            raise typer.Exit(2) from None
        typer.echo(f"Created {path}")

    def _interactive(self, request: _MetricRequest) -> None:
        """Run the metrics, then hand the report to the interactive TUI."""
        # imported lazily: textual is heavy and only needed on this path
        from tingle.gates.tui.app import (  # pylint: disable=import-outside-toplevel
            MetricsApp,
        )

        if request.diff:
            diff_report = self._collect_diff(request)
            MetricsApp(diff_report).run()
            self._finish_diff(diff_report)
        else:
            run_report = self._collect_run(request)
            MetricsApp(run_report).run()
            self._finish_run(run_report)

    def _print_stat(self, request: _MetricRequest, *, json_out: bool) -> None:
        if request.diff:
            diff_report = self._collect_diff(request)
            if json_out:
                typer.echo(render.stat_diff_json(diff_report))
            else:
                self._stdout.print(render.diff_table(diff_report))
            self._finish_diff(diff_report)
        else:
            run_report = self._collect_run(request)
            if json_out:
                typer.echo(render.stat_json(run_report))
            else:
                self._stdout.print(render.report_table(run_report))
            self._finish_run(run_report)

    def _collect_run(self, request: _MetricRequest) -> RunReport:
        config = self._load(request.config)
        try:
            return self._services.metrics.run(config, only=request.metrics)
        except ConfigError as exc:
            self._config_failure(exc)

    def _collect_diff(self, request: _MetricRequest) -> DiffReport:
        config = self._load(request.config)
        try:
            return self._services.metrics.diff(
                config, self._base_of(config, request), only=request.metrics
            )
        except ConfigError as exc:
            self._config_failure(exc)
        except DiffSourceError as exc:
            self._diff_failure(exc)

    def _collect_check(
        self, config: Config, request: _MetricRequest, *, policy: CheckPolicy | None
    ) -> tuple[DiffReport, CheckVerdict]:
        try:
            return self._services.metrics.check(
                config,
                self._base_of(config, request),
                only=request.metrics,
                policy=policy,
            )
        except ConfigError as exc:
            self._config_failure(exc)
        except DiffSourceError as exc:
            self._diff_failure(exc)

    @staticmethod
    def _base_of(config: Config, request: _MetricRequest) -> str:
        return request.base or config.diff_base or "main"

    @staticmethod
    def _diff_failure(exc: DiffSourceError) -> NoReturn:
        typer.echo(f"diff error: {exc}", err=True)
        raise typer.Exit(2) from None

    def _load(self, config_path: Path | None) -> Config:
        try:
            return self._services.config.load(Path.cwd(), config_path)
        except (ConfigError, ConfigNotFoundError) as exc:
            self._config_failure(exc)

    @staticmethod
    def _finish_run(report: RunReport) -> None:
        for outcome in report.outcomes:
            if outcome.error is not None:
                typer.echo(f"error: {outcome.spec.name}: {outcome.error}", err=True)
            elif outcome.result is not None:
                for warning in outcome.result.warnings:
                    typer.echo(f"warning: {outcome.spec.name}: {warning}", err=True)
        if any(outcome.error for outcome in report.outcomes):
            raise typer.Exit(1)

    @staticmethod
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

    @staticmethod
    def _parse_policy(policy: str | None) -> CheckPolicy | None:
        """Turn --policy into the enum; None leaves the config's policy alone."""
        if policy is None:
            return None
        by_value = {member.value: member for member in CheckPolicy}
        if policy not in by_value:
            allowed = ", ".join(by_value)
            typer.echo(
                f'usage error: unknown --policy "{policy}"'
                f" (expected one of: {allowed})",
                err=True,
            )
            raise typer.Exit(2)
        return by_value[policy]

    @staticmethod
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

    @staticmethod
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
            ", ".join(metric_type.params.required),
            ", ".join(metric_type.params.optional),
            metric_type.description,
        )
    return table


def _metrics_table(config: Config) -> Table:
    table = Table("Metric", "Type", "Ranges")
    for spec in config.metrics:
        ranges = ", ".join(spec.ranges) if spec.ranges else config.default_range.name
        table.add_row(spec.name, spec.type, ranges)
    return table
