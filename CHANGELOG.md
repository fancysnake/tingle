# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- The interactive TUI shows a progress bar while it measures, rather than
  leaving the terminal blank until the table is ready. The metrics now run
  inside the app instead of before it opens, so the wait is visible: the bar
  counts files while it walks the tree — where there is no total to be a
  proportion of — and metrics once it starts measuring, naming the one it is
  on. Under it, a line of Sims-flavoured nonsense about code quality, turning
  over on a timer and whenever the phase changes. A run that finishes quickly
  never draws it, since a screen that flashes up and vanishes is worse than a
  beat of stillness.

### Changed

- Runs are around four times faster on a project carrying a virtualenv.
  `tingle stat` on this repo went from ~3.6s to ~0.85s, and nothing it reports
  changed. Three things were in the way:
    - the tree walk descended into `.venv/`, `.git/`, `node_modules/` and the
      rest of the always-excluded directories — 26,581 files walked here to
      measure 102 — and then every metric rediscovered that they matched
      nothing. It now skips them while descending. A `.venv` nested inside a
      package is not the project's own and is still measured, exactly as
      before.
    - walking used `Path.rglob`, which builds a path object per entry and
      stats every one of them. It now reads directory entries directly, which
      is ten times faster over the same files.
    - each metric resolved its ranges separately, so metrics sharing a range —
      most of them — rescanned the tree to arrive at the same answer. Each
      distinct set of ranges is now resolved once per run.


## [0.6.0] - 2026-08-20

### Added

- A metric can build on a **template** instead of stating everything itself:
  `base = "tingle.builtins.ruff.noqa_comment"` is a whole metric — type,
  pattern, name, group, description — and any key the entry states wins over
  it. `tingle library` lists what is on offer, `tingle library --expand`
  prints each one as the config it stands for, and `tingle add --base <path>`
  writes the two-line entry.
- Templates for the tools most projects already run: `black`, `codespell`,
  `import_linter`, `mypy`, `pylint`, `python`, `ruff`, `taplo`,
  `unittest_mock`.
- `extra_<param>` extends a template's list rather than replacing it, so
  `extra_ignore_lines` keeps whatever the template already excused and adds
  to it. The plain param still replaces.
- `[templates.<name>]` declares a template in the config file itself. One
  with no type is a mixin — a shared `ignore_lines` set or pair of ranges —
  usable by metrics of different types, and it may build on an imported
  template in turn.
- Templates are ordinary Python: a package of `MetricTemplate` instances at
  an import path, needing tingle and nothing else, so a team can publish its
  own and name it the same way. tingle's own pack is reached by that loader,
  not from the inside. A pack may nest as deeply as it likes, and where a
  module declares `__all__` that is what it publishes.
- A `toml_list_length` key that carries on past an array of tables means it
  once per entry: `tool.importlinter.contracts.ignore_imports` counts the
  excused imports across every contract.

### Changed

- `tingle.toml` measures itself through the template library, which changes
  nothing it counts. `any-uses` now sits under `typing` rather than
  ungrouped, since a template carries a group and there is no way to take one
  back.
- `tingle library` lists the templates a pack offers that verify, and reports
  the rest, rather than refusing to list anything when one is broken.

## [0.5.0] - 2026-08-16

### Added

- `--group NAME` narrows `tingle`, `stat`, `check` and `report` to the
  metrics under one group heading, the way `--metric NAME` narrows them to
  one metric. Both repeat and read as a union, so `--group linting --metric
  loc` measures a group plus one metric from outside it; a name no metric or
  group carries is a usage error.
- `tingle list` names each metric's group, so the values `--group` takes can
  be read off the CLI instead of out of the config file.
- The interactive TUI is a sortable table: group headers, metrics and their
  located hits are rows in one outline instead of a three-level accordion.
  Sort by group, name, type, value or score — `g` `n` `t` `v` `c` ascending,
  `G` `N` `T` `V` `C` descending. Sorts stack, so `n` then `t` gives
  type-major order with names ordered inside each type, and asking for a
  stacked key the other way up turns it over in place. The column deciding
  the order carries ▲ or ▼, and a line under the table names the whole stack.
  Sorting by anything but `group` drops the group headers and names each
  metric's group on its own row instead; `0` clears the stack and brings them
  back.
- `value` and `score` are separate sorts: the raw count, and the same number
  against the metric's own guide. Only `score` compares metrics whose guides
  differ.
- Search the table with `/`. Case-sensitive substring, matched against a
  metric's name, its group's, its description and its range names — and
  against the path of every occurrence, whether or not it is on screen, so a
  fully folded tree is still searchable. A metric found by name is left as
  you had it; found by description or range, it opens on those words; found
  through its files, it opens showing only the files that matched.
  ++enter++ keeps the query and hands the rows back, ++escape++ restores the
  outline untouched.
- A metric's description, the ranges it measures over and the error it failed
  with are rows under it, shown when it is unfolded.
