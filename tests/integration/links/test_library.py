"""The Python-import adapter, against real modules on the real path."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tingle.links.library.python import PythonTemplateLoader
from tingle.pacts.config import (
    BUILTIN_TEMPLATE_PACKAGE,
    MetricTemplate,
    TemplateNotFoundError,
)

if TYPE_CHECKING:
    from pathlib import Path
    from types import ModuleType


def test_a_module_level_template_is_loaded_by_its_path(pack: str) -> None:
    loaded = PythonTemplateLoader().load(f"{pack}.tools.noqa")

    assert isinstance(loaded, MetricTemplate)
    assert loaded.name == "noqa"


def test_a_template_inside_a_namespace_is_reached_the_same_way(pack: str) -> None:
    """The path does not say whether the last step crossed a module."""
    loaded = PythonTemplateLoader().load(f"{pack}.tools.grouped.inner")

    assert isinstance(loaded, MetricTemplate)
    assert loaded.name == "inner"


def test_a_missing_attribute_names_the_module_it_looked_in(pack: str) -> None:
    with pytest.raises(TemplateNotFoundError) as caught:
        PythonTemplateLoader().load(f"{pack}.tools.nope")

    assert caught.value.args[0] == f"no attribute 'nope' in '{pack}.tools'"


def test_the_longest_importable_prefix_is_tried_first() -> None:
    """`pack.tools.noqa` asks for the module before it asks for the name."""
    asked: list[str] = []

    def importer(name: str) -> ModuleType:
        asked.append(name)
        raise ModuleNotFoundError(name=name)

    with pytest.raises(TemplateNotFoundError):
        PythonTemplateLoader(importer=importer).load("pack.tools.noqa")

    assert asked == ["pack.tools.noqa", "pack.tools", "pack"]


def test_a_missing_package_is_not_a_missing_attribute() -> None:
    with pytest.raises(TemplateNotFoundError) as caught:
        PythonTemplateLoader().load("no_such_pack.thing")

    assert "no importable module" in caught.value.args[0]


def test_a_broken_package_raises_rather_than_reading_as_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A typo and a package that cannot import are different problems."""
    package = tmp_path / "broken_pack"
    package.mkdir()
    (package / "__init__.py").write_text("import nonexistent_dep", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    with pytest.raises(ModuleNotFoundError):
        PythonTemplateLoader().load("broken_pack.thing")


def test_the_catalogue_finds_templates_at_both_levels(pack: str) -> None:
    found = PythonTemplateLoader().catalogue(pack)

    assert sorted(found) == [f"{pack}.tools.grouped.inner", f"{pack}.tools.noqa"]


def test_the_catalogue_skips_private_names_and_other_objects(pack: str) -> None:
    found = PythonTemplateLoader().catalogue(pack)

    assert not [path for path in found if "private" in path or "NOT_A" in path]


def test_the_builtins_are_reachable_as_a_pack_like_any_other() -> None:
    """Nothing imports them statically, so this is what proves they load."""
    found = PythonTemplateLoader().catalogue(BUILTIN_TEMPLATE_PACKAGE)

    assert f"{BUILTIN_TEMPLATE_PACKAGE}.ruff.noqa_comment" in found
    assert all(isinstance(template, MetricTemplate) for template in found.values())
