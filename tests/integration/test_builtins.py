"""The bundled pack, held to what any other pack is held to.

Nothing imports `tingle.builtins` statically, so these are the tests that
say it loads at all -- and they go through the same loader and the same
verifier a third-party package does, since the whole point of the pack is
that it is not a special case.
"""

from __future__ import annotations

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
