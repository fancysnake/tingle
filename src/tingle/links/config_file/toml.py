"""TOML adapter for tingle's own configuration file."""

from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING, Any

import tomlkit

from tingle.pacts.config import ConfigError, ConfigNotFoundError, ConfigStore

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from tomlkit.items import Table

TINGLE_FILE = "tingle.toml"
PYPROJECT_FILE = "pyproject.toml"

STARTER = r"""# tingle configuration
# Ranges are named file sets; each metric measures the files of its ranges.

[ranges.python]
include = ["src/**/*.py", "tests/**/*.py"]
default = true

# [ranges.js]
# include = ["frontend/**/*.js", "frontend/**/*.ts"]

# A metric states what it counts...
[[metrics]]
name = "noqa-comments"
type = "regex_count"
pattern = '#\s*noqa'

# ...or names a ready-made one and overrides what differs.
# Run `tingle library` to see them all.
# [[metrics]]
# base = "tingle.builtins.mypy.type_ignore_comment"
# extra_ignore_lines = ['# @generated']

# [[metrics]]
# name = "old-client-uses"
# type = "symbol_uses"
# symbol = "myapp.legacy.OldClient"

# [[metrics]]
# base = "tingle.builtins.ruff.lint_ignores"

# [[metrics]]
# base = "tingle.builtins.pylint.rcfile_disables"
"""


class TomlConfigStore(ConfigStore):
    # the receiver is required by the ConfigStore protocol, not by the bodies
    # pylint: disable=no-self-use
    """Reads and edits tingle's configuration as TOML."""

    def load_raw(
        self, root: Path, override: Path | None = None
    ) -> tuple[Path, dict[str, Any]]:
        """Locate and parse the tingle configuration.

        Returns the file the configuration came from and its raw, unvalidated
        content. `tingle.toml` wins over `[tool.tingle]` in `pyproject.toml`.
        """
        if override is not None:
            if not override.is_file():
                msg = f"config file not found: {override}"
                raise ConfigNotFoundError(msg)
            return override, _parse(override)

        tingle = root / TINGLE_FILE
        if tingle.is_file():
            return tingle, _parse(tingle)

        pyproject = root / PYPROJECT_FILE
        if pyproject.is_file():
            section = _parse(pyproject).get("tool", {}).get("tingle")
            if isinstance(section, dict):
                return pyproject, section
            if section is not None:
                raise ConfigError([f"{pyproject}: [tool.tingle] must be a table"])

        msg = f"no {TINGLE_FILE} or [tool.tingle] in {PYPROJECT_FILE} found in {root}"
        raise ConfigNotFoundError(msg)

    def edit_target(self, root: Path) -> Path:
        """Return the config file `tingle add` should edit.

        tingle.toml wins; pyproject.toml only when it already carries a
        [tool.tingle] table; otherwise a fresh tingle.toml (to be created).
        """
        tingle = root / TINGLE_FILE
        if tingle.is_file():
            return tingle
        pyproject = root / PYPROJECT_FILE
        if pyproject.is_file():
            section = _parse(pyproject).get("tool", {}).get("tingle")
            if isinstance(section, dict):
                return pyproject
        return tingle

    def append_metric(self, path: Path, metric: Mapping[str, Any]) -> None:
        """Append a [[metrics]] entry, preserving existing formatting."""
        document = (
            tomlkit.parse(path.read_text(encoding="utf-8"))
            if path.is_file()
            else tomlkit.document()
        )
        container: Any = document
        if path.name == PYPROJECT_FILE:
            container = document["tool"]["tingle"]  # guaranteed by edit_target

        if "metrics" not in container:
            container["metrics"] = tomlkit.aot()
        container["metrics"].append(_metric_table(metric))

        path.write_text(tomlkit.dumps(document), encoding="utf-8")

    def render_metric(self, metric: Mapping[str, Any]) -> str:
        """Write a metric entry out as the `[[metrics]]` TOML it is."""
        document = tomlkit.document()
        metrics = tomlkit.aot()
        metrics.append(_metric_table(metric))
        document["metrics"] = metrics
        return tomlkit.dumps(document).strip()

    def write_starter(self, root: Path) -> Path:
        """Create a commented starter tingle.toml; refuse to overwrite."""
        path = root / TINGLE_FILE
        if path.exists():
            raise FileExistsError(path)
        path.write_text(STARTER, encoding="utf-8")
        return path


def _metric_table(metric: Mapping[str, Any]) -> Table:
    """Build one `[[metrics]]` table, however it is about to be used."""
    table = tomlkit.table()
    for key, value in metric.items():
        table[key] = _value(value)
    return table


def _value(value: object) -> object:
    """Quote a value the way that leaves a regex readable.

    Most params of the built-in templates are patterns, and a basic string
    doubles every backslash in one. A literal string cannot hold a single
    quote or a newline, so tomlkit is asked and takes the basic form back
    when it says no.
    """
    if isinstance(value, str) and "\\" in value:
        try:
            return tomlkit.string(value, literal=True)
        except ValueError:
            return tomlkit.string(value)
    return value


def _parse(path: Path) -> dict[str, Any]:
    with path.open("rb") as fp:
        try:
            return tomllib.load(fp)
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError([f"{path}: invalid TOML: {exc}"]) from exc
