# Manual Test Scenarios

Based on: `feature/spread-metrics` vs `main`
Changes in: **`regex_spread`**, **`symbol_spread`**, **crossing semantics in a diff**,
**`tingle check` gating**, **JSON `value` vs `details`**, **shared finder refactor
(regression surface on `regex_count` / `symbol_uses`)**

Run commands from the repo root. This branch is **dogfooded** — the root `tingle.toml`
carries `type-ignore-spread` beside the existing `type-ignores` count, so several
scenarios below work against tingle's own source with no setup.

**Preconditions common to all:** built/installed tingle on this branch
(`poetry install`), a git repo with history (the merge-base is needed for every `--diff`
scenario).

The single most important property to confirm by hand: **a branch that reworks code
which already matched must net zero.** That is the entire point of the feature, and it
is the one thing a reader will not believe until they see it.

---

## `regex_spread` — counting files, not matches

### A file counts once however many matches it holds

**Preconditions:** the root `tingle.toml` as committed on this branch.

- [ ] Run `tingle report --metric type-ignores` → Expected: **4** occurrences, two of
  them in the same file (`tests/unit/test_contracts.py`).
- [ ] Run `tingle report --metric type-ignore-spread` → Expected: **3** occurrences —
  one line per *file*, and `test_contracts.py` appears **once**, not twice.
- [ ] Compare the two lists → Expected: the spread list is the count list with
  duplicates-per-file collapsed; no file appears in one and not the other.
- [ ] Read the spread occurrence for `test_contracts.py` → Expected: it points at the
  **first** `# type: ignore` in that file (line 23), not the second.

### It reacts to a new file, not to more matches in an old one

**Preconditions:** a scratch file you will delete afterwards.

- [ ] Add a second `# type: ignore` to a file that **already** has one, run
  `tingle stat` → Expected: `type-ignores` goes **up by 1**, `type-ignore-spread` stays
  **the same**.
- [ ] Instead put one `# type: ignore` in a file that had **none**, run `tingle stat` →
  Expected: **both** go up by 1.
- [ ] Remove one of two `# type: ignore`s from the same file → Expected: the count drops,
  the spread does not.
- [ ] Remove the last one from a file → Expected: both drop.

### Params behave as they do on `regex_count`

**Preconditions:** a scratch `tingle.toml`, or a `--config` pointing at one.

- [ ] Configure a `regex_spread` with `flags = ["IGNORECASE"]` against mixed-case text →
  Expected: matches case-insensitively, same as `regex_count`.
- [ ] Configure one with an invalid pattern (`'([unclosed'`) → Expected: rejected at
  **config validation** time with a clear message, not at run time — same as
  `regex_count`.
- [ ] Configure one with an unknown flag (`flags = ["MAGIC"]`) → Expected: config error
  naming the allowed flags.
- [ ] Configure one with a param that does not exist (`over_lines = 5`) → Expected:
  `unknown param "over_lines"`.

---

## `symbol_spread` — counting files, not references

### Reach rather than volume

**Preconditions:** a scratch project with a legacy class used several times in one file
and once in another:

```toml
[[metrics]]
name = "legacy-uses"
type = "symbol_uses"
symbol = "app.legacy.OldClient"

[[metrics]]
name = "legacy-spread"
type = "symbol_spread"
symbol = "app.legacy.OldClient"
```

- [ ] Run `tingle report` → Expected: `legacy-uses` lists every reference including the
  import line; `legacy-spread` lists each *file* once, at its first reference.
- [ ] Point both at a **bare** symbol (`OldClient`) → Expected: same collapse behaviour;
  the bare-symbol overcounting warning in the docs applies to the count, and the spread
  is correspondingly less sensitive to it.
- [ ] Add a `.md` or `.txt` file containing the word `OldClient` → Expected: **not**
  counted by either, and **no** warning about it (non-Python files are skipped silently).
- [ ] Add a Python file with a **syntax error** → Expected: it is skipped with a warning,
  and does not count toward the spread.
- [ ] Add a file using `from app.legacy import *` then `OldClient()` → Expected: counted,
  with the star-import fallback warning — one warning, not one per reference.

---

## Crossing semantics in a diff — the core of the feature

### Reworking legacy code nets zero

**Preconditions:** a branch off `main` that heavily edits a file which **already**
matched, and adds **one** new file that matches. (This is the exact scenario the feature
exists for.)

