"""The bundled pack, held to what any other pack is held to.

Nothing imports `tingle.builtins` statically, so these are the tests that
say it loads at all -- and they go through the same loader and the same
verifier a third-party package does, since the whole point of the pack is
that it is not a special case.
"""

from __future__ import annotations

from pathlib import Path, PurePath
from typing import TYPE_CHECKING

import pytest

from tingle.links.library.python import PythonTemplateLoader
from tingle.mills.config import validate
from tingle.mills.metrics.registry import METRIC_TYPES
from tingle.mills.templates import resolve
from tingle.pacts.config import BUILTIN_TEMPLATE_PACKAGE, ConfigError, MetricTemplate
from tingle.pacts.metrics import MetricContext

if TYPE_CHECKING:
    from tingle.pacts.metrics import MetricResult

PATHS = sorted(PythonTemplateLoader().catalogue(BUILTIN_TEMPLATE_PACKAGE))
FIXTURES = Path(__file__).parent / "fixtures"


def _measure(path: str, source: str, *, filename: str = "test_it.py") -> MetricResult:
    """Run one bundled template over one source, as a real run would."""
    template = PythonTemplateLoader().load(f"{BUILTIN_TEMPLATE_PACKAGE}.{path}")
    assert isinstance(template, MetricTemplate)
    assert template.type is not None

    return METRIC_TYPES[template.type].func(
        MetricContext(
            files=(PurePath(filename),),
            read=lambda _: source,
            exists=lambda _: True,
            params=template.params,
        )
    )


def test_the_pack_is_not_empty() -> None:
    assert len(PATHS) > 10


@pytest.mark.parametrize("path", PATHS)
def test_every_template_makes_a_valid_metric_on_its_own(
    path: str, tmp_path: Path
) -> None:
    """A bundled template must need nothing but a range to be usable.

    A missing required param would only surface for whoever first named
    the template, which is too late for something shipped.
    """
    raw = {
        "ranges": {"python": {"include": ["**/*.py"], "default": True}},
        "metrics": [{"base": path}],
    }
    errors: list[str] = []
    templates = resolve(
        raw, PythonTemplateLoader(), metric_types=METRIC_TYPES, errors=errors
    )

    assert not errors
    config = validate(
        raw, METRIC_TYPES, source=tmp_path / "tingle.toml", templates=templates
    )

    assert len(config.metrics) == 1


@pytest.mark.parametrize("path", PATHS)
def test_every_template_says_what_it_is_for(path: str) -> None:
    """The library is a menu; a row with no description does not sell."""
    template = PythonTemplateLoader().load(path)

    assert getattr(template, "description", None)
    assert getattr(template, "group", None)
    assert getattr(template, "name", None)


@pytest.mark.parametrize("path", PATHS)
def test_no_template_names_a_range(path: str) -> None:
    """Range names belong to the project, so a pack cannot know one."""
    assert getattr(PythonTemplateLoader().load(path), "ranges", None) is None


def test_two_templates_may_share_a_metric_name_across_packs(tmp_path: Path) -> None:
    """Only a warning to the reader: the duplicate is caught in the config."""
    raw = {
        "ranges": {"python": {"include": ["**/*.py"], "default": True}},
        "metrics": [
            {"base": f"{BUILTIN_TEMPLATE_PACKAGE}.python.any_used"},
            {"base": f"{BUILTIN_TEMPLATE_PACKAGE}.unittest_mock.any_used"},
        ],
    }
    errors: list[str] = []
    templates = resolve(
        raw, PythonTemplateLoader(), metric_types=METRIC_TYPES, errors=errors
    )
    config = validate(
        raw, METRIC_TYPES, source=tmp_path / "tingle.toml", templates=templates
    )

    assert [spec.name for spec in config.metrics] == ["any-uses", "mock-any-uses"]


