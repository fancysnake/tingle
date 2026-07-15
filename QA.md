# Manual Test Scenarios

Based on: `feature/display-guides` vs `main`
Changes in: **Severity emoji & density guide**, **Group summaries & folding (TUI)**,
**`ignore_lines`**, **`over_lines` on `file_count`**, **Metric descriptions**,
**`tingle check` success line**, **TUI focus fix**

Run commands from the repo root. This branch is **dogfooded** — `tingle.toml` in the
root exercises most of these features against tingle's own source. Note that the root
`tingle.toml` currently pins `[display] guide = 10` (uncommitted). Several scenarios
below ask you to remove that pin — do so in a scratch copy or `git stash`/restore it
after, since it's a deliberate local edit.

**Preconditions common to all:** built/installed tingle on this branch; a terminal that
renders emoji at 2 cells wide.

---

## Severity emoji & the density guide

### The ladder actually spreads across a real table

**Preconditions:** root `tingle.toml`, `[display] guide = 10` line **removed** (so the
derived density guide is used).

- [ ] Run `tingle stat` → Expected: every value is preceded by one of 🎉 🦠 🚧 🚨 🔥 💀,
  exactly one emoji per value, each drawn full-width (not clipped in half).
- [ ] Read across the metrics → Expected: they do **not** all show the same emoji; a
  metric with 0 hits shows 🎉, small counts show 🦠/🚧, larger ones climb.
- [ ] Run `tingle stat --json` → Expected: each metric has a `"guide"` field equal to
  `round(LOC/100)` for the codebase, floored at 1; not the literal 100.

### A pinned global guide overrides the density guide

**Preconditions:** root `tingle.toml` with `[display] guide = 10` present.

- [ ] Run `tingle stat --json` → Expected: **every** metric's `"guide"` is `10`,
  regardless of codebase size.
- [ ] Change to `guide = 100`, rerun → Expected: emoji get gentler (a value of 3 that
  read 🔥 against guide 10 now reads 🦠/🚧 against 100).
- [ ] Set `guide = 0` → Expected: config error refusing a non-positive guide (not a
  crash, not a silent divide-by-zero).
- [ ] Set `guide = "abc"` or `guide = 1.5` → Expected: config error naming `guide` as
  needing a positive whole number.

### A per-metric guide beats both

**Preconditions:** any config.

- [ ] Add `guide = 20000` to a `line_count` metric, keep `[display] guide = 10` →
  Expected: that metric is judged against 20000 (reads low/green even for thousands of
  lines), while other metrics still use 10.
- [ ] Run `tingle stat --json` → Expected: that one metric's `"guide"` is `20000`; the
  rest are `10`.

### The guide is always the top of 🚨, and the log scale bites early

**Preconditions:** a metric with a known count; set its `guide` equal to that exact count.

- [ ] Run `tingle stat` for `value == guide` → Expected: 🚨 (full-size debt, not yet
  past it).
- [ ] Set the guide to half the value → Expected: 🔥 or 💀 (past full size).
- [ ] With `guide = 100`, find/craft a metric reading exactly 3 → Expected: 🚧 (log makes
  3-of-100 already a quarter of the way up, harsher than a linear scale would show).

### loc_range controls what LOC is counted over

**Preconditions:** `[display] guide` **removed**; two ranges defined, e.g. `python`
(src+tests) and a narrower `python-src` (src only).

- [ ] Run `tingle stat --json`, note a metric's `guide` with no `loc_range` set →
  Expected: guide derived from the **default** range's LOC.
- [ ] Add `[display] loc_range = "python-src"`, rerun → Expected: guide is smaller (fewer
  lines counted), so emoji get harsher across the board.
- [ ] Set `loc_range = "does-not-exist"` → Expected: config error naming the unknown
  range (not a silent fallback).

### Empty / tiny project edge cases

- [ ] Point tingle at a nearly empty directory (a few lines, `guide` unset) → Expected:
  derived guide floors at 1 (never 0); a handful of markers reads harsh (🔥/💀) — density
  being honest, not a bug.
- [ ] A metric measuring 0 with any guide → Expected: 🎉, and no divide-by-zero even if
  the guide itself resolves to 0 (all-errored group).

---

## Group summaries & folding

### Group headers show the summed value and emoji (outline layout)

**Preconditions:** root `tingle.toml` (has `formatting`, `linting`, `typing` groups).

