# Current Task: tingle MVP

**Status**: MVP complete — all 12 plan steps implemented, verified, and
committed on `feature/mvp`. Awaiting review/merge decision.

**Plan**: see `MVP_PLAN.md` (approved). Each step has its own commit.

## Done

1. Scaffolding: GLIMPSE layer packages, typer/rich/tomlkit deps, dev
   tooling (pytest, ruff, mypy strict, import-linter with layer contracts)
2. pacts (contracts) + specs (invariants)
3. Config discovery/parsing (tingle.toml > [tool.tingle], --config)
4. Config validation (aggregated ConfigError, strict params, default range)
5. Filesystem walking + pure range resolution (multi-range union)
6. file_count / line_count / regex_count metrics
7. toml_list_length / ini_list_length metrics (generic lint-ignore counting)
8. symbol_uses metric (AST import-binding analysis)
9. Runner (per-metric error isolation) + static wiring
10. CLI: run (default) + list, table/JSON output, exit codes 0/1/2
11. tingle add (validate-before-write, auto-names) + tingle init
12. README, dogfood tingle.toml, final sweep (138 tests, all gates green)

## Verification

`mise exec -- poetry run <pytest | ruff check | mypy | lint-imports>` — all
clean. Dogfood: `mise exec -- poetry run tingle` in the repo works.

## Out of scope (deliberate)

- No history/storage of results, no thresholds/exit-code gating on values
- No HTML export, no Python-file "advanced mode", no plugin API (YAGNI)

## Possible next steps (not started)

- Thresholds (`fail_above`) for CI ratcheting
- HTML report export
- Publishing to PyPI
