"""TOML adapter for tingle's own configuration file."""

from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING, Any

import tomlkit

from tingle.pacts.config import ConfigError, ConfigNotFoundError, ConfigStore

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

TINGLE_FILE = "tingle.toml"
PYPROJECT_FILE = "pyproject.toml"

STARTER = r"""# tingle configuration
# Ranges are named file sets; each metric measures the files of its ranges.

[ranges.python]
include = ["src/**/*.py", "tests/**/*.py"]
default = true

# [ranges.js]
# include = ["frontend/**/*.js", "frontend/**/*.ts"]

[[metrics]]
name = "noqa-comments"
type = "regex_count"
pattern = '#\s*noqa'

# [[metrics]]
# name = "old-client-uses"
# type = "symbol_uses"
# symbol = "myapp.legacy.OldClient"

# [[metrics]]
# name = "ruff-ignores"
# type = "toml_list_length"
# key = "tool.ruff.lint.ignore"

# [[metrics]]
# name = "pylint-disables"
# type = "ini_list_length"
# file = ".pylintrc"
# section = "MESSAGES CONTROL"
# option = "disable"
"""


class TomlConfigStore(ConfigStore):
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

        table = tomlkit.table()
        for key, value in metric.items():
            table[key] = value
        if "metrics" not in container:
            container["metrics"] = tomlkit.aot()
        container["metrics"].append(table)

        path.write_text(tomlkit.dumps(document), encoding="utf-8")

    def write_starter(self, root: Path) -> Path:
        """Create a commented starter tingle.toml; refuse to overwrite."""
        path = root / TINGLE_FILE
        if path.exists():
            raise FileExistsError(path)
        path.write_text(STARTER, encoding="utf-8")
        return path


def _parse(path: Path) -> dict[str, Any]:
    with path.open("rb") as fp:
        try:
            return tomllib.load(fp)
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError([f"{path}: invalid TOML: {exc}"]) from exc
