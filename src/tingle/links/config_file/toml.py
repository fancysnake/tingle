"""TOML adapter for tingle's own configuration file."""

from __future__ import annotations

import io
import tomllib
from pathlib import PurePath
from typing import TYPE_CHECKING, Any

import tomlkit

from tingle.pacts.config import ConfigError, ConfigNotFoundError, ConfigStore

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from pathlib import Path

    from tomlkit.items import Table

TINGLE_FILE = "tingle.toml"
PYPROJECT_FILE = "pyproject.toml"

STARTER_HEAD = """# tingle configuration
# Ranges are named file sets; each metric measures the files of its ranges.

[ranges.python]
include = ["src/**/*.py", "tests/**/*.py"]
default = true

# [ranges.js]
# include = ["frontend/**/*.js", "frontend/**/*.ts"]

"""

STARTER_DETECTED = """# Ready-made metrics for the tools this project configures.
# Run `tingle library` to see them all.
"""

STARTER_EXAMPLES = r"""# A metric states what it counts...
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
        content.
        """
        if override is not None:
            if not override.is_file():
                msg = f"config file not found: {override}"
                raise ConfigNotFoundError(msg)
            return override, _parsed(override.read_bytes(), override)

        def read(file: PurePath) -> bytes | None:
            path = root / file
            return path.read_bytes() if path.is_file() else None

        if (found := _discovered(read, labelled=root)) is None:
            msg = (
                f"no {TINGLE_FILE} or [tool.tingle] in {PYPROJECT_FILE} found in {root}"
            )
            raise ConfigNotFoundError(msg)
        file, raw = found
        return root / file, raw

    def load_at(
        self, read: Callable[[PurePath], bytes | None], name: str
    ) -> tuple[PurePath, dict[str, Any]] | None:
        """Locate and parse the configuration of another revision.

        Discovery is the same as `load_raw`'s, behind a file `--config`
        named, so a branch pointing at a new file still meets the base's own.
        """
        path = PurePath(name)
        known = name in {TINGLE_FILE, PYPROJECT_FILE}
        if not known and (data := read(path)) is not None:
            return path, _parsed(data, name)
        return _discovered(read, labelled=PurePath())

    def differs_only_in_config(
        self, path: PurePath, *, before: bytes | None, after: bytes | None
    ) -> bool:
        """Whether a config file's two copies differ in tingle's config alone.

        A pyproject.toml holds everything else too, so its other tables are
        compared; any other config file is tingle's entirely.
        """
        if path.name != PYPROJECT_FILE:
            return True
        try:
            return _beside_config(before) == _beside_config(after)
        except ConfigError:
            return False

    def edit_target(self, root: Path) -> Path:
        """Return the config file `tingle add` should edit.

        tingle.toml wins; pyproject.toml only when it already carries a
        [tool.tingle] table; otherwise a fresh tingle.toml (to be created).
        """
        tingle = root / TINGLE_FILE
        if tingle.is_file():
            return tingle
        pyproject = root / PYPROJECT_FILE
        if pyproject.is_file() and _tool_tingle(pyproject) is not None:
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

    def write_starter(self, root: Path, bases: Sequence[str]) -> Path:
        """Create a starter tingle.toml of a metric per base; refuse to overwrite."""
        metrics = "\n\n".join(self.render_metric({"base": base}) for base in bases)
        return self._create_starter(root, STARTER_DETECTED + metrics)

    def write_examples(self, root: Path) -> Path:
        """Create the commented generic tingle.toml; refuse to overwrite."""
        return self._create_starter(root, STARTER_EXAMPLES)

    def _create_starter(self, root: Path, body: str) -> Path:
        """Write a starter tingle.toml unless config already exists.

        A [tool.tingle] table counts as existing config: a tingle.toml beside
        it would win and silently shadow it.
        """
        if (target := self.edit_target(root)).exists():
            raise ConfigError([f"{target} already holds the tingle config"])
        target.write_text(f"{STARTER_HEAD}{body.rstrip()}\n", encoding="utf-8")
        return target


def _discovered(
    read: Callable[[PurePath], bytes | None], *, labelled: PurePath
) -> tuple[PurePath, dict[str, Any]] | None:
    """Find the configuration through `read`; None if absent.

    `tingle.toml` wins over `[tool.tingle]` in `pyproject.toml`. Errors name
    each file under `labelled`.
    """
    if (data := read(PurePath(TINGLE_FILE))) is not None:
        return PurePath(TINGLE_FILE), _parsed(data, labelled / TINGLE_FILE)
    path = PurePath(PYPROJECT_FILE)
    if (data := read(path)) is None:
        return None
    label = labelled / path
    section = _section(_parsed(data, label), label)
    return None if section is None else (path, section)


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


def _tool_tingle(pyproject: Path) -> dict[str, Any] | None:
    """Return the [tool.tingle] table of a pyproject.toml, None if it has none."""
    return _section(_parsed(pyproject.read_bytes(), pyproject), pyproject)


def _section(parsed: dict[str, Any], label: object) -> dict[str, Any] | None:
    section = parsed.get("tool", {}).get("tingle")
    if section is None or isinstance(section, dict):
        return section
    raise ConfigError([f"{label}: [tool.tingle] must be a table"])


def _beside_config(data: bytes | None) -> dict[str, Any]:
    """Parse a pyproject.toml into everything but tingle's own table."""
    parsed = _parsed(data or b"", PYPROJECT_FILE)
    parsed.get("tool", {}).pop("tingle", None)
    return parsed


def _parsed(data: bytes, label: object) -> dict[str, Any]:
    try:
        return tomllib.load(io.BytesIO(data))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError([f"{label}: invalid TOML: {exc}"]) from exc
