"""Command-line gate for tingle (typer adapter)."""

from typing import Annotated

import typer

from tingle import __version__

app = typer.Typer(add_completion=False)


def _show_version(value: bool) -> None:
    if value:
        typer.echo(f"tingle {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_show_version,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = False,
) -> None:
    """Measure code metrics during constant refactoring."""


def main() -> None:
    app()
