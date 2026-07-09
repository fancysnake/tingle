# Plan: Metric groups + `toml_table_array` (count mypy overrides)

## Goal

Two related additions, driven by the same use case ("show `# type: ignore`
count and the number of mypy overrides together under one *typing* group"):

1. **Metric groups** — an optional `group = "<name>"` on any metric. Metrics
   sharing a group are shown together, under a group heading, in every human
   view (report listing, compact table, TUI) and named in JSON. Purely a
   presentation layer: values, occurrences, and warnings are unchanged.
2. **`toml_table_array` metric type** — count the entries of a TOML *array of
   tables* (e.g. `[[tool.mypy.overrides]]`), labelling each occurrence by a
   configurable field (e.g. `module`).

Decisions taken (see conversation): groups are a **per-metric field** (not
separate `[[groups]]` tables); mypy-override counting gets a **dedicated
metric type** (not an extension of `toml_list_length`).

## Why a new type when `toml_list_length` already counts them

`[[tool.mypy.overrides]]` parses as a Python `list` of dict tables, so
`toml_list_length` with `key = "tool.mypy.overrides"` already returns the
correct **value** today. What it cannot do is produce meaningful
**occurrences**: `_entries()` renders each table via `str(entry)` — a raw
dict repr. `toml_table_array` exists to label each override by a chosen field
(`module`), so `report`/TUI/cobertura show `pyproject.toml: foo.*` instead of
`{'module': 'foo.*', 'ignore_errors': True}`. Counting is not new; useful
occurrences are.

## Scope

- **Groups**: `pacts/config.py` (`MetricSpec.group`, `MetricDraft.group`),
  `mills/config.py` (parse + validate), `gates/cli/render.py` (grouping
  helper + all renderers + JSON), `gates/tui/app.py` (Group column),
  `mills/add.py` + the `add` CLI (`--group`).
- **Metric type**: `mills/metrics/config_lists.py` (new `toml_table_array`
  and `toml_table_array_diff`, reusing the existing `_delta`/`_empty`
  helpers), `inits/wiring.py` (register the type).
- **Dogfood/docs**: `tingle.toml`, `README.md`, `CHANGELOG.md`,
  `CURRENT_TASK.md`.
- **Unchanged**: runner execution model, ranges, diff engine, cobertura
  semantics, all existing metric types.

## Independence from `PLAN.md` (streaming)

No conflict. `toml_table_array` is a **batch** metric (reads one named config
file, ignores ranges) — exactly the class the streaming plan explicitly keeps
on the current `MetricContext`/`func` interface. Groups touch config/render/
TUI, which streaming does not. The two plans can land in either order.

## Feature 1 — Metric groups

### Contracts (`pacts/config.py`)

- `MetricSpec` gains `group: str | None = None`.
- `MetricDraft` gains `group: str | None = None` (for `tingle add`).

Both additive with defaults → existing construction sites unaffected.

### Validation (`mills/config.py`)

- Add `"group"` to `_METRIC_RESERVED_KEYS` so it is **not** collected into
  `params` (otherwise every metric type would reject it as unknown).
- In `_validate_metrics`: if `group` is present it must be a non-empty
  string; on success set `MetricSpec.group`. (Reuse `METRIC_NAME_RE`? No —
  group labels are human-facing headings; only require non-empty string. Note
  in a comment.)

### Ordering model (the one rule, applied everywhere)

Grouping is a stable reshape of the outcome list, never a re-sort of values:

- **Group display order** = order in which each group name first appears in
  config.
- **Within a group** = config order.
- Metrics with no group form a single trailing **"(ungrouped)"** section.
- **Consequence:** with no `group` anywhere, there is exactly one ungrouped
  section in original order → *byte-identical* output to today. This is the
  invariant the tests pin.

Implement once as a pure helper in `gates/cli/render.py` (presentation
logic; the TUI already imports from this module):

```python
def group_sections(
    outcomes: Sequence[MetricOutcome | DiffOutcome],
) -> list[tuple[str | None, list[MetricOutcome | DiffOutcome]]]:
    """(group_name | None, outcomes) in first-appearance order; None last."""
```

### Rendering

- `run_listing` / `diff_listing` (the human "report"): for each section emit a
  bold group heading (e.g. `## typing`), then the existing per-metric lines;
  the `None` section gets a `(ungrouped)` heading only if at least one *named*
  group exists (so today's output is unchanged when no groups are used).
- `report_table` / `diff_table`: add a leading **`Group`** column; rows
  emitted in `group_sections` order. (A column keeps the table dense and
  sortable; the listing carries the visual headers.)
- `run_json` / `diff_json`: add `"group": outcome.spec.group` per metric
  (additive; `null` when unset). Order follows `group_sections` for
  consistency with the tables.
- `cobertura`: unchanged (line-coverage format has no place for groups).

### TUI (`gates/tui/app.py`)

*(Revised from the original DataTable/Group-column design: the TUI is now a
3-level nested accordion, approved in conversation.)*

- Three levels of `Collapsible`: **group** → **metric** → **file results**.
- Groups are rendered in `group_sections` order; each group is a `Collapsible`
  **expanded** at rest, so every group and its metric rows are visible on load.
  The trailing `None` section uses an `(ungrouped)` heading only when at least
  one named group exists (mirrors the listing rule).
- Each metric is a nested `Collapsible`, **collapsed** at rest; its body is the
  occurrence/file-result lines. Enter (or click) on a metric header expands it
  in place.
- **Fold behaviour:** expanding a metric collapses every *other* group section
  (the active group and its sibling metric rows stay visible); collapsing that
  metric again auto-reopens the other groups, back to the all-open resting
  state. Implemented via `Collapsible.Expanded`/`Collapsed` handlers.
- Up/Down move focus across all headers (group and metric titles) using the
  existing `focus_metric` priority bindings.

### `tingle add --group`

- CLI: add `--group TEXT` option; thread into `MetricDraft.group`.
- `mills/add.py build_metric`: when `draft.group` is set, write `group = ...`
  into the emitted metric table (place it after `type`, before params, for
  readable diffs). Validated through the existing merged-config `validate()`.

## Feature 2 — `toml_table_array` metric type

### `mills/metrics/config_lists.py`

```python
def toml_table_array(ctx: MetricContext) -> MetricResult:
    """Count entries of the array of tables at dotted `key`."""
    return _table_array_count(ctx.read, ctx.params)

def toml_table_array_diff(ctx: DiffMetricContext) -> DiffResult:
    return _delta(_table_array_count, ctx)          # reuse existing helper
```

`_table_array_count(read, params)`:

- params: `key` (required, dotted), `file` (optional, default
  `TOML_LIST_DEFAULT_FILE` = `pyproject.toml`), `label` (optional),
  `explode` (optional bool, default `false`).
- Read + parse + navigate to `key` reusing the same not-found / invalid-TOML /
  missing-key warnings as `_toml_count` (factor the shared "load + descend"
  into a small helper so both stay consistent).
- Require the value be a `list` whose every element is a `Mapping`; otherwise
  `_empty(f'{file}: value at "{key}" is not an array of tables')`.

**Count unit — `explode` (decision taken in conversation):**

- **`explode = false` (default): count tables.** One `[[...]]` block = 1.
  - `value = len(entries)`.
  - Occurrences, in file order, one per table:
    - if `label` present in the entry: note = the field stringified; a list
      value (mypy `module = ["a","b"]`) is joined with `", "`.
    - else: note = `f"#{index}"` (1-based) so unlabeled entries stay
      addressable.
- **`explode = true`: count label elements.** Each element of the label list
  becomes its own count and occurrence (e.g. `module = ["a","b","c"]` → 3).
  - Requires `label` — fanning out needs a field to expand. Validation
    errors if `explode` is true without `label`.
  - Per table: if the label value is a list, emit one occurrence per element
    (note = each element stringified); if it is a scalar, one occurrence; if
    the label field is missing, one `#{index}` occurrence (counts as 1).
  - `value = ` total occurrences emitted (sum across tables).
- Empty array → `value=0`, no occurrences, no warning (both modes).

`validate_toml_table_array_params(params)`: `key` non-empty string; `file`
and `label`, if present, strings; `explode`, if present, a bool; and
`explode = true` requires `label`.

**Diff note:** `_delta` compares occurrences as *sets*, so two overrides that
produce the same label collapse in the added/removed lists while `net` stays
count-based — identical to the documented behaviour of the existing list
metrics. Acceptable and consistent.

### Wiring (`inits/wiring.py`)

Register:

```python
"toml_table_array": MetricType(
    name="toml_table_array",
    func=toml_table_array,
    required_params=("key",),
    optional_params=("file", "label", "explode"),
    primary_param="key",
    validate_params=validate_toml_table_array_params,
    description="Count entries of a TOML array of tables (e.g. mypy overrides).",
    diff_func=toml_table_array_diff,
),
```

## Dogfood + docs

- `tingle.toml`: add a `mypy-overrides` metric
  (`type = "toml_table_array"`, `key = "tool.mypy.overrides"`,
  `label = "module"`) and assign `group`s to the existing metrics, e.g.
  `typing` (type-ignores, mypy-overrides), `lint` (noqa, ruff-ignores,
  ruff-per-file-ignores, pylint-disables), `size` (python-loc, python-files).
  (Adds `[[tool.mypy.overrides]]` coverage of tingle's own config as a side
  effect — the repo currently has none, so the metric reads 0 until one is
  added; that is a truthful baseline.)
- `README.md`: document the `group` field and the `toml_table_array` type
  (with the mypy-overrides example) in the metrics/CLI sections.
- `CHANGELOG.md`: additive entries — "metric groups" and "`toml_table_array`
  metric type". No breaking change (JSON gains an additive `group` key; table/
  TUI gain a `Group` column).
- `CURRENT_TASK.md`: status.

## Verification

Gates (unchanged commands): `pytest`, `ruff check` (select=ALL),
`mypy` (strict, 3.11 target), `lint-imports`.

**Invariant tests (regression guard):**

- With no `group` in any metric, `run_listing`, `report_table`, `diff_*`, and
  `run_json` output is byte-identical to pre-change (single ungrouped
  section, original order). No existing expectation should change; if one
  does, that's a bug in the reshape.

**New tests:**

- config: `group` accepted; empty/non-string `group` rejected with a clear
  message; `group` never appears in a metric's `params` (does not trip
  "unknown param").