- [ ] Run `tingle stat --diff` → Expected: the **counting** metric shows a large `+N`
  driven by churn; the **spread** metric shows exactly **`+1`**.
- [ ] Run `tingle report --diff --metric <spread-metric>` → Expected: exactly one `+`
  line, naming the **new** file — the churned file is **absent** from the list.
- [ ] Confirm the spread occurrence has **no line number** (bare path) → Expected: it is
  the *file* that crossed, so a line would be a lie.
- [ ] Now rework the legacy file even harder (double the matches) and rerun → Expected:
  the spread net is **still** `+1`; only the counting metric moves.

### Both directions, and creation / deletion

- [ ] On a branch, delete the **last** match from a file that had one → Expected: spread
  net `−1`, the file appears under removed occurrences.
- [ ] Delete an entire file that matched → Expected: `−1`, and **no** warning (a deleted
  file has no current side to read, which is not a problem).
- [ ] Create a new file that matches → Expected: `+1`, no warning.
- [ ] On one branch do both (one file gains, one loses) → Expected: `Added +1`,
  `Removed −1`, `Net 0` — and both files listed in `report --diff`.
- [ ] Rename a file that matches, without changing its contents → Expected: treated as
  delete + add, so net 0 (documented approximation — confirm it does not report `+1`).

### The diff never consults touched lines

- [ ] Take a file that matches, and change a line **far away** from any match →
  Expected: spread net 0 (the file matched before and matches still).
- [ ] Take a file that matches, and make a **whitespace-only** change → Expected: net 0.
- [ ] Confirm a file the branch did **not** touch at all never appears in the diff, in
  either direction.

### `regex_spread` has no multi-line caveat

**Preconditions:** a pattern containing a newline, e.g. `pattern = 'start\nend'`, on both
a `regex_count` and a `regex_spread` metric.

- [ ] Add a matching two-line block on a branch, run `tingle stat --diff` → Expected:
  `regex_count` shows **0** in the diff columns while its Total is non-zero (the
  documented per-line caveat); `regex_spread` shows **`+1`** and agrees with its Total.
- [ ] Same check with `flags = ["DOTALL"]` → Expected: `regex_spread` behaves the same in
  the diff as in the full run.

---

## `ignore_lines` on the spread types

**Preconditions:** a metric with `ignore_lines`, e.g.

```toml
[[metrics]]
name = "any-spread"
type = "symbol_spread"
symbol = "ANY"
ignore_lines = ['"form":\s*ANY']
```

- [ ] A file whose **every** hit is excused → Expected: does **not** count, and does not
  appear among occurrences.
- [ ] A file with one excused hit and one real hit → Expected: counts **once**, and its
  occurrence points at the **real** hit, not the excused one.
- [ ] On a branch, add only an **excused** hit to a clean file → Expected: spread net
  **0** (excusing happens before the collapse, on both sides).
- [ ] Remove the excusing pattern from the config and rerun → Expected: the file now
  counts.

---

## `tingle check` — gating on containment

**Preconditions:** a spread metric configured, and the churn branch from above.

- [ ] Run `tingle check` on a branch that only reworks already-matching code → Expected:
  the spread metric contributes **0**; if it is the only metric, exit **0** and the
  success line prints.
- [ ] Run `tingle check` on a branch that adds one new matching file → Expected: exit
  **1**, and the spread metric is listed with `+1` and the file path.
- [ ] Set `[check] policy = "any"` and confirm a `+1` spread fails even when other
  metrics improved.
- [ ] Add the spread metric to `[check] ignore` → Expected: it neither fails the build
  nor appears in the output.
- [ ] Confirm the sum in the failure line accounts for the spread metric exactly once.

---

## Registry surface — `list`, `add`, JSON

### Both types are discoverable

- [ ] Run `tingle list --types` → Expected: `regex_spread` and `symbol_spread` appear,
  alphabetically among the rest, each with a description mentioning **spread**.
- [ ] Check their Required/Optional param columns → Expected: identical to `regex_count`
  and `symbol_uses` respectively (`pattern` + `flags`, `ignore_lines`; `symbol` +
  `ignore_lines`).
- [ ] Run `tingle list --types` with **no config file present** → Expected: still works.

### `add` binds the positional value

