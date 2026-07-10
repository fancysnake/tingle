from __future__ import annotations

from pathlib import PurePath
from typing import TYPE_CHECKING

from tingle.mills.metrics.symbol_uses import symbol_uses, validate_params
from tingle.pacts.metrics import MetricContext, MetricResult

if TYPE_CHECKING:
    from collections.abc import Mapping

SYMBOL = "myapp.legacy.OldClient"


def _run(code: str, symbol: str = SYMBOL) -> MetricResult:
    return _run_files({"main.py": code}, symbol)


def _run_files(
    contents: Mapping[str, str | None], symbol: str = SYMBOL
) -> MetricResult:
    return symbol_uses(
        MetricContext(
            files=tuple(PurePath(name) for name in contents),
            read=lambda path: contents.get(str(path)),
            exists=lambda path: str(path) in contents,
            params={"symbol": symbol},
        )
    )


def test_plain_import_and_attribute_chain() -> None:
    code = "import myapp.legacy\n\nclient = myapp.legacy.OldClient()\n"

    assert _run(code).value == 1


def test_aliased_module_import() -> None:
    code = "import myapp.legacy as leg\n\nclient = leg.OldClient()\n"

    assert _run(code).value == 1


def test_from_import_counts_import_and_uses() -> None:
    code = "from myapp.legacy import OldClient\n\nclient = OldClient()\n"

    assert _run(code).value == 2


def test_from_import_with_alias() -> None:
    code = "from myapp.legacy import OldClient as OC\n\nclient = OC()\nother = OC\n"

    assert _run(code).value == 3


def test_from_import_of_module() -> None:
    code = "from myapp import legacy\n\nclient = legacy.OldClient()\n"

    assert _run(code).value == 1


def test_trailing_attributes_still_count_once() -> None:
    code = "import myapp.legacy\n\nx = myapp.legacy.OldClient.create().value\n"

    assert _run(code).value == 1


def test_relative_import() -> None:
    code = "from .legacy import OldClient\n\nclient = OldClient()\n"

    assert _run(code).value == 2


def test_unrelated_code_counts_zero() -> None:
    code = "from other import NewClient\n\nclient = NewClient()\n"

    result = _run(code)

    assert result.value == 0
    assert dict(result.details) == {}


def test_same_bare_name_without_import_counts_zero_in_dotted_mode() -> None:
    code = "class OldClient:\n    pass\n\nx = OldClient()\n"

    assert _run(code).value == 0


def test_bare_mode_counts_names_and_attributes() -> None:
    code = "x = OldClient()\ny = registry.OldClient\n"

    assert _run(code, symbol="OldClient").value == 2


def test_bare_mode_counts_imports() -> None:
    code = "from somewhere import OldClient\n\nx = OldClient()\n"

    assert _run(code, symbol="OldClient").value == 2


def test_star_import_falls_back_to_bare_counting() -> None:
    code = "from myapp.legacy import *\n\nclient = OldClient()\n"

    result = _run(code)

    assert result.value == 1
    assert "star import" in result.warnings[0]


def test_syntax_error_skips_file_with_warning() -> None:
    result = _run_files({"bad.py": "def broken(:\n", "ok.py": ""})

    assert result.value == 0
    assert "syntax error" in result.warnings[0]


def test_non_python_files_are_ignored() -> None:
    result = _run_files({"notes.md": "myapp.legacy.OldClient everywhere"})

    assert result.value == 0
    assert result.warnings == ()


def test_details_are_per_file() -> None:
    result = _run_files(
        {"a.py": "from myapp.legacy import OldClient\nOldClient()\n", "b.py": "x = 1\n"}
    )

    assert dict(result.details) == {"a.py": 2}
    assert [str(o) for o in result.occurrences] == ["a.py:1", "a.py:2"]


def test_validate_params() -> None:
    assert validate_params({"symbol": "pkg.mod.OldClient"}) == []
    assert validate_params({"symbol": "OldClient"}) == []
    assert validate_params({"symbol": ""}) != []
    assert validate_params({"symbol": "not a name"}) != []
    assert validate_params({"symbol": 5}) != []
