# CURRENT TASK

**Task:** Spread metrics — `regex_spread` and `symbol_spread`, counting the
number of *files* a pattern or symbol appears in rather than the number of hits.

**Branch:** `feature/spread-metrics` (off `main`, not merged)

**Phase:** Implement — complete. All 7 steps done, quality gate green.

**Plan:** [PLAN.md](PLAN.md) · **Manual scenarios:** [QA.md](QA.md)

## Decisions made

- Two new metric types, not a flag on `regex_count` / `symbol_uses`: one meaning
  of `value` and one documented `--diff` algorithm per type.
- Named `*_spread`, not `*_files`: the latter reads as though filenames were
  matched.
- Diff compares whole-file presence between the branch and the merge-base
  ("crossing"), not touched lines. Rewriting already-matching code nets zero —
  this is the whole point of the feature.
- Dogfood metric revised mid-implementation (approved): `type-ignore-spread`
  rather than a `# noqa:` metric, which measures 0 in this repo.
- `.todo` left untracked and untouched.

## Progress

- [x] Step 1 — shared collapse and crossing helpers in `assemble.py` (`a8d90ea`)
- [x] Step 2 — `regex_spread` + diff (`ec97c93`)
- [x] Step 3 — `symbol_spread` + diff (`2b26ec1`)
- [x] Step 4 — registry entries (`a012854`)
- [x] Step 5 — docs (`d6cdbb0`)
- [x] Step 6 — changelog + dogfood in root `tingle.toml` (`3983dbb`)
- [x] Step 7 — full quality gate + QA.md

## State at handoff

- 503 tests pass (55 new); ruff, mypy, pylint 10.00/10, import-linter 6/6,
  codespell, black all clean; `mise run docs:build` strict passes.
- `mise run shitcheck` fails on this branch **and on `main`**:
  `scripts/shitcheck.sh` does not exist in the repo. Pre-existing gap in the
  shared task config, not introduced here. Its check was run manually against
  the branch diff: one `Any` added in `src`, in
  `symbol_uses._parts(params: Mapping[str, Any])`, matching the existing
  signature convention for metric params.

## Not done

- Not merged to `main`; no PR opened.
- Manual QA scenarios in `QA.md` not yet executed.