- `group_sections`: first-appearance ordering; scattered members of one group
  collected together; ungrouped section placed last; single-group and
  no-group shapes.
- render: group headings present in listings; `Group` column populated in
  tables; JSON carries `group` (and `null` when unset).
- TUI (gates test): `Group` column present; rows in section order; sort
  bindings still cover the widened column set.
- `toml_table_array`: count of `[[tool.mypy.overrides]]` (tables mode); label
  from a string field; label from a **list** field (joined); missing-label
  index fallback; non-array-of-tables value → warning; missing key → warning;
  default file (`pyproject.toml`); empty array → 0.
- `toml_table_array` `explode = true`: list label fans out (3-element
  `module` → value 3, one occurrence each); scalar label → 1; missing label →
  1 (`#index`); `explode = true` without `label` → validation error.
- `toml_table_array_diff`: added / removed overrides via `_delta`; base-side
  warning prefixing.
- `add`: `--group` writes the `group` key and the result validates.

## GLIMPSE / layering check

- `MetricSpec.group` in `pacts.config` — contract layer, fine.
- `toml_table_array` in `mills.metrics` — no new IO (reads via injected
  `ctx.read`), fine.
- `group_sections` in `gates/cli/render` — presentation; TUI (`gates`)
  importing it is a within-layer import, already the established pattern.
