"""Resolving `base` into a template, and a template into a metric table.

Three sources feed one verifier: templates imported from a package,
templates declared as `[templates.<id>]` in the config file, and -- through
`apply` -- the metric entries that build on either. A template arriving
from someone else's package is untrusted input wearing the shape of a
Python object, so it is held to what a TOML table is held to.

What identifies a template is never what it names a metric. An imported
one is identified by its import path, a local one by its table key, and
both carry a `name` that is only the metric's default.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from tingle.pacts.config import MetricTemplate, TemplateNotFoundError
from tingle.specs.config import METRIC_NAME_RE

if TYPE_CHECKING:
    from collections.abc import Iterable

    from tingle.pacts.config import TemplateLoader
    from tingle.pacts.metrics import MetricType

#: Marks a list param as extending the template's rather than replacing it.
EXTRA_PREFIX = "extra_"

_RANGE_KEYS = frozenset({"range", "ranges"})
#: The keys a template states directly; everything else it holds is a param.
_TEMPLATE_KEYS = (
    frozenset({"type", "name", "group", "description", "guide", "base"}) | _RANGE_KEYS
)

#: What a param may hold, so a template cannot smuggle a live object into
#: what is meant to be config. Lists are checked element by element.
_SCALARS = (str, int, float, bool)


def resolve(
    raw: Mapping[str, Any],
    loader: TemplateLoader,
    *,
    metric_types: Mapping[str, MetricType],
    errors: list[str],
) -> dict[str, MetricTemplate]:
    """Every template the config reaches for, by the name it reaches with.

    Imported templates are loaded first and locals resolved against them,
    so a local template may build on a packaged one. Locals may build on
    each other too; a cycle is reported rather than followed.
    """
    tables = _local_tables(raw, errors)
    imported = _imported(
        raw, tables, loader=loader, metric_types=metric_types, errors=errors
    )
    return _locals(tables, imported, metric_types=metric_types, errors=errors)


def apply(
    template: MetricTemplate | None,
    table: Mapping[str, Any],
    *,
    label: str,
    errors: list[str],
) -> dict[str, Any]:
    """Lay a table's own keys over a template's, returning the effective table.

    Every key the table states wins outright -- there is no deep merge, so
    a list replaces rather than grows. `extra_<key>` is the other choice:
    it appends to whatever `<key>` came to, template or table.

    `range` and `ranges` are one slot between them. A table naming either
    drops both from the template, or a template's `range` and an entry's
    `ranges` would arrive together and fail as if the reader had written
    both.
    """
    result = _as_table(template)
    stated = {key: value for key, value in table.items() if not _is_extra(key)}
    extras = {
        key.removeprefix(EXTRA_PREFIX): value
        for key, value in table.items()
        if _is_extra(key)
    }

    if template is not None and template.type is not None and "type" in stated:
        errors.append(f'{label}: type is fixed by the template ("{template.type}")')
        del stated["type"]
    if _RANGE_KEYS & set(stated):
        for key in _RANGE_KEYS:
            result.pop(key, None)

    result.update(stated)
    if template is None:
        errors.extend(
            f'{label}: "{EXTRA_PREFIX}{key}" has nothing to extend without a base'
            for key in extras
        )
        return result
    for key, added in extras.items():
        _extend(result, key, added=added, label=label, errors=errors)
    return result


def verify(
    obj: object, *, path: str, metric_types: Mapping[str, MetricType], errors: list[str]
) -> MetricTemplate | None:
    """Check a loaded object really is a template, and hand back a safe copy.

    The type test is exact rather than `isinstance`: `MetricTemplate` is
    final, and a subclass could carry state that vanishes silently in the
    merge. Annotations enforce nothing at runtime, so every field is
    checked, and params are copied -- `frozen` stops nobody rewriting the
    mapping the declaring package still holds a reference to.
    """
    label = f'template "{path}"'
    if obj.__class__ is not MetricTemplate:
        errors.append(f"{label}: expected a MetricTemplate, got {type(obj).__name__}")
        return None

    found = len(errors)
    for key, value in (
        ("type", obj.type),
        ("group", obj.group),
        ("description", obj.description),
    ):
        _check_optional_str(value, key=key, label=label, errors=errors)
    _check_name(obj.name, label=label, errors=errors)
    _check_guide(obj.guide, label=label, errors=errors)
    _check_ranges(obj.ranges, label=label, errors=errors)
    _check_params(obj.params, label=label, errors=errors)
    _check_type_name(obj.type, metric_types, label=label, errors=errors)
    if len(errors) > found:
        return None
    return replace(obj, params=_frozen_params(obj.params))


def _is_extra(key: str) -> bool:
    return key.startswith(EXTRA_PREFIX) and len(key) > len(EXTRA_PREFIX)


def _as_table(template: MetricTemplate | None) -> dict[str, Any]:
    """Flatten a template back into the table shape a metric entry has."""
    if template is None:
        return {}
    table: dict[str, Any] = {
        key: value
        for key, value in (
            ("type", template.type),
            ("name", template.name),
            ("group", template.group),
            ("description", template.description),
            ("guide", template.guide),
        )
        if value is not None
    }
    if template.ranges is not None:
        table["ranges"] = list(template.ranges)
    table.update({key: _copied(value) for key, value in template.params.items()})
    return table


def _extend(
    result: dict[str, Any], key: str, *, added: object, label: str, errors: list[str]
) -> None:
    name = f"{EXTRA_PREFIX}{key}"
    if not isinstance(added, list):
        errors.append(f'{label}: "{name}" must be a list')
        return
    current = result.get(key, [])
    if not isinstance(current, list):
        errors.append(f'{label}: "{key}" is not a list, so "{name}" cannot extend it')
        return
    result[key] = [*current, *added]


def _local_tables(
    raw: Mapping[str, Any], errors: list[str]
) -> dict[str, Mapping[str, Any]]:
    """Validate the shape of `[templates]` and key the entries by their id."""
    listed = raw.get("templates", {})
    if not isinstance(listed, Mapping):
        errors.append("[templates] must be a table")
        return {}

    tables: dict[str, Mapping[str, Any]] = {}
    for name, table in listed.items():
        label = f'template "{name}"'
        if not isinstance(table, Mapping):
            errors.append(f"{label}: must be a table")
            continue
        if "." in name:
            errors.append(
                f'{label}: a local name may not contain "." -- that is how an'
                " imported template is told apart from a local one"
            )
            continue
        tables[name] = table
    return tables


def _imported(
    raw: Mapping[str, Any],
    tables: Mapping[str, Mapping[str, Any]],
    *,
    loader: TemplateLoader,
    metric_types: Mapping[str, MetricType],
    errors: list[str],
) -> dict[str, MetricTemplate]:
    """Load every dotted base the config mentions, verifying each.

    Only the config's own `base` keys are followed. A packaged template
    carries no base of its own -- Python composes with `replace()` -- so
    one pass over what is written down reaches everything.
    """
    metrics = raw.get("metrics", [])
    paths = sorted(
        {
            base
            for source in (
                metrics if isinstance(metrics, list) else [],
                tables.values(),
            )
            for base in _bases(source)
            if "." in base
        }
    )
    loaded: dict[str, MetricTemplate] = {}
    for path in paths:
        try:
            obj = loader.load(path)
        except TemplateNotFoundError as exc:
            errors.append(f'template "{path}": {exc.args[0]}')
            continue
        template = verify(obj, path=path, metric_types=metric_types, errors=errors)
        if template is not None:
            loaded[path] = template
    return loaded


def _bases(source: Iterable[Any]) -> list[str]:
    return [
        table["base"]
        for table in source
        if isinstance(table, Mapping) and isinstance(table.get("base"), str)
    ]


@dataclass
class _Resolution:
    """The half-built map of local templates, and what is in flight.

    A local template may name another as its base, so resolving one can
    resolve several. `building` is the chain currently open, which is what
    catches a template that reaches, however far round, back to itself.
    """

    tables: Mapping[str, Mapping[str, Any]]
    metric_types: Mapping[str, MetricType]
    errors: list[str]
    resolved: dict[str, MetricTemplate]
    done: set[str] = field(default_factory=set)
    building: list[str] = field(default_factory=list)


def _locals(
    tables: Mapping[str, Mapping[str, Any]],
    imported: Mapping[str, MetricTemplate],
    *,
    metric_types: Mapping[str, MetricType],
    errors: list[str],
) -> dict[str, MetricTemplate]:
    """Resolve local templates, following bases between them without looping."""
    state = _Resolution(
        tables=tables, metric_types=metric_types, errors=errors, resolved=dict(imported)
    )
    for name in tables:
        _build(state, name)
    return state.resolved


def _build(state: _Resolution, name: str) -> None:
    if name in state.done:
        return
    if name in state.building:
        loop = " -> ".join([*state.building[state.building.index(name) :], name])
        state.errors.append(f'template "{name}": base cycle ({loop})')
        state.done.add(name)
        return

    state.building.append(name)
    label = f'template "{name}"'
    table = state.tables[name]
    merged = apply(
        _base_of(state, table, label=label), table, label=label, errors=state.errors
    )
    template = _from_table(
        merged, label=label, metric_types=state.metric_types, errors=state.errors
    )
    if template is not None:
        state.resolved[name] = template
    state.building.pop()
    state.done.add(name)


def _base_of(
    state: _Resolution, table: Mapping[str, Any], *, label: str
) -> MetricTemplate | None:
    if (base := table.get("base")) is None:
        return None
    if not isinstance(base, str):
        state.errors.append(f"{label}: base must be a string")
        return None
    if base not in state.resolved and base in state.tables:
        _build(state, base)
    if base in state.resolved:
        return state.resolved[base]
    # a base that exists but did not resolve -- a dotted one that failed to
    # load, a local one in a cycle -- has already been reported where it
    # broke; saying it again for everything that named it buries it.
    if "." not in base and base not in state.tables:
        state.errors.append(f'{label}: unknown base "{base}"')
    return None


def _from_table(
    table: Mapping[str, Any],
    *,
    label: str,
    metric_types: Mapping[str, MetricType],
    errors: list[str],
) -> MetricTemplate | None:
    """Turn a resolved local table into a template, verified like a loaded one."""
    ranges = _table_ranges(table, label=label, errors=errors)
    params = {key: value for key, value in table.items() if key not in _TEMPLATE_KEYS}
    found = len(errors)
    for key in ("type", "name", "group", "description"):
        _check_optional_str(table.get(key), key=key, label=label, errors=errors)
    _check_name(table.get("name"), label=label, errors=errors)
    _check_guide(table.get("guide"), label=label, errors=errors)
    _check_params(params, label=label, errors=errors)
    _check_type_name(table.get("type"), metric_types, label=label, errors=errors)
    if len(errors) > found:
        return None
    return MetricTemplate(
        type=table.get("type"),
        name=table.get("name"),
        group=table.get("group"),
        description=table.get("description"),
        guide=table.get("guide"),
        ranges=ranges,
        params=_frozen_params(params),
    )


def _table_ranges(
    table: Mapping[str, Any], *, label: str, errors: list[str]
) -> tuple[str, ...] | None:
    if "range" in table and "ranges" in table:
        errors.append(f'{label}: give either "range" or "ranges", not both')
        return None
    if "range" in table:
        single = table["range"]
        if isinstance(single, str):
            return (single,)
        errors.append(f"{label}: range must be a string")
        return None
    if "ranges" not in table:
        return None
    listed = table["ranges"]
    if not isinstance(listed, list) or not all(
        isinstance(item, str) for item in listed
    ):
        errors.append(f"{label}: ranges must be a list of strings")
    elif not listed:
        errors.append(f"{label}: ranges must not be empty")
    else:
        return tuple(listed)
    return None


def _check_optional_str(
    value: object, *, key: str, label: str, errors: list[str]
) -> None:
    if value is not None and (not isinstance(value, str) or not value):
        errors.append(f"{label}: {key} must be a non-empty string")


def _check_name(value: object, *, label: str, errors: list[str]) -> None:
    if value is None or not isinstance(value, str):
        return
    if not METRIC_NAME_RE.match(value):
        errors.append(
            f"{label}: invalid name (allowed: letters, digits, '_', '-', '.')"
        )


def _check_guide(value: object, *, label: str, errors: list[str]) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        errors.append(f"{label}: guide must be a positive integer")


def _check_ranges(value: object, *, label: str, errors: list[str]) -> None:
    if value is None:
        return
    if not isinstance(value, tuple) or not all(isinstance(item, str) for item in value):
        errors.append(f"{label}: ranges must be a tuple of strings")
    elif not value:
        errors.append(f"{label}: ranges must not be empty")


def _check_params(value: object, *, label: str, errors: list[str]) -> None:
    if not isinstance(value, Mapping):
        errors.append(f"{label}: params must be a mapping")
        return
    for key, param in value.items():
        if not isinstance(key, str):
            errors.append(f"{label}: param names must be strings")
        elif not _configurable(param):
            errors.append(
                f'{label}: param "{key}" must be a string, number, boolean, or a'
                " list of those"
            )


def _check_type_name(
    value: object,
    metric_types: Mapping[str, MetricType],
    *,
    label: str,
    errors: list[str],
) -> None:
    """Check a stated type exists; a template without one is a mixin.

    Its params are left unchecked here -- which ones are valid depends on
    the type, and the metric that supplies one takes that check as it
    stands.
    """
    if isinstance(value, str) and value and value not in metric_types:
        errors.append(f"{label}: unknown type {value!r}")


def _configurable(value: object) -> bool:
    if isinstance(value, list):
        return all(isinstance(item, _SCALARS) for item in value)
    return isinstance(value, _SCALARS)


def _copied(value: object) -> object:
    return list(value) if isinstance(value, list) else value


def _frozen_params(params: Mapping[str, Any]) -> Mapping[str, Any]:
    """Copy params away from whoever declared them, then close the mapping."""
    return MappingProxyType({key: _copied(value) for key, value in params.items()})
