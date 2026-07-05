from pathlib import Path

import pytest

from tingle.links.config_file.toml import load_raw
from tingle.pacts.config import ConfigError, ConfigNotFoundError


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
