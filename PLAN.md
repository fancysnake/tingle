# PLAN: spread metrics (`regex_spread`, `symbol_spread`)

Branch: `feature/spread-metrics`

## Problem

`regex_count` and `symbol_uses` measure **volume**: how many times a thing is
written. That is the wrong number when the goal is containment. Fixing a bug in
a legacy file often rewrites a dozen lines that already matched, so the metric
jumps and `tingle check` fails a branch that spread nothing — while a branch
that adds one fresh import of the legacy base in a brand-new file barely
registers.

What is wanted is **spread**: how many files touch the thing at all. Editing an
already-counted file moves nothing. A new file that reaches for the old
architecture is +1. A file cleaned out entirely is −1.

## Design

Two new metric types, siblings of the two existing finders:

| Type | Params | Counts |
|---|---|---|
| `regex_spread` | `pattern` (positional), `flags`, `ignore_lines` | files with at least one regex match |
| `symbol_spread` | `symbol` (positional), `ignore_lines` | Python files with at least one reference |

Separate types, not a flag on `regex_count` / `symbol_uses`: `value` keeps one
meaning per type, and `--diff` keeps one documented algorithm per type (the
flag version would silently switch between line-scoped matching and whole-file
presence comparison).

### Full-run semantics

Reuse each finder unchanged, then collapse per file:

- `value` = number of files with ≥1 surviving hit.
- `details[path]` = number of hits in that file. `located_metric` already
  computes exactly this, so the collapse is nearly free — and the report still
  says *how heavily* a file is involved, not merely that it is.
- `occurrences` = one per file, located at the **first** hit's line, so editor
  links still jump somewhere useful.
- `ignore_lines` applies before the collapse. A file whose only hits are all
  excused does not count.
- Warnings (unreadable file, syntax error, star-import fallback) pass through
  unchanged.

### Diff semantics: crossing, not touching

This is the point of the feature, and it is **not** the line-scoped algorithm
the sibling types use. A file counts as added when it holds a hit now and held
none at the merge-base, and as removed in the reverse case — the same
"crossing" model `file_count` already uses for its `over_lines` gate.

Both sides of every changed file are read in full and re-analysed; the touched
line sets are not consulted at all. Consequences, all intended:

- Rewriting 200 already-matching lines: net 0.
- A new file that matches: +1. Deleting a matching file: −1.
- A file whose last match was deleted while other lines changed: −1.

Only changed files are examined, which is sound: presence cannot flip in a file
the branch did not touch.

Unreadable sides: following the `file_count` precedent, a side that reads as
`None` is treated as *absent* rather than as an error. A warning is emitted only
when the side ought to exist given `FileStatus` — so a deleted file's missing
current side is silent, but a genuinely undecodable one is reported.
`symbol_spread` warns on a syntax error per side, as `symbol_uses_diff` does.

### Naming

`regex_files` / `symbol_files` was rejected: it reads as though the pattern
matched filenames. "Spread" names the thing being watched and matches the
motivating goal — keeping the old architecture from spreading.

## Steps

### Step 1 — shared collapse and crossing helpers

`src/tingle/mills/metrics/assemble.py`

- `per_file_result(located: MetricResult) -> MetricResult` — collapse a located
  result to one occurrence per file, first line kept, `details` and `warnings`
  passed through, `value = len(details)`.
- `presence_crossings(ctx, *, present, suffix=None) -> DiffResult` — fold each
  changed file's before/after presence into a `DiffResult`, where `present` is a
  per-side callable returning `(bool, list[str])` from the side's full text.
  Emits `Occurrence(path=...)` per crossing; reuses `accumulate_diff`.

Both are pure; no new imports outside `pacts`.

**Verify:** `mise run test:unit` (new cases in
`tests/unit/test_metric_assemble.py`, created if absent) — covering collapse of
multi-hit files, first-line retention, all-hits-ignored, and each crossing
direction including created/deleted files.

### Step 2 — `regex_spread`

`src/tingle/mills/metrics/regex_count.py` (shares `_compile`, `_line_starts`,
`validate_params`; module is 144 lines, well under the split threshold)

