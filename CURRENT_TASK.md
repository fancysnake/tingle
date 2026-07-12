# Current Task: `tingle check` (CI gate)

**Status**: Feature complete — implemented, verified, and committed on
`feature/check-command` (branched from main). Awaiting review/merge
decision.

Note: the previous task (metric groups + toml_table_array + TUI
accordion) is on `feature/report-and-tui` and is still awaiting its own
merge decision. This branch does not depend on it.

## Done

1. `[check]` config section: `policy` (`sum` | `any`) and `ignore`.
   `CheckPolicy` is a `StrEnum` mirroring the existing `FileStatus`
   idiom; `CheckSpec` carries the pair on `Config`. Validation follows
   `[diff]`: problems are collected, not raised one at a time. Names in
   `ignore` are checked against the configured metrics, so a typo fails
   at load instead of silently ignoring nothing.
2. `mills/check.py::judge` — a pure function over the `DiffReport` that
   `--diff` already produces, so the gate is a policy layer, not a
   second way to measure. Ignored metrics move neither the total nor the
   verdict; errored metrics are left to the caller (a metric that could
   not be measured is no evidence either way).
3. `MetricsService.check` (one call per use case) and the `tingle check`
   command. Prints only the added occurrences under the metrics that
   grew; exits 1 when the policy says the branch worsened things.
   `--policy` overrides the config for a run.
4. Docs (README section, CLI entry, CI example, corrected exit-code
   paragraph; CHANGELOG) and dogfood (`[check] policy = "sum"` in
   `tingle.toml`).

## Semantics

- `sum` (default): fails when the metrics grow **in total** — debt paid
  off in one metric offsets debt taken on in another.
- `any`: fails when **any single** metric grows.
- Under `sum` a metric can grow and the branch still pass; its added
  lines are printed anyway, because the trade is worth seeing even when
  allowed. A branch that worsens nothing prints nothing and exits 0.

## Verification

314 tests green: `ruff check`, `black --check`, `mypy` (strict),
`lint-imports`. Run via `mise exec --`. **Formatting is black, not
`ruff format`** — the two disagree.

Dogfood: `tingle check --base main` on this branch exits 0 silently;
with two debt lines planted in a source file it exits 1 and prints just
those two lines with their locations.

## Known, deliberately left alone

`--diff` (and so `check`) prints a warning twice when a config key is
missing on **both** the base and current side — once with a `base side:`
prefix. Root cause: `mills/metrics/config_lists.py::_delta` concatenates
both sides' warnings unconditionally. Pre-existing, not introduced by
`check`; reviewed with the human and kept as is.
