"""Console-script entry point: inject the services into the CLI gate."""

from __future__ import annotations

from tingle.gates.cli.typer import CliGate
from tingle.inits.services import Services


def run() -> None:
    """Build the service graph and hand it to the command line."""
    CliGate(Services()).run()
