from pathlib import Path

from tingle.inits.wiring import METRIC_TYPES, project_files
from tingle.links.fs.local import LocalProjectFiles

EXPECTED_TYPES = {
    "regex_count",
    "symbol_uses",
    "toml_list_length",
    "ini_list_length",
    "file_count",
    "line_count",
}


def test_all_metric_types_are_wired() -> None:
    assert set(METRIC_TYPES) == EXPECTED_TYPES


def test_names_match_keys() -> None:
    for key, metric_type in METRIC_TYPES.items():
        assert metric_type.name == key
        assert metric_type.description


def test_param_specs() -> None:
    assert METRIC_TYPES["regex_count"].required_params == ("pattern",)
    assert METRIC_TYPES["regex_count"].primary_param == "pattern"
    assert METRIC_TYPES["symbol_uses"].required_params == ("symbol",)
    assert METRIC_TYPES["symbol_uses"].primary_param == "symbol"
    assert METRIC_TYPES["toml_list_length"].required_params == ("key",)
    assert METRIC_TYPES["toml_list_length"].optional_params == ("file",)
    assert METRIC_TYPES["ini_list_length"].required_params == (
        "file",
        "section",
        "option",
    )
    assert METRIC_TYPES["ini_list_length"].primary_param is None
    assert METRIC_TYPES["file_count"].required_params == ()
    assert METRIC_TYPES["line_count"].required_params == ()


def test_project_files_returns_local_adapter(tmp_path: Path) -> None:
    assert isinstance(project_files(tmp_path), LocalProjectFiles)