- [ ] Run `tingle stat` → Expected: **no** `Group` column; instead the table reads as an
  outline — each group name heads its own row (bold), its metrics indented two spaces
  beneath it, and a horizontal rule between one group's block and the next.
- [ ] Read a group heading row → Expected: it shows the **sum** of its metrics' values,
  led by an emoji ranking that sum against the summed guides. Because it sits on the named
  heading line (not a blank row with a stray number), it reads clearly as a total.
- [ ] Look down the `Value` column → Expected: every emoji sits in the **same column**;
  the numbers are right-padded with spaces so `🦠  2` and `🚨 23` line up under each other.
- [ ] Run `tingle report` → Expected: each `## <group>` heading carries the same summed
  value + emoji.
- [ ] Run `tingle stat --json` → Expected: metrics carry their `"group"`; the outline and
  sum are presentation only (verify by hand that group value == sum of members).
- [ ] Confirm a metric that **errored** is excluded from its group's sum (contributes no
  value and no guide), but the group heading and its row are still shown (`ERROR` in the
  value cell).
- [ ] With no groups configured at all → Expected: no group headings, no rules, metric
  names not indented — just the plain metric rows, values still emoji-led and aligned.
- [ ] Run `tingle stat --diff` → Expected: the same outline (no `Group` column); each
  group heading shows the net beside the standing total, and the `Total` column's emoji
  are aligned the same way.

### A zero-sum group starts folded in the TUI — unless it holds an error

**Preconditions:** a group whose metrics all measure 0 (e.g. `formatting` if no `# fmt`
etc. exist); run bare `tingle` in a TTY.

- [ ] Launch TUI → Expected: the all-zero group appears **folded** at start; its header
  still shows the `🎉 0` total (quiet, not hidden).
- [ ] A group with any non-zero metric → Expected: starts **unfolded**.
- [ ] Force a metric in an otherwise-zero group to error (e.g. point a `toml_list_length`
  at a bad key) → Expected: that group starts **unfolded** despite summing to zero,
  because it hides an error.

### Diff group headers show net beside standing total

**Preconditions:** a branch with changes vs base; `tingle stat --diff` and bare
`tingle --diff`.

- [ ] Run `tingle stat --diff` → Expected: group row shows the **net** change and the
  **standing total** (with emoji on the total). A group with +2/−2 (net 0) still shows the
  full standing total, and is marked changed.
- [ ] In the TUI diff, a group that moved nothing (net 0, no churn) → Expected: starts
  folded; one with churn (net 0 but +2/−2) → starts unfolded.

---

## `ignore_lines`

### Excusing placeholder hits

**Preconditions:** create a scratch file with:

```python
assert response == {"form": ANY, "id": 3}   # should be excused
assert result == ANY                        # should be counted
```

and a metric:

```toml
[[metrics]]
name = "any-uses"
type = "symbol_uses"
symbol = "ANY"
ignore_lines = ['"form":\s*ANY']
```

- [ ] Run `tingle report --metric any-uses` → Expected: value counts **only** the
  `result == ANY` line; the `"form": ANY` line does not appear among occurrences.
- [ ] Run `tingle report --json` for it → Expected: the excused line is absent from
  `occurrences` **and** leaves no trace in per-file `details`.
- [ ] Remove `ignore_lines`, rerun → Expected: both lines counted (value goes up by 1).
  Confirms the filter is what excused it.
- [ ] Apply `ignore_lines` to a `regex_count` metric too → Expected: same behavior (both
  types honor it).
- [ ] Give `ignore_lines` an invalid regex → Expected: config error naming the bad
  pattern, not a stack trace at run time.
- [ ] A pattern matching **every** line → Expected: value 0, no occurrences, no error.

---

## `over_lines` on `file_count`

### Counting only oversized files

**Preconditions:** a range containing files of known lengths; a metric:

```toml
[[metrics]]
name = "big-files"
type = "file_count"
over_lines = 100
```

- [ ] Run `tingle report --metric big-files` → Expected: counts only files with
  **strictly more than** 100 lines; a file with exactly 100 lines is **not** counted.
- [ ] Inspect occurrences / `--json details` → Expected: each counted file is listed with
  its line count recorded.
- [ ] Remove `over_lines`, rerun → Expected: counts **all** files in the range (plain file
  count).
