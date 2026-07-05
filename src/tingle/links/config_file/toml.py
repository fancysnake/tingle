"""TOML adapter for tingle's own configuration file."""

import tomllib
from pathlib import Path
from typing import Any

from tingle.pacts.config import ConfigError, ConfigNotFoundError

TINGLE_FILE = "tingle.toml"
PYPROJECT_FILE = "pyproject.toml"


def load_raw(root: Path, override: Path | None = None) -> tuple[Path, dict[str, Any]]:
    """Locate and parse the tingle configuration.

    Returns the file the configuration came from and its raw, unvalidated
    content. `tingle.toml` wins over `[tool.tingle]` in `pyproject.toml`.
    """
    if override is not None:
        if not override.is_file():
            raise ConfigNotFoundError(f"config file not found: {override}")
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

    raise ConfigNotFoundError(
        f"no {TINGLE_FILE} or [tool.tingle] in {PYPROJECT_FILE} found in {root}"
    )


def _parse(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as fp:
            return tomllib.load(fp)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError([f"{path}: invalid TOML: {exc}"]) from exc
