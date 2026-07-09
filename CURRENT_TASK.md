# Current Task: metric groups + toml_table_array (+ TUI accordion)

**Status**: Feature complete — implemented, verified, and committed on
`feature/report-and-tui` (branched from main). Awaiting review/merge
decision. Builds on the earlier full-report + interactive-mode work on
the same branch (see git history).

## Done (this round)

0. TUI redesign: the interactive view is now an **accordion**, not a
   sortable table. Sorting/columns removed; `↑`/`↓` move between headers,
   Enter/click expands a metric's occurrences in place.
1. `MetricSpec.group` / `MetricDraft.group`; `group` reserved config key;
   validated as a non-empty string (never leaks into `params`).
2. `group_sections` reshape helper (first-appearance order, ungrouped
   last) driving every human view: `##` headings in the report listing,
   a `Group` column in the summary tables (only when a group is used, so
   groupless output is byte-identical), and an additive `group` JSON key.
3. TUI 3-level accordion: group → metric → file results. Groups expanded
   at rest; each group and metric folds/unfolds independently (↑/↓ move
   between headers, → unfold, ← fold, Space/Enter/click toggle; hjkl
   alias the moves). `f` folds/unfolds every group at once. The arrow
   bindings live on a `NavCollapsible` widget, not the app, so the
   command palette on `p` keeps its own arrows.
   Groupless config falls back to a flat accordion.
4. `toml_table_array` metric type + diff variant: count entries of a TOML
   array of tables (e.g. `[[tool.mypy.overrides]]`), `label` describes
   each occurrence, `explode = true` fans a list label out per element.
   Shares load+descend with `toml_list_length` via `_descend_toml`.
5. Wiring registration + `tingle add --group` (group written after
   `type` for readable diffs).
6. Dogfood (`tingle.toml` grouped into lint/typing/size + a
   `mypy-overrides` metric) and docs (README metric-type table, Groups
   section, CLI notes; CHANGELOG additive entries).

## Verification

258 tests green: `ruff check` (select=ALL), `mypy` (strict, 3.11),
`lint-imports`. Run via `mise exec -- pytest` / `ruff` / `mypy` /
`lint-imports`. Dogfood: `tingle stat` shows the Group column and the
three sections; `mypy-overrides` reads 0 with a "key not found" warning
(the repo has no `[[tool.mypy.overrides]]` yet — a truthful baseline).

## Notes

- Groups are presentation-only: values, occurrences, warnings unchanged.
- JSON gains an additive `group` key (null when unset); the compact
  tables gain a `Group` column only when a group exists.
- Plan doc: `PLAN_METRIC_GROUPS.md` (Step 3 revised to the approved
  3-level accordion instead of the original DataTable Group column).
