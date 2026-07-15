# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-07-12

### Added

- Severity emoji (🎉 🦠 🚧 🚨 🔥 💀) on every value, ranking it against a
  **guide** on a logarithmic ladder. With no guide set, one is derived from
  the size of the codebase (one unit per 100 lines), so debt is read as a
  density. Pin one with `[display] guide`, or per metric with `guide`.
- `[display] loc_range` names the range those lines are counted over
  (default: the default range).
- Group headers show the sum of their metrics, ranked against the summed
  guides. In the TUI a group summing to zero starts folded, unless it holds
  an errored metric.
- The summary tables now read as an outline — a group name heads its indented
  metrics, blocks ruled apart — replacing the `Group` column, where a
  totalled heading row could read as a nameless metric. Every value's emoji
  is aligned into one column, the numbers space-padded beneath it.
- `ignore_lines` on `regex_count` and `symbol_uses`: regexes matched against
  the line a hit sits on, excusing hits that are not debt — `ANY` in an
  assertion counts, `"form": ANY` does not.
- `over_lines` on `file_count`: counts only files longer than the gate. In a
  diff, a file growing past the gate is new debt, one refactored back under
  it is debt paid off.
- `description` on any metric, shown in `tingle report` and the JSON.
  `tingle add --description` writes one.
- `tingle check` prints a line when it passes, instead of exiting silently.
- In the TUI, arrow onto an occurrence and press Space or Enter to open it in
  VS Code — the file at its line, in the window you are already in. Works from
  VS Code's integrated terminal; elsewhere the key says there is no editor.

### Fixed

- TUI: clicking empty space no longer moves focus off the metric rows,
  leaving the arrow keys scrolling instead of navigating.

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
