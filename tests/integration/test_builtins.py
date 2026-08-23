"""The bundled pack, held to what any other pack is held to.

Nothing imports `tingle.builtins` statically, so these are the tests that
say it loads at all -- and they go through the same loader and the same
verifier a third-party package does, since the whole point of the pack is
that it is not a special case.
"""

from __future__ import annotations

from pathlib import PurePath
from typing import TYPE_CHECKING

import pytest

from tingle.links.library.python import PythonTemplateLoader
from tingle.mills.config import validate
from tingle.mills.metrics.registry import METRIC_TYPES
from tingle.mills.templates import resolve
from tingle.pacts.config import BUILTIN_TEMPLATE_PACKAGE, ConfigError, MetricTemplate
from tingle.pacts.metrics import MetricContext

if TYPE_CHECKING:
    from pathlib import Path

PATHS = sorted(PythonTemplateLoader().catalogue(BUILTIN_TEMPLATE_PACKAGE))


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
    template = PythonTemplateLoader().load(f"{BUILTIN_TEMPLATE_PACKAGE}.{path}")
    assert isinstance(template, MetricTemplate)
    assert template.type is not None
    metric_type = METRIC_TYPES[template.type]

    result = metric_type.func(
        MetricContext(
            files=(),
            read=lambda _: REAL_CONFIG,
            exists=lambda _: True,
            params=template.params,
        )
    )

    assert not result.warnings
    assert result.value == expected


#: Every suppression form ruff documents, plus the ones its neighbours do.
#: Each template must pick out its own and leave the rest to the others,
#: since they all open with a hash and three of them name ruff after it.
REAL_SOURCE = """\
# ruff: noqa: E501
# ruff: file-ignore[F401]
from typing import Any, cast

import pytest

# ruff: disable[E741]
l = 1
# ruff: enable[E741]


@pytest.mark.skip(reason="broken")
@pytest.mark.xfail
def test_it(value: object) -> Any:  # pragma: no cover
    # TODO: narrow this
    # HACK: until the API settles
    # ruff: ignore[ARG001]
    x = 1  # noqa: F841  # sample
    y = 2  # noqa  # sample
    return cast(int, value)
"""


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
        pytest.param("python.object_used", 1, id="object-uses"),
    ),
)
def test_a_source_template_matches_the_suppression_it_names(
    path: str, expected: int
) -> None:
    """The pattern is the whole template, so a typo in it is the bug."""
    template = PythonTemplateLoader().load(f"{BUILTIN_TEMPLATE_PACKAGE}.{path}")
    assert isinstance(template, MetricTemplate)
    assert template.type is not None

    result = METRIC_TYPES[template.type].func(
        MetricContext(
            files=(PurePath("test_it.py"),),
            read=lambda _: REAL_SOURCE,
            exists=lambda _: True,
            params=template.params,
        )
    )

    assert not result.warnings
    assert result.value == expected


#: mypy's strictness settings as a project writes them off.
RELAXED_CONFIG = """
[tool.mypy]
disallow_untyped_defs = false
disallow_any_generics = false
warn_unused_ignores = true
"""


def test_the_mypy_strictness_template_counts_only_the_holes() -> None:
    template = PythonTemplateLoader().load(
        f"{BUILTIN_TEMPLATE_PACKAGE}.mypy.strictness_holes"
    )
    assert isinstance(template, MetricTemplate)
    assert template.type is not None

    result = METRIC_TYPES[template.type].func(
        MetricContext(
            files=(PurePath("pyproject.toml"),),
            read=lambda _: RELAXED_CONFIG,
            exists=lambda _: True,
            params=template.params,
        )
    )

    assert result.value == 2
