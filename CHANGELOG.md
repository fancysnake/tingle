# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `tingle diff` — measure the impact of the current branch against the
  merge-base with a base branch (diff-cover style). Line-scoped metrics
  (`regex_count`, `symbol_uses`, `line_count`, `file_count`) count
  occurrences on added vs removed lines; value metrics
  (`toml_list_length`, `ini_list_length`) report the delta between the
  merge-base and now. Colored table (added red, removed green) with a
  Total column; JSON output includes the resolved base ref and
  merge-base sha. Base branch: `--base` flag > `[diff] base` config key
  > `main`, with `origin/<base>` fallback. Uncommitted changes count;
  untracked files count as fully added.

## [0.1.0] - 2026-07-06

### Added

- Initial MVP release.
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
  - `ini_list_length` — entries of a comma/newline separated INI option
  - `file_count` / `line_count` — files and lines in a range
- CLI: `tingle` / `tingle run` (with `--format table|json`, repeatable
  `--metric` filter), `tingle add TYPE [VALUE]` (validate-before-write,
  auto-generated names, repeatable `--range`, `--param key=value`),
  `tingle init` (starter config), `tingle list` / `tingle list --types`.
- Rich table and JSON output; reports on stdout, warnings and per-metric
  errors on stderr; exit codes: 0 ran, 1 metric failure, 2 config/usage
  error — metric values never affect the exit code.
- Per-metric failure isolation: one broken metric does not stop the run.
- GLIMPSE architecture (pacts/specs/mills/links/gates/inits) enforced with
  import-linter; strict mypy; 138 tests.
