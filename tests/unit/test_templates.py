"""Resolving and verifying metric templates."""

from __future__ import annotations

from types import MappingProxyType, SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from tingle.mills.metrics.registry import METRIC_TYPES
from tingle.mills.templates import apply, as_table, resolve, verify
from tingle.pacts.config import MetricTemplate, TemplateNotFoundError

NOQA = MetricTemplate(
    type="regex_count",
    name="noqa-comment",
    group="linting",
    description="noqa comments.",
    params={"pattern": r"#\s*noqa", "ignore_lines": ["# legacy"]},
)


def _loader(**templates: object) -> MagicMock:
    loader = MagicMock()
    loader.load.side_effect = lambda path: (
        templates[path] if path in templates else _missing(path)
    )
    return loader


def _missing(path: str) -> object:
    message = f"no such template {path!r}"
    raise TemplateNotFoundError(message)


def _resolve(
    raw: dict[str, Any], **templates: object
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    resolved = resolve(
        raw, _loader(**templates), metric_types=METRIC_TYPES, errors=errors
    )
    return resolved, errors


def _base(template: MetricTemplate | None) -> dict[str, Any] | None:
    """Flatten a template into what `apply` merges: the table it stands for."""
    return None if template is None else as_table(template)


def _applied(template: MetricTemplate | None, table: dict[str, Any]) -> dict[str, Any]:
    return apply(_base(template), table, label="metric", errors=[])


def _errors(template: MetricTemplate | None, table: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    apply(_base(template), table, label="metric", errors=errors)
    return errors


# --- merging ---------------------------------------------------------------


def test_a_stated_key_wins_over_the_template() -> None:
    merged = _applied(NOQA, {"name": "ours", "pattern": "TODO"})

    assert merged["name"] == "ours"
    assert merged["pattern"] == "TODO"
    assert merged["group"] == "linting"


def test_a_list_param_is_replaced_not_grown() -> None:
    """The plain key is the blunt one; `extra_` exists because it is."""
    merged = _applied(NOQA, {"ignore_lines": ["# ours"]})

    assert merged["ignore_lines"] == ["# ours"]


def test_extra_appends_to_the_templates_list() -> None:
    merged = _applied(NOQA, {"extra_ignore_lines": ["# ours"]})

    assert merged["ignore_lines"] == ["# legacy", "# ours"]


def test_extra_appends_to_a_replacement_when_both_are_given() -> None:
    merged = _applied(
        NOQA, {"ignore_lines": ["# only"], "extra_ignore_lines": ["# and"]}
    )

    assert merged["ignore_lines"] == ["# only", "# and"]


def test_extra_starts_a_list_the_template_never_had() -> None:
    merged = _applied(NOQA, {"extra_flags": ["MULTILINE"]})

    assert merged["flags"] == ["MULTILINE"]


def test_extra_without_a_base_has_nothing_to_extend() -> None:
    assert _errors(None, {"extra_ignore_lines": ["x"]}) == [
        'metric: "extra_ignore_lines" has nothing to extend without a base'
    ]


def test_extra_must_be_a_list() -> None:
    assert _errors(NOQA, {"extra_ignore_lines": "x"}) == [
        'metric: "extra_ignore_lines" must be a list'
    ]


def test_extra_cannot_extend_a_scalar() -> None:
    assert _errors(NOQA, {"extra_pattern": ["x"]}) == [
        'metric: "pattern" is not a list, so "extra_pattern" cannot extend it'
    ]


def test_type_is_fixed_by_a_template_that_states_one() -> None:
    errors = _errors(NOQA, {"type": "regex_spread"})

    assert errors == ['metric: type is fixed by the template ("regex_count")']


def test_a_mixin_leaves_the_type_to_the_metric() -> None:
    mixin = MetricTemplate(params={"ignore_lines": ["# generated"]})

    merged = _applied(mixin, {"type": "symbol_uses", "symbol": "ANY"})

    assert merged["type"] == "symbol_uses"
    assert merged["ignore_lines"] == ["# generated"]


def test_stating_ranges_clears_the_templates_range() -> None:
    """One slot between them, or the two arrive together and fail as a pair."""
    ranged = MetricTemplate(type="regex_count", ranges=("python",))

    merged = _applied(ranged, {"ranges": ["js", "css"]})

    assert merged["ranges"] == ["js", "css"]
    assert "range" not in merged


def test_a_templates_params_are_not_shared_with_what_it_builds() -> None:
    merged = _applied(NOQA, {"extra_ignore_lines": ["# ours"]})
    merged["ignore_lines"].append("# later")

    assert NOQA.params["ignore_lines"] == ["# legacy"]


# --- verifying -------------------------------------------------------------


def _verified(obj: object) -> tuple[MetricTemplate | None, list[str]]:
    errors: list[str] = []
    template = verify(obj, path="pack.one", metric_types=METRIC_TYPES, errors=errors)
    return template, errors


def test_a_subclass_is_not_a_template() -> None:
    """`@final` is a claim to a type checker; the verifier is what enforces it.

    Built through `type()` rather than a `class` statement, because a
    subclass of a final class is exactly what the type checker refuses to
    read -- which is the point being made.
    """
    sneaky = type("Sneaky", (MetricTemplate,), {})

    _, errors = _verified(sneaky(type="regex_count"))

    assert errors == ['template "pack.one": expected a MetricTemplate, got Sneaky']


def test_something_else_entirely_is_not_a_template() -> None:
    _, errors = _verified({"type": "regex_count"})

    assert errors == ['template "pack.one": expected a MetricTemplate, got dict']


def test_an_unknown_type_is_caught_at_the_template() -> None:
    _, errors = _verified(MetricTemplate(type="no_such_type"))

    assert errors == ["template \"pack.one\": unknown type 'no_such_type'"]


def test_field_types_are_checked_because_annotations_are_not() -> None:
    """A package can put anything in these fields; nothing stops it at runtime."""
    wrong: dict[str, Any] = {"name": 17, "guide": 0, "ranges": ["python"]}

    _, errors = _verified(MetricTemplate(**wrong))

    assert errors == [
        'template "pack.one": name must be a non-empty string',
        'template "pack.one": guide must be a positive integer',
        'template "pack.one": ranges must be a tuple of strings',
    ]


def test_a_param_may_not_hold_a_live_object() -> None:
    _, errors = _verified(
        MetricTemplate(type="regex_count", params={"pattern": object()})
    )

    assert errors == [
        (
            'template "pack.one": param "pattern" must be a string, number,'
            " boolean, or a list of those"
        )
    ]


def test_params_are_copied_away_from_the_declaring_package() -> None:
    """A package holding the mapping could otherwise rewrite it mid-run."""
    live: dict[str, Any] = {"pattern": "x", "ignore_lines": ["a"]}
    template, _ = _verified(MetricTemplate(type="regex_count", params=live))

    assert template is not None
    live["pattern"] = "changed"
    live["ignore_lines"].append("b")

    assert template.params["pattern"] == "x"
    assert template.params["ignore_lines"] == ["a"]
    assert isinstance(template.params, MappingProxyType)


# --- resolving -------------------------------------------------------------


def test_an_imported_base_is_loaded_once_however_often_it_is_named() -> None:
    raw = {
        "metrics": [
            {"base": "pack.noqa", "name": "a"},
            {"base": "pack.noqa", "name": "b"},
        ]
    }
    errors: list[str] = []
    loader = _loader(**{"pack.noqa": NOQA})

    resolve(raw, loader, metric_types=METRIC_TYPES, errors=errors)

    assert loader.load.call_count == 1
    assert not errors


def test_a_missing_import_is_reported_under_the_path() -> None:
    _, errors = _resolve({"metrics": [{"base": "pack.nope"}]})

    assert errors == ["template \"pack.nope\": no such template 'pack.nope'"]


def test_a_local_template_may_build_on_an_imported_one() -> None:
    raw = {
        "templates": {"ours": {"base": "pack.noqa", "extra_ignore_lines": ["# ours"]}},
        "metrics": [{"base": "ours", "name": "a"}],
    }
    resolved, errors = _resolve(raw, **{"pack.noqa": NOQA})

    assert not errors
    assert resolved["ours"]["ignore_lines"] == ["# legacy", "# ours"]
    assert resolved["ours"]["type"] == "regex_count"


def test_a_local_template_may_build_on_another_declared_after_it() -> None:
    raw = {
        "templates": {
            "outer": {"base": "inner", "group": "ours"},
            "inner": {"type": "regex_count", "pattern": "x"},
        }
    }
    resolved, errors = _resolve(raw)

    assert not errors
    assert resolved["outer"]["group"] == "ours"
    assert resolved["outer"]["pattern"] == "x"


def test_a_base_cycle_is_reported_rather_than_followed() -> None:
    raw = {"templates": {"a": {"base": "b"}, "b": {"base": "a"}}}

    _, errors = _resolve(raw)

    assert errors == ['template "a": base cycle (a -> b -> a)']


def test_a_local_name_may_not_look_like_an_import_path() -> None:
    _, errors = _resolve({"templates": {"a.b": {"type": "regex_count"}}})

    assert errors == [
        (
            'template "a.b": a local name may not contain "." -- that is how an'
            " imported template is told apart from a local one"
        )
    ]


def test_a_template_in_a_subpackage_is_reached_by_the_same_path() -> None:
    """How deep a pack nests is the pack's business; the config sees a path."""
    raw = {"metrics": [{"base": "pack.group.noqa", "name": "a"}]}

    resolved, errors = _resolve(raw, **{"pack.group.noqa": NOQA})

    assert not errors
    assert resolved["pack.group.noqa"]["name"] == "noqa-comment"


def test_templates_must_be_a_table_of_tables() -> None:
    assert _resolve({"templates": []})[1] == ["[templates] must be a table"]
    assert _resolve({"templates": {"a": 1}})[1] == ['template "a": must be a table']


def test_a_local_base_must_be_a_string() -> None:
    _, errors = _resolve({"templates": {"a": {"base": 17}}})

    assert errors == ['template "a": base must be a string']


def test_a_local_template_may_not_name_a_base_that_is_not_there() -> None:
    _, errors = _resolve({"templates": {"a": {"base": "nope"}}})

    assert errors == ['template "a": unknown base "nope"']


def test_a_local_template_is_carried_through_as_the_table_it_was_written_as() -> None:
    """No round trip through a template object, so no second validator either.

    Its fields are checked where a metric uses them, by the validator that
    already owns those rules -- which is also the one that says which
    metric, and which base, a complaint is about.
    """
    resolved, errors = _resolve(
        {"templates": {"a": {"range": "python", "group": "", "guide": -1}}}
    )

    assert not errors
    assert resolved["a"] == {"range": "python", "group": "", "guide": -1}


def test_an_empty_ranges_tuple_is_a_template_insisting_on_none() -> None:
    """None means "not stated"; `()` would be a template with no ranges."""
    _, errors = _verified(MetricTemplate(type="regex_count", ranges=()))

    assert errors == ['template "pack.one": ranges must not be empty']


def test_params_must_be_a_mapping_with_string_keys() -> None:
    not_a_mapping: dict[str, Any] = {"params": ["pattern"]}
    bad_keys: dict[str, Any] = {"params": {1: "x"}}

    assert _verified(MetricTemplate(**not_a_mapping))[1] == [
        'template "pack.one": params must be a mapping'
    ]
    assert _verified(MetricTemplate(**bad_keys))[1] == [
        'template "pack.one": param names must be strings'
    ]


def test_a_namespace_is_not_itself_a_template() -> None:
    raw = {"metrics": [{"base": "pack.group", "name": "a"}]}

    _, errors = _resolve(raw, **{"pack.group": SimpleNamespace(noqa=NOQA)})

    assert errors == [
        'template "pack.group": expected a MetricTemplate, got SimpleNamespace'
    ]