- [ ] Set `over_lines = 0` / negative / non-integer → Expected: sensible config
  validation (0 effectively counts non-empty; non-integer errors) — confirm no crash.
- [ ] Confirm a `file_count` **without** `over_lines` opens no files (fast path) — sanity:
  it still returns the right count on a range with binary/unreadable files present.

### over_lines in a diff crosses the threshold both ways

**Preconditions:** branch where one file grows past `over_lines` and another shrinks back
under it.

- [ ] Run `tingle stat --diff --metric big-files` → Expected: the file crossing **up**
  counts as added debt (+1); the file crossing **down** counts as paid off (−1); files
  that stay on the same side don't move the count.

---

## Metric descriptions

**Preconditions:** add `description = "Untyped escape hatches. Prefer a real type."` to a
metric (or use `tingle add … --description "…"`).

- [ ] Run `tingle report` → Expected: the description prints under that metric,
  dimmed/italic; metrics without one are unchanged.
- [ ] Run `tingle report --json` and `tingle stat --json` → Expected: `"description"`
  field present (value or `null`).
- [ ] Run `tingle add regex_count '#\s*hack' --name hacks --description "…"` → Expected:
  the written TOML block includes the `description` key; `tingle stat` then shows it.
- [ ] `tingle stat` table (not report) → Expected: description does **not** clutter the
  compact table.

---

## `tingle check` success line

**Preconditions:** a branch that does **not** worsen metrics vs base.

- [ ] Run `tingle check` on a clean branch → Expected: exit 0 **and** a printed line
  `🎉 no new debt: N metrics against <base>` (no longer silent).
- [ ] Run on a branch that pays off debt → Expected: `🎉 no new debt, and K paid off: …`.
- [ ] Run on a branch that adds debt → Expected: exit 1, the worsened metrics with `+`
  occurrences, and **no** success line.
- [ ] Confirm singular/plural: a config with exactly one judged metric → `1 metric`, not
  `1 metrics`.
- [ ] Confirm the base named in the line matches `--base` / `[diff] base` / `main`
  resolution.

---

## TUI focus & navigation (regression)

**Preconditions:** bare `tingle` in a real terminal (the fix is about mouse focus, so this
needs manual clicking).

- [ ] Launch, then press ↑/↓ → Expected: focus moves between group/metric headers; →/←
  unfold/fold; Space toggles; `hjkl` mirror the arrows.
- [ ] **The fix:** click the **empty space below** the metric rows, then press ↑/↓ →
  Expected: arrows still **navigate** headers (they must not turn into scroll — this was
  the bug).
- [ ] Switch focus to another terminal window and back (click to refocus the window on
  empty space), then press arrows → Expected: navigation still works without first
  clicking a row.
- [ ] Press `f` to fold all groups, then arrows → Expected: focus lands on a still-visible
  enclosing header and arrows keep working (focus not lost into a hidden widget); `f`
  again unfolds.
- [ ] Press `p` → command palette opens and its own result list responds to arrows (the
  app arrows don't steal them); `q` quits.
- [ ] Metric name / range containing `[` (craft one) → Expected: rendered literally in the
  TUI, not swallowed as Textual markup.

---

## Cross-cutting regressions

- [ ] `tingle stat`/`report` with **no** groups configured → Expected: output shape
  unchanged from pre-feature (no empty `Group` column, no headings), just with emoji added
  to values.
- [ ] `tingle report --cobertura` → Expected: still emits valid XML; emoji/guide changes
  don't leak into it.
- [ ] A per-metric failure (one broken metric) → Expected: the run still completes, that
  metric shows `ERROR`, its group shows but excludes it from the sum, exit code reflects a
  metric failure (1) not a crash (2).
- [ ] Run the automated suite as a backstop: `mise run test:py`, `mise run lint:py`, and
  `tingle check` on the branch → Expected: all green (confirms the manual surface matches
  what CI asserts).

---

**Highest-risk, least-machine-covered** items — the three that need a real terminal and a
mouse: **the empty-space click focus fix**, **emoji width (no half-drawn glyphs)**, and
**fold-all not losing focus**. Automated tests can't click or measure font rendering, so
give those extra attention. The density-guide math is well unit-tested (including the 94k
dataset as a regression), so trust it more — but do the one end-to-end check that the
pinned-vs-derived guide actually flips the JSON `guide` field, since that's the seam
between config and display.
