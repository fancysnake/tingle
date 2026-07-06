# Current Task: full report + interactive mode

**Status**: Feature complete — all 7 plan steps implemented, verified, and
committed on `feature/report-and-tui` (branched from main). Awaiting
review/merge decision.

## Done

1. pacts: Occurrence(path, line, note); MetricResult.occurrences;
   DiffResult.added/removed_occurrences
2. Run-side collection: regex (bisect offset→line, full-text semantics
   kept), symbol_uses linenos, file_count paths, config-list entries
3. Diff-side collection incl. entry-set comparison for list metrics
4. CLI restructure: `stat` + `report` commands (--json/--diff/--base);
   BREAKING: `run`/`diff` removed; bare `tingle` prints summary when
   stdout is not a TTY
5. `report --cobertura`: occurrence lines as uncovered lines (GitLab/
   Jenkins/diff-cover); line-scoped metrics only
6. Interactive TUI (textual): sortable table (1-6, repeat to flip),
   Enter → occurrence detail, q quits; bare `tingle` on a TTY; diff
   variant via `tingle --diff`
7. Docs (README CLI rewrite + migration note, CHANGELOG breaking entry)

## Verification

231 tests (ruff select=ALL, mypy strict 3.11, import-linter all green);
suite also passes on a real 3.11 interpreter (textual works there).
Dogfood: `tingle report --diff --base main` names the exact noqa lines
and per-file-ignore entries this branch added.

## Notes

- New runtime dep: textual (requires-python now >=3.11,<4.0)
- JSON schema extended with occurrence arrays (additive)
- Occurrence display: path:line, or "path: entry" for list metrics
