"""The doc pages that make claims about the code, checked against it.

Both pages read here are files on disk, which is what puts these in the
integration suite rather than beside the unit tests for the layers they
exercise: a docs edit must not break `test:unit`.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from typer.main import get_group

from tingle.gates.cli.typer import CliGate
from tingle.inits.services import Services
from tingle.mills.config import validate
from tingle.mills.metrics.registry import METRIC_TYPES

DOCS = Path(__file__).parents[2] / "docs"

#: Only ever a label in the errors `validate` would raise; nothing is read.
SOURCE = Path("/proj/tingle.toml")


def _documented_options(body: str) -> set[str]:
    # every command documents its options as a table, `| `--flag` | ... |`.
    # Anchoring at the row start reads the first cell only, so a flag merely
    # named in a Meaning column does not count as documented. No rows means
    # no options, which is `tingle init`.
    return {
        match.group(1)
        for line in body.splitlines()
        if (match := re.match(r"\| `(--[\w-]+)", line))
    }


def test_cli_page_documents_every_command_and_option() -> None:
    page = (DOCS / "cli.md").read_text(encoding="utf-8")
    documented = {
        match.group(1): _documented_options(match.group(2))
        for match in re.finditer(
            r"^## `tingle ?(\w*)`\n(.*?)(?=^## |\Z)", page, re.MULTILINE | re.DOTALL
        )
    }
    group = get_group(CliGate(Services()).app)
    exposed = {
        name: {opt for param in command.params for opt in param.opts if opt[:2] == "--"}
        for name, command in (("", group), *group.commands.items())
    }
    assert documented == exposed


def test_configuration_page_example_is_a_valid_config() -> None:
    # the first TOML block of the page is the example every setting is
    # explained against; parsing it into a Config is what keeps the two in step
    page = (DOCS / "configuration.md").read_text(encoding="utf-8")
    block = re.search(r"```toml\n(.*?)```", page, re.DOTALL)
    assert block is not None
    config = validate(tomllib.loads(block.group(1)), METRIC_TYPES, source=SOURCE)
    assert set(config.ranges) == {"python", "js"}
    assert [m.name for m in config.metrics] == ["noqa-comments", "todo-comments"]
    assert config.default_range.name == "python"