- [ ] Run `tingle add regex_spread '#\s*hack' --name hack-spread` → Expected: writes a
  `[[metrics]]` block with `type = "regex_spread"` and `pattern = '#\s*hack'`; existing
  file formatting and comments preserved.
- [ ] Run `tingle add symbol_spread 'app.legacy.OldClient'` with no `--name` → Expected:
  an auto-name derived from the type and value, not colliding with existing names.
- [ ] Run `tingle add regex_spread` with **no** value → Expected: the required-param
  error, same as `regex_count`.
- [ ] Run `tingle stat` afterwards → Expected: the added metric measures immediately.
- [ ] Revert the added blocks.

### JSON: `value` and `details` deliberately disagree

- [ ] Run `tingle report --json` → Expected: `type-ignore-spread` has `"value": 3` while
  its `"details"` maps **files to hit counts** and sums to **4**.
- [ ] Confirm `type-ignores` in the same output has `"value": 4` and details summing to
  4 — the two metrics share identical details and differ only in `value`.
- [ ] Run `tingle stat --json` → Expected: `"details"` is `null` for both (unchanged
  behaviour — `stat` does not carry details).
- [ ] Read the `"occurrences"` in `tingle report --json` for the spread metric →
  Expected: three entries, each a file with the line of its first hit.
- [ ] Run `tingle report --cobertura` → Expected: still valid XML, spread metrics
  included without breaking the schema.

---

## Report, TUI, and editor links

- [ ] Run `tingle report --metric type-ignore-spread` → Expected: the description prints,
  and each occurrence renders as `path:line`.
- [ ] Open the TUI (`tingle`) → Expected: the spread metric appears in its group, the
  group sum includes it, emoji ranking works as for any other metric.
- [ ] In the TUI, select a spread occurrence and press ++space++ → Expected: opens the
  file at the first hit's line in VS Code.
- [ ] In `report --diff`, select a spread occurrence (bare path, no line) → Expected:
  opens the file at the top, no crash from the missing line.

---

## Regressions — the shared finder refactor

`regex_count` and `symbol_uses` were refactored to share their finder with the new
spread types. Their behaviour must be **unchanged**.

- [ ] Run `tingle stat` on this branch and on `main`, compare every metric value →
  Expected: identical except for the newly added `type-ignore-spread` row.
- [ ] Run `tingle report --metric type-ignores` on both → Expected: byte-identical
  occurrence lists.
- [ ] Run `tingle report --metric any-uses` on both → Expected: identical, including the
  `ignore_lines` exclusion of `CheckPolicy.ANY`.
- [ ] Run `tingle stat --diff` on a branch with real changes on both → Expected:
  identical Added/Removed/Net for every pre-existing metric.
- [ ] Trigger a `symbol_uses` **star-import** warning and a **syntax-error** warning on a
  diff → Expected: wording still reads `<path>: <side> side skipped (syntax error: …)`
  for `symbol_uses_diff` (unchanged); the new spread types use
  `<path>: <side> side: <message>` (new, and consistent between warning kinds).

---

## Cross-cutting

- [ ] A spread metric whose range matches **no files** → Expected: value 0, 🎉, no crash.
- [ ] A spread metric over a range containing **binary/unreadable** files → Expected: the
  file is skipped with the usual warning and does not count.
- [ ] A per-metric failure in a spread metric → Expected: the run completes, that metric
  shows `ERROR`, others are unaffected, exit 1 not a crash.
- [ ] `tingle stat --diff` in a **shallow clone** → Expected: the documented merge-base
  failure, not a spread-specific error.
- [ ] Run the automated suite as a backstop: `mise run test:py`, `mise run lint:py`,
  `mise run docs:build` → Expected: all green.

---

**Highest-risk, least-machine-covered** items: the **churn-nets-zero** scenario end to
end on a real branch (unit tests assert it, but only against synthetic file contents —
see it once against real git history), the **rename** case (delete + add is an
approximation the unit tests do not exercise), and the **`main` vs branch value
comparison** confirming the shared-finder refactor changed nothing. The collapse
arithmetic, crossing directions, and `ignore_lines` interaction are thoroughly unit
tested — trust those more.

Ignore the `shitcheck` task inherited from the shared task config — tingle replaces it.
The equivalent gate here is `tingle check`, against the `noqa-comment`, `type-ignores`
and `any-uses` metrics the root `tingle.toml` already carries.
