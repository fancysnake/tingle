from __future__ import annotations

from pathlib import PurePath
from typing import TYPE_CHECKING

import pytest

from tingle.links.config_file.toml import TomlConfigStore
from tingle.pacts.config import ConfigError, ConfigNotFoundError

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

load_raw = TomlConfigStore().load_raw


def test_reads_tingle_toml(tmp_path: Path) -> None:
    (tmp_path / "tingle.toml").write_text('[[metrics]]\nname = "x"\n')

    source, raw = load_raw(tmp_path)

    assert source == tmp_path / "tingle.toml"
    assert raw == {"metrics": [{"name": "x"}]}


def test_falls_back_to_pyproject_tool_tingle(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[[tool.tingle.metrics]]\nname = "x"\n')

    source, raw = load_raw(tmp_path)

    assert source == tmp_path / "pyproject.toml"
    assert raw == {"metrics": [{"name": "x"}]}


def test_tingle_toml_wins_over_pyproject(tmp_path: Path) -> None:
    (tmp_path / "tingle.toml").write_text('[[metrics]]\nname = "from-tingle"\n')
    (tmp_path / "pyproject.toml").write_text(
        '[[tool.tingle.metrics]]\nname = "from-pyproject"\n'
    )

    source, raw = load_raw(tmp_path)

    assert source == tmp_path / "tingle.toml"
    assert raw["metrics"][0]["name"] == "from-tingle"


def test_pyproject_without_tool_tingle_is_not_found(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "other"\n')

    with pytest.raises(ConfigNotFoundError):
        load_raw(tmp_path)


def test_missing_config_raises_not_found(tmp_path: Path) -> None:
    with pytest.raises(ConfigNotFoundError):
        load_raw(tmp_path)


def test_malformed_toml_raises_config_error(tmp_path: Path) -> None:
    (tmp_path / "tingle.toml").write_text("[[metrics\n")

    with pytest.raises(ConfigError) as excinfo:
        load_raw(tmp_path)

    assert "invalid TOML" in str(excinfo.value)


def test_tool_tingle_must_be_a_table(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool]\ntingle = 5\n")

    with pytest.raises(ConfigError) as excinfo:
        load_raw(tmp_path)

    assert "[tool.tingle] must be a table" in str(excinfo.value)


def test_override_path_is_used(tmp_path: Path) -> None:
    (tmp_path / "tingle.toml").write_text('[[metrics]]\nname = "ignored"\n')
    custom = tmp_path / "custom.toml"
    custom.write_text('[[metrics]]\nname = "from-custom"\n')

    source, raw = load_raw(tmp_path, override=custom)

    assert source == custom
    assert raw["metrics"][0]["name"] == "from-custom"


def test_missing_override_raises_not_found(tmp_path: Path) -> None:
    with pytest.raises(ConfigNotFoundError):
        load_raw(tmp_path, override=tmp_path / "nope.toml")


def _reader(files: dict[str, bytes]) -> Callable[[PurePath], bytes | None]:
    return lambda path: files.get(str(path))


def test_load_at_prefers_tingle_toml_over_pyproject() -> None:
    read = _reader(
        {
            "tingle.toml": b'[diff]\nbase = "a"\n',
            "pyproject.toml": b'[tool.tingle.diff]\nbase = "b"\n',
        }
    )

    found = TomlConfigStore().load_at(read, "pyproject.toml")

    assert found == (PurePath("tingle.toml"), {"diff": {"base": "a"}})


def test_load_at_reads_the_pyproject_section() -> None:
    read = _reader({"pyproject.toml": b'[tool.tingle.diff]\nbase = "b"\n'})

    found = TomlConfigStore().load_at(read, "tingle.toml")

    assert found == (PurePath("pyproject.toml"), {"diff": {"base": "b"}})


def test_load_at_tries_a_named_file_first_then_discovery() -> None:
    both = _reader({"lax.toml": b"", "tingle.toml": b"[diff]\n"})
    discovered = _reader({"tingle.toml": b"[diff]\n"})

    store = TomlConfigStore()

    assert store.load_at(both, "lax.toml") == (PurePath("lax.toml"), {})
    assert store.load_at(discovered, "lax.toml") == (
        PurePath("tingle.toml"),
        {"diff": {}},
    )


def test_load_at_finds_nothing() -> None:
    read = _reader({"pyproject.toml": b"[tool.other]\n"})

    assert TomlConfigStore().load_at(read, "tingle.toml") is None
    assert TomlConfigStore().load_at(_reader({}), "tingle.toml") is None


def test_load_at_reports_a_file_it_cannot_parse() -> None:
    with pytest.raises(ConfigError, match=r"tingle\.toml: invalid TOML"):
        TomlConfigStore().load_at(_reader({"tingle.toml": b"= nope"}), "tingle.toml")


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    (
        (b"[tool.tingle]\nx = 1\n[tool.a]\ny = 1\n", b"[tool.a]\ny = 1\n", True),
        (b"[tool.a]\ny = 1\n", b"[tool.a]\ny = 2\n", False),
        (b"[tool.a]\ny = 1\n", b"= nope", False),
    ),
)
def test_pyproject_is_compared_beside_tingle_own_table(
    *, before: bytes, after: bytes, expected: bool
) -> None:
    path = PurePath("pyproject.toml")

    assert (
        TomlConfigStore().differs_only_in_config(path, before=before, after=after)
        is expected
    )


def test_any_other_config_file_is_tingle_own() -> None:
    path = PurePath("tingle.toml")

    assert TomlConfigStore().differs_only_in_config(path, before=b"a", after=None)