- No change to `mills/runner`, `links`, or the import-linter contracts.

## Steps (commit after each; each independently verifiable)

1. **pacts + config**: `MetricSpec.group`, `MetricDraft.group`, `"group"`
   reserved key, validation. Tests: acceptance, rejection, no-param-leak.
2. **`group_sections` + renderers**: helper, group headings in
   `run_listing`/`diff_listing`, `Group` column in `report_table`/
   `diff_table`, `group` in `run_json`/`diff_json`. Invariant + grouping
   tests.
3. **TUI**: 3-level nested accordion (group → metric → file results); groups
   expanded at rest, expanding a metric folds other groups and collapsing
   reopens them. Gates test.
4. **`toml_table_array` + diff + validation** in `mills/metrics`. Unit tests.
5. **Wiring** registration + **`tingle add --group`**. Add-flow test.
6. **Dogfood + docs**: `tingle.toml`, `README`, `CHANGELOG`, `CURRENT_TASK`.

## Open question for approval before Step 1

- **Compact-table grouping**: this plan adds a `Group` *column* and reorders
  rows into sections. Alternative is a spanning **header row** per group
  (`Table.add_section()` + a styled label row) and no column. Column is
  denser and sortable in the TUI; header rows read more like the listing.
  Confirm which you want for the tables before I build Step 2.
