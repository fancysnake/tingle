from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING

import pytest

from tingle.links.config_file.toml import TomlConfigStore

if TYPE_CHECKING:
    from pathlib import Path

_store = TomlConfigStore()
append_metric = _store.append_metric
render_metric = _store.render_metric
edit_target = _store.edit_target
write_starter = _store.write_starter

# Deliberately not the config the CLI tests use: this suite only cares that
# whatever was already in the file survives being appended to.
EXISTING = """# my metrics
[ranges.sources]
include = ["src/**/*.py"]  # only sources

[[metrics]]
name = "todo-comments"
type = "regex_count"
range = "sources"
pattern = '#\\s*TODO'
"""


def test_append_preserves_existing_text(tmp_path: Path) -> None:
    config = tmp_path / "tingle.toml"
    config.write_text(EXISTING)

    append_metric(config, {"name": "files", "type": "file_count"})

    text = config.read_text()
    assert text.startswith(EXISTING.rstrip("\n"))
    assert "# my metrics" in text
    assert "# only sources" in text
    assert 'name = "files"' in text
    assert 'type = "file_count"' in text


def test_append_to_pyproject_tool_tingle(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "demo"\n\n[tool.tingle]\n'
        '[tool.tingle.ranges.python]\ninclude = ["**/*.py"]\n'
    )

    append_metric(pyproject, {"name": "files", "type": "file_count"})

    text = pyproject.read_text()
    assert "[[tool.tingle.metrics]]" in text
    assert '[project]\nname = "demo"' in text


def test_append_creates_missing_tingle_toml(tmp_path: Path) -> None:
    config = tmp_path / "tingle.toml"

    append_metric(config, {"name": "files", "type": "file_count"})

    assert 'name = "files"' in config.read_text()


def test_append_metric_with_ranges_list(tmp_path: Path) -> None:
    config = tmp_path / "tingle.toml"

    append_metric(
        config,
        {"name": "todo", "type": "regex_count", "ranges": ["a", "b"], "pattern": "x"},
    )

    text = config.read_text()
    assert 'ranges = ["a", "b"]' in text


def test_edit_target_prefers_tingle_toml(tmp_path: Path) -> None:
    (tmp_path / "tingle.toml").write_text("")
    (tmp_path / "pyproject.toml").write_text("[tool.tingle]\n")

    assert edit_target(tmp_path) == tmp_path / "tingle.toml"


def test_edit_target_uses_pyproject_with_tool_tingle(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.tingle]\n")

    assert edit_target(tmp_path) == tmp_path / "pyproject.toml"


def test_edit_target_defaults_to_new_tingle_toml(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')

    assert edit_target(tmp_path) == tmp_path / "tingle.toml"


def test_write_starter_creates_and_refuses_overwrite(tmp_path: Path) -> None:
    path = write_starter(tmp_path)

    assert path == tmp_path / "tingle.toml"
    assert "[ranges.python]" in path.read_text()

    with pytest.raises(FileExistsError):
        write_starter(tmp_path)


def test_render_metric_writes_the_entry_without_a_file_to_put_it_in() -> None:
    """`library --expand` needs the same TOML, minus anywhere to write it."""
    rendered = render_metric({"name": "files", "type": "file_count", "guide": 200})

    assert rendered == '[[metrics]]\nname = "files"\ntype = "file_count"\nguide = 200'


def test_a_regex_keeps_the_quoting_that_leaves_it_readable() -> None:
    """A basic string doubles every backslash; a literal one shows the pattern."""
    rendered = render_metric({"pattern": r"#\s*noqa"})

    assert rendered == "[[metrics]]\npattern = '#\\s*noqa'"


@pytest.mark.parametrize(
    "pattern",
    (
        pytest.param("it\\'s", id="a quote a literal string cannot hold"),
        pytest.param("a\\b\nc", id="a newline a literal string cannot hold"),
    ),
)
def test_what_a_literal_string_cannot_hold_falls_back_to_a_basic_one(
    pattern: str,
) -> None:
    rendered = render_metric({"pattern": pattern})

    assert tomllib.loads(rendered)["metrics"][0]["pattern"] == pattern
