# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Severity emoji: every value is led by how bad it is against a **guide** —
  the point at which its debt has reached full size. Set it globally with
  `[display] guide` (default 100) or per metric with `guide`.
- Group headers now carry what their metrics add up to, judged against the
  sum of their guides. In the TUI, a group with nothing to show starts
  folded; its header still reports the total, and a group holding an errored
  metric never folds.
- `ignore_lines` on `regex_count` and `symbol_uses`: regexes matched against
  the line a hit sits on, so uses that are not debt can be excused. `ANY` in
  an assertion is debt; `"form": ANY`, standing in for something that cannot
  be compared, is not.
- `over_lines` on `file_count`: count only the files longer than the gate,
  answering "how many files are over 1k lines". A diff counts crossings — a
  file that grows past the gate is new debt though it already existed.
- `description` on any metric, shown in `tingle report` and the JSON, and
  writable with `tingle add --description`.
- `tingle check` says so when it passes, instead of passing in silence: in a
  CI log, no output cannot be told apart from a step that never ran.

### Fixed

- The TUI's scroll container no longer steals focus from the metric rows. A
  click on the empty space below them — or on the way back to a terminal
  window that had lost focus — left the arrow keys scrolling the view, and
  only clicking a row would return the cursor.

## [0.1.0] - 2026-07-12

Initial release.

### Added

- `tingle stat` — the compact summary table (`--json`, `--diff`,
  `--base`).
- `tingle report` — the full occurrence listing (`--json`, `--diff`,
  `--base`), plus `--cobertura`: Cobertura XML for CI consumers
  (GitLab, Jenkins, diff-cover) marking each occurrence line as
  uncovered.
- `tingle check` — the CI gate: measures the branch like `stat --diff`,
  then exits 1 if it worsened the metrics, printing only the lines the
  branch added under the metrics that grew (no removed lines, no summary
  table, nothing unchanged). Configured by the `[check]` section:
  `policy = "sum"` (default — fails when the metrics grow in total, so
  paying off one metric can offset another) or `policy = "any"` (fails
  when any single metric grows), plus `ignore = [...]` for metrics that
  are expected to grow and should never fail the build. `--policy`
  overrides the config for one run; `--base`, `--config`, and `--metric`
  work as on `stat`.
- `--diff [--base REF]` on `stat` and `report` — measure the impact of the
  current branch against the merge-base with a base branch (diff-cover
  style). Line-scoped metrics (`regex_count`, `symbol_uses`, `line_count`,
  `file_count`) count occurrences on added vs removed lines; value metrics
  (`toml_list_length`, `ini_list_length`) report the delta between the
  merge-base and now. Colored table (added red, removed green) with a
  Total column; JSON output includes the resolved base ref and merge-base
  sha. Base branch: `--base` flag > `[diff] base` config key > `main`, with
  `origin/<base>` fallback. Uncommitted changes count; untracked files
  count as fully added.
- Interactive mode: bare `tingle` on a terminal opens a three-level
  accordion (textual) of group → metric → file results, navigated with
  the arrow keys (`↑`/`↓` between headers, `→` unfold, `←` fold, Space to
  toggle; `hjkl` alias the same moves); each group and metric folds
  independently and unfolding a metric shows its occurrences. `f` folds
  or unfolds every group at once, leaving the file results alone. `p`
  opens the command palette, `q` quits. Non-TTY invocations print the
  static summary instead.
- Occurrences: every metric reports where its hits are — file and line
  for `regex_count`/`symbol_uses`, file names for `file_count`, and the
  actual list entries for `toml_list_length`/`ini_list_length`. Diff
  results carry signed added/removed occurrences (list metrics show
  *which* entries changed). `report --json` includes them and the
  per-file `details`; `stat --json` stays values-only, like its table.
- Metric groups: an optional `group = "<name>"` (or `tingle add
  --group`) on any metric. Grouped metrics are collected under a heading
  in the report listing, a `Group` column in the summary tables, their
  own foldable section in the TUI, and an additive `group` key in JSON.
  Presentation only — values, occurrences, and warnings are unchanged.
- TOML configuration: `tingle.toml`, with fallback to `[tool.tingle]` in
  `pyproject.toml` (`tingle.toml` wins), `--config PATH` override.
- Named ranges: include/exclude glob file sets; a metric may target one
  range (`range`) or several (`ranges`, union of files); one range may be
  marked `default = true`; built-in excludes for `.git`, `.venv`,
  `__pycache__`, `node_modules`, `dist`, `.tox`, `.mise`.
- Built-in metric types:
  - `regex_count` — regex matches across a range's files
  - `symbol_uses` — AST-based references to a bare or dotted Python symbol
  - `toml_list_length` — length of the list at a dotted key in a TOML file
  - `toml_table_array` — entries of a TOML array of tables (e.g.
    `[[tool.mypy.overrides]]`), labelling each occurrence by a
    configurable field; `explode = true` fans a list-valued label out
    into one count per element
  - `ini_list_length` — entries of a comma/newline separated INI option
  - `file_count` / `line_count` — files and lines in a range
- Config authoring commands: `tingle add TYPE [VALUE]`
  (validate-before-write, auto-generated names, repeatable `--range`,
  `--param key=value`, `--group`), `tingle init` (starter config),
  `tingle list` / `tingle list --types`.
- Rich table and JSON output; reports on stdout, warnings and per-metric
  errors on stderr; exit codes: 0 ran, 1 metric failure, 2 config/usage
  error — metric values never affect the exit code (`check` is the one
  command whose exit code reflects the measurements).
- Per-metric failure isolation: one broken metric does not stop the run.
- Python 3.11 through 3.14; the test matrix runs on all four.
- GLIMPSE architecture (pacts/specs/mills/links/gates/inits) enforced with
  import-linter; strict mypy.
