# Current Task: tingle diff

**Status**: Feature complete — all 7 plan steps implemented, verified, and
committed on `feature/diff` (branched from origin/main). Awaiting
review/merge decision.

**Plan**: approved "tingle diff — Feature Plan" (per-type diff semantics,
merge-base vs working tree, colored impact table + totals).

## Done

1. pacts/diff contracts (FileDiff/BranchDiff/DiffSource/DiffResult/…),
   MetricType.diff_func, `[diff] base` config key
2. links/git/cli: hardened git adapter — merge-base with origin/ fallback,
   -U0 hunk parser, untracked synthesis, read_base via git show
   (21 real-git tests, fully isolated env)
3. counts + regex diff variants (per-line added/removed counting)
4. symbol_uses lineno refactor (behavior-neutral) + diff variant;
   toml/ini value deltas
5. mills/diff.DiffRunner (isolation, totals, range filtering, skip notes)
   + wiring (diff_func on all six types, diff_source factory)
6. `tingle diff` command: --base/--format/--metric, colored
   Added/Removed/Net/Total table, JSON with base + merge_base
   (9 e2e tests on real repos)
7. README diff section, CHANGELOG Unreleased entry, dogfood run

## Verification

210 tests, ruff select=ALL, mypy strict, import-linter — all green.
Dogfood: `tingle diff --base main` on this repo reports +14 noqa,
+5 per-file-ignores, +2132/−47 LOC, +12 files — matches the branch.

## Known approximations (documented in README)

- Diff counting is per-line; newline-containing regex patterns don't
  match in diff mode
- symbol_uses attributes references to their starting line
- Renames = delete + add; shallow clones need history for merge-base