def test_a_template_used_twice_without_a_name_is_a_duplicate(tmp_path: Path) -> None:
    raw = {
        "ranges": {"python": {"include": ["**/*.py"], "default": True}},
        "metrics": [
            {"base": f"{BUILTIN_TEMPLATE_PACKAGE}.ruff.noqa_comment"},
            {"base": f"{BUILTIN_TEMPLATE_PACKAGE}.ruff.noqa_comment"},
        ],
    }
    errors: list[str] = []
    templates = resolve(
        raw, PythonTemplateLoader(), metric_types=METRIC_TYPES, errors=errors
    )

    with pytest.raises(ConfigError) as caught:
        validate(
            raw, METRIC_TYPES, source=tmp_path / "tingle.toml", templates=templates
        )

    assert caught.value.errors == [
        (
            'metric "noqa-comment" (base "tingle.builtins.ruff.noqa_comment"):'
            " duplicate name"
        )
    ]


#: The keys the TOML-reading templates point at, as the tools write them.
REAL_CONFIG = """
[tool.ruff.format]
exclude = ["generated/*.py", "vendor/*.py"]

[[tool.importlinter.contracts]]
name = "layers"
ignore_imports = ["a -> b", "c -> d"]

[[tool.importlinter.contracts]]
name = "clean"
"""


@pytest.mark.parametrize(
    ("path", "expected"),
    (
        pytest.param("ruff.format_excludes", 2, id="ruff-format-excludes"),
        pytest.param("import_linter.ignored_imports", 2, id="import-linter-ignores"),
    ),
)
def test_a_toml_template_points_at_the_key_the_tool_actually_writes(
    path: str, expected: int
) -> None:
    """A key no tool writes reads as 0 with a warning, for every project."""
    result = _measure(path, REAL_CONFIG, filename="pyproject.toml")

    assert not result.warnings
    assert result.value == expected


#: Every suppression form ruff documents, plus the ones its neighbours do,
#: read from a `.txt` so the project does not measure its own test data.
SUPPRESSIONS = (FIXTURES / "suppressions.py.txt").read_text()


@pytest.mark.parametrize(
    ("path", "expected"),
    (
        pytest.param("ruff.noqa_comment", 2, id="noqa-comment"),
        pytest.param("ruff.ignore_comment", 1, id="ruff-ignore-comment"),
        pytest.param("ruff.suppressed_ranges", 1, id="ruff-suppressed-ranges"),
        pytest.param("ruff.file_exemptions", 2, id="ruff-file-exemptions"),
        pytest.param("coverage.pragma_comment", 1, id="pragma-comment"),
        pytest.param("pytest.skip_marks", 1, id="pytest-skip"),
        pytest.param("pytest.xfail_marks", 1, id="pytest-xfail"),
        pytest.param("python.todo_comments", 2, id="todo-comments"),
        pytest.param("python.cast_used", 2, id="cast-uses"),
    ),
)
def test_a_source_template_matches_the_suppression_it_names(
    path: str, expected: int
) -> None:
    """The pattern is the whole template, so a typo in it is the bug.

    One shared fixture on purpose: the counts only hold if each pattern
    leaves its neighbours' comments alone, which per-case sources cannot say.
    """
    result = _measure(path, SUPPRESSIONS)

    assert not result.warnings
    assert result.value == expected


#: mypy's strictness settings as a project writes them off, in each of the
#: spellings a config file is allowed -- only TOML has a formatter settling
#: its spacing, and `False` is how mypy.ini and setup.cfg write it.
@pytest.mark.parametrize(
    ("source", "filename", "expected"),
    (
        pytest.param(
            "[tool.mypy]\n"
            "disallow_untyped_defs = false\n"
            "disallow_any_generics = false\n"
            "warn_unused_ignores = true\n",
            "pyproject.toml",
            2,
            id="toml",
        ),
        pytest.param(
            "[mypy]\ndisallow_untyped_defs = False\n",
            "mypy.ini",
            1,
            id="ini-capitalised",
        ),
        pytest.param(
            "[tool.mypy]\ndisallow_untyped_defs=false\n",
            "pyproject.toml",
            1,
            id="unspaced",
        ),
        pytest.param(
            "[tool.mypy]\n# disallow_untyped_defs = false\n",
            "pyproject.toml",
            0,
            id="commented-out",
        ),
    ),
)
def test_the_mypy_strictness_template_counts_only_the_holes(
    source: str, filename: str, *, expected: int
) -> None:
    result = _measure("mypy.strictness_holes", source, filename=filename)

    assert not result.warnings
    assert result.value == expected