- `regex_spread(ctx)` — the existing `find` closure through `per_file_result`.
- `regex_spread_diff(ctx)` — per-side presence via a full-text `pattern.search`
  after `drop_ignored`.

Note in the docstring that, unlike `regex_count_diff`, matching here is
full-text on both sides, so multi-line patterns and `MULTILINE`/`DOTALL`
behave the same in diff mode as in a full run. This is a genuine improvement
over the sibling type's documented caveat.

**Verify:** `mise run test:unit` — new `tests/unit/test_metric_regex_spread.py`
and `test_metric_regex_spread_diff.py`, mirroring the existing regex test
layout.

### Step 3 — `symbol_spread`

`src/tingle/mills/metrics/symbol_uses.py` (shares `_occurrence_lines`,
`_Query`, `validate_params`; 293 lines, still under threshold)

- `symbol_spread(ctx)` — existing `find` closure through `per_file_result`,
  `suffix=".py"`.
- `symbol_spread_diff(ctx)` — per-side parse + `_occurrence_lines`, presence =
  any hit surviving `drop_ignored`, non-`.py` files skipped.

**Verify:** `mise run test:unit` — new
`tests/unit/test_metric_symbol_spread.py` and `..._diff.py`, including the
star-import fallback warning and a syntax error on one side only.

### Step 4 — register the types

`src/tingle/mills/metrics/registry.py` — two `MetricType` entries reusing the
sibling `ParamSchema`s (`primary="pattern"` / `primary="symbol"`, same
`optional` and `validate`). Descriptions phrased around spread.

`tingle list --types`, config validation, `add`, `check`, `report`, JSON output
and the TUI are all registry-driven and need no change.

**Verify:** `mise run test:unit` (`tests/unit/test_registry.py` — assert both
types are present, carry a `diff_func`, and expose the expected primary param);
then by hand:

```console
$ tingle list --types
$ tingle add regex_spread 'from tingle\.pacts' --name pacts-reach   # then revert
```

### Step 5 — documentation

- `docs/metrics.md` — two rows in the type table; a `## Spread: counting files
  instead of hits` section covering the containment motivation, the crossing
  diff semantics, `ignore_lines` interaction, and the full-text-in-diff
  difference from `regex_count`.
- `docs/diff.md` — note that the spread types compare whole-file presence
  rather than touched lines, so a rewrite of already-matching code nets zero.
- `docs/check.md` — one line: spread is the metric to gate on when the goal is
  containment rather than removal.

**Verify:** `mise run docs:build` (strict — fails on broken links).

### Step 6 — changelog and dogfood

- `CHANGELOG.md` — entry under `## [Unreleased]` → `### Added`.
- `tingle.toml` — add one spread metric so the repo exercises the feature
  against itself. Proposal: `noqa-comment-files` (`regex_spread` on
  `#\s*noqa:`, group `linting`), which reads directly against the existing
  `noqa-comment` count.

**Verify:** `mise run lint:py && mise run test:py && tingle stat && tingle stat --diff`

### Step 7 — full quality gate

**Verify, all of:**

```console
$ mise run format          # black, ruff --fix, taplo
$ mise run lint:py         # ruff, mypy, pylint, import-linter, codespell, vulture
$ mise run test:py         # unit + integration
$ mise run shitcheck       # no new noqa / Any / cast
```

Then `QA.md` manual scenarios for the branch, per the usual practice on this
repo.

## Out of scope

- A spread variant of `file_count` / `line_count` (meaningless — they already
  count files).
- `ast-grep` as a backend, TUI live findings, caching (separate `.todo` items).
- Changing `regex_count` or `symbol_uses` in any way.

## Open risks

1. **Diff cost.** Both sides of every changed file are read and, for
   `symbol_spread`, parsed twice. Bounded by the branch diff, so it stays in the
   same order as `symbol_uses_diff` today.
2. **`details` overload.** For spread types `details[path]` is a hit count while
   `value` counts files, so `sum(details.values()) != value`. Verified harmless:
   `details` is consumed in exactly two places, both in `gates/cli/render.py`
   (lines 448 and 463), and both only copy it into the JSON payload — nothing
   sums it or checks it against `value`. The JSON contract does grow a case
   where the two disagree, which the docs in Step 5 must state.