- A GitHub Actions composite action,
  `fancysnake/tingle/actions/metrics-history`, that records `stat --json` on
  a branch and publishes its history as one chart per metric group — a line
  per metric, on a logarithmic axis that still has room for a count of 0. Its
  other half, `.../metrics-history/publish`, fetches that chart into a site
  being built, for repositories whose Pages source is already a build
  artifact and so cannot serve the data branch. Both are documented under
  [History](https://tingle.fancysnake.dev/history/); tingle's own history is
  published this way, at <https://tingle.fancysnake.dev/history/chart/>.

### Changed

- A `--metric` or `--group` name the config does not carry is reported as
  `usage error:` rather than `config error:`. The file is valid; the typo is
  on the command line.
- TUI: folding a metric now hides its description, which the accordion kept
  visible at rest.
- A file is called binary on a NUL in its first 8,000 bytes, the window git's
  own differ uses; it was 8,192.
- An untracked file that is not UTF-8 now counts as fully added, the way git
  would diff it. Whether a metric may read it is still decided when the
  metric runs.

### Fixed

- TUI: the ▲/▼ on the sorted column was cut off whenever that column's values
  were narrower than its heading.
- TUI: opening a hit no longer blocks the table while the editor is being
  handed the file, and an editor that will not open it says so in a
  notification instead of ending the session.

### Removed

- `Occurrence.sort_key`, which ordered hits by path, then line, then note.
  Nothing asked for that order.

## [0.4.1] - 2026-08-09

### Added

- `regex_spread` and `symbol_spread`: the searches `regex_count` and
  `symbol_uses` run, counting the **files** a thing appears in rather than
  the number of times it is written. A file with forty matches counts once.
- In a diff the spread types compare whole-file presence against the
  merge-base rather than counting touched lines, so rewriting a file that
  already matched nets zero while one new file that matches is +1 — the
  metric to gate on for containment rather than removal, since it does not
  fail every bug fix to legacy code. They match full text on both sides, so
  they carry no multi-line caveat in diff mode.

### Changed

- `symbol_uses` side-scoped diff warnings now read `a.py: base side: skipped
  (syntax error: ...)`, with the colon every other side warning already used.

## [0.4.0] - 2026-07-16

### Added

- Severity emoji (🎉 🦠 🚧 🚨 🔥 💀) on every value, ranking it against a
  **guide** on a logarithmic ladder. With no guide set, one is derived from
  the size of the codebase (one unit per 100 lines), so debt is read as a
  density. Pin one with `[display] guide`, or per metric with `guide`;
  `[display] loc_range` names the range those lines are counted over.
- Group headers show the sum of their metrics, ranked against the summed
  guides. In the TUI a group summing to zero starts folded, unless it holds
  an errored metric.
- The summary tables read as an outline — a group name heads its indented
  metrics, blocks ruled apart — replacing the `Group` column. Every value's
  emoji is aligned into one column, the numbers space-padded beneath it.
- `ignore_lines` on `regex_count` and `symbol_uses`: regexes matched against
  the line a hit sits on, excusing hits that are not debt — `ANY` in an
  assertion counts, `"form": ANY` does not.
- `over_lines` on `file_count`: counts only files longer than the gate. In a
  diff, a file growing past the gate is new debt, one refactored back under
  it is debt paid off.
- `description` on any metric, shown in `tingle report`, the JSON and the
  TUI. `tingle add --description` writes one.
- `tingle check` prints a line when it passes, instead of exiting silently.
- In the TUI, Space or Enter on an occurrence opens it in VS Code — the file
  at its line, in the window you are already in. Works from VS Code's
  integrated terminal; elsewhere the key says there is no editor.

### Fixed

- TUI: clicking empty space no longer moves focus off the metric rows,
  leaving the arrow keys scrolling instead of navigating.

## [0.1.0] - 2026-07-12

Initial release: `tingle.toml` (or `[tool.tingle]` in `pyproject.toml`),
named ranges of include/exclude globs, metric groups, and the three commands.

### Added

- `tingle stat` — the summary table. `tingle report` — every occurrence,
  file and line, plus `--cobertura` for CI consumers that read coverage XML
  (GitLab, Jenkins, diff-cover). Both take `--json`, `--diff`, `--base`,
  `--config` and `--metric`. Bare `tingle` on a terminal opens the same
  results as a foldable accordion; a non-TTY gets the static summary.
- `tingle check` — the CI gate: it measures the branch like `stat --diff`,
  then exits 1 if the metrics worsened, printing only the lines the branch
  added under the metrics that grew. `[check] policy = "sum"` (default) fails
  when the metrics grow in total, `"any"` when a single metric does;
  `ignore = [...]` names metrics that may grow; `--policy` overrides for one
  run.
- `--diff [--base REF]` — the impact of the current branch against the
  merge-base with a base branch, diff-cover style. Line-scoped metrics count
  occurrences on added vs removed lines, value metrics report the delta
  between the merge-base and now. The base resolves as `--base` >
  `[diff] base` > `main`, with an `origin/<base>` fallback. Uncommitted
  changes count; untracked files count as fully added.
- Metric types: `regex_count` (regex matches), `symbol_uses` (AST references
  to a bare or dotted Python symbol), `toml_list_length`, `toml_table_array`
  (entries of an array of tables, labelled by a configurable field;
  `explode = true` fans a list-valued label out into one count per element),
  `ini_list_length`, `file_count`, `line_count`.
- Every metric reports where its hits are, and diff results carry signed
  added/removed occurrences, so the list metrics show *which* entries
  changed. `report --json` includes them and the per-file `details`;
  `stat --json` stays values-only, like its table.
- Config authoring: `tingle add TYPE [VALUE]` (validate-before-write,
  auto-generated names, repeatable `--range`, `--param key=value`,
  `--group`), `tingle init`, `tingle list` / `tingle list --types`.
- Reports on stdout, warnings and per-metric errors on stderr; exit codes: 0
  ran, 1 metric failure, 2 config/usage error. Metric values never affect the
  exit code, `check` being the one command whose exit code reflects the
  measurements, and one broken metric does not stop the run.
- Python 3.11 through 3.14; the test matrix runs on all four.
- GLIMPSE architecture (pacts/specs/mills/links/gates/inits) enforced with
  import-linter; strict mypy.
