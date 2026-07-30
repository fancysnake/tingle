# CURRENT TASK

**Task:** Spread metrics — `regex_spread` and `symbol_spread`, counting the
number of *files* a pattern or symbol appears in rather than the number of hits.

**Branch:** `feature/spread-metrics` (off `main`)

**Phase:** Plan — written, awaiting approval. Nothing implemented.

**Plan:** [PLAN.md](PLAN.md) — 7 steps.

## Decisions made

- Two new metric types, not a flag on `regex_count` / `symbol_uses`: one meaning
  of `value` and one documented `--diff` algorithm per type.
- Named `*_spread`, not `*_files`: the latter reads as though filenames were
  matched.
- Diff compares whole-file presence between the branch and the merge-base
  ("crossing"), not touched lines. Rewriting already-matching code nets zero —
  this is the whole point of the feature.
- `.todo` left untracked and untouched.

## Progress

- [ ] Step 1 — shared collapse and crossing helpers in `assemble.py`
- [ ] Step 2 — `regex_spread` + diff
- [ ] Step 3 — `symbol_spread` + diff
- [ ] Step 4 — registry entries
- [ ] Step 5 — docs
- [ ] Step 6 — changelog + dogfood in root `tingle.toml`
- [ ] Step 7 — full quality gate + QA.md
