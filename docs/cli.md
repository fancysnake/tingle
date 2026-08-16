# CLI reference

Reports go to stdout; warnings and per-metric errors go to stderr, so
`tingle stat --json | jq .` stays clean.

## Selecting what to measure

`--metric NAME` and `--group NAME` narrow `tingle`, [`stat`](#tingle-stat),
[`check`](#tingle-check) and [`report`](#tingle-report) to part of the
config — the metric you are working on, or the group you are working
through:

```console
$ tingle report --group linting
$ tingle report --metric noqa-comments
```

Both repeat, and naming both is a union: `--group linting --metric loc`
measures the linting group plus one metric from outside it. A name no
metric or group in the config carries is a usage error (exit 2), so a typo
cannot pass for a clean report.

## `tingle`

Interactive mode on a terminal; the static summary table otherwise (CI,
pipes).

The TUI is one table. Group headers, the metrics under them and — once a
metric is unfolded — what it measures and every hit it located are all
rows in it, indented into an outline:

```text
  Group / Metric        Type              Value
▾ linting                                 🚧 24
    noqa-comment        regex_count       🎉  0
  ▾ pylint-comment      regex_count       🚧  4
      lint escapes we still carry
      ranges: python
      src/mills/runner.py:1
      src/mills/diff.py:12
```

| Key | Action |
|---|---|
| `↑` / `↓` (`k` / `j`) | move the cursor between rows |
| `→` / `←` (`l` / `h`) | unfold / fold — from a hit, `←` folds the metric above it |
| ++space++ / ++enter++ | fold or unfold the row — or, on a located hit, open it |
| `f` | fold or unfold every group at once, leaving each metric as it is |
| `/` | search |
| `g` `n` `t` `v` `c` | sort by group, name, type, value, score |
| `G` `N` `T` `V` `C` | the same sorts, the other way up |
| `0` | clear the sort |
| `p` | command palette |
| `q` | quit |

Each group and metric folds independently. Unfolding a metric shows what
it measures, the ranges it measures over, and its occurrences. A metric
that failed shows its error there too. With no groups configured the
metrics are the top level, and `f` folds those instead. A group with
nothing to report — no hits at all, or, in a diff, a branch that moved
nothing — starts folded, unless it holds an error.

Move onto an occurrence and press ++space++ or ++enter++ to **open it in
VS Code** — the file at its line, in the window you are already in. This
works from VS Code's integrated terminal, which puts the `code` command on
`PATH`; run elsewhere, the key just says there is no editor to open into.

### Sorting

Sorts stack, most recent first, so consecutive keys compose: `n` then `t`
gives type-major order with names ordered inside each type. Pushing a key
already in the stack moves it to the front rather than repeating it, so
asking for it the other way up turns that sort over in place.

The lowercase key sorts upwards and the shifted one downwards. The header
of the column deciding the order carries ▲ or ▼ — `value` and `score`
share a column, and either can be pointing either way. A line under the
table names the whole stack.

`value` is the raw count, `score` the same number against the metric's own
guide. They answer different questions: what is biggest, and what is
worst. Only `score` compares metrics with different guides.

**Sorting by anything but `group` drops the group headers**, since the
metrics no longer nest under one: every row names its own group instead.
Folding stays — sort by `value`, then unfold the top row to see the files
behind the number. `0` brings the headers and the config order back.

### Search

`/` opens a query box. Matching is case-sensitive substring, against
everything a metric says about itself — its name, its group's, its
description and its range names — and against the path of every one of
its occurrences, whether or not that occurrence is on screen. Searching a
fully folded tree finds files inside it.

What a match reveals depends on where it was found. Matched on a name or
a group, the metric is left exactly as you had it: the row already shows
why it is there. Matched on a description or a range name, the metric
opens to show those words. Matched through its files, it opens showing
**only** the files that matched.

Folding during a search is respected while the query stands, and forgotten
with it. ++enter++ hands the rows back without giving up the query, so you
can fold and open hits inside a search; ++escape++ leaves, restoring the
outline exactly as it was.

`tingle --diff [--base REF]` opens the [branch-impact](diff.md) view.

Options: `--version`, `--diff`, `--base REF`, `--config PATH`, `--metric
NAME`, `--group NAME`.

## `tingle stat`

The compact summary — values only.

| Option | Meaning |
|---|---|
| `--json` | machine-readable output; values only, no occurrences or per-file details (use [`report --json`](#tingle-report) for those); diff JSON includes the resolved base ref and merge-base sha |
| `--diff` | measure the current branch's impact instead |
| `--base REF` | base branch for `--diff` (implies `--diff`) |
| `--config PATH` | path to the config file |
| `--metric NAME` | run only the named metric (repeatable) |
| `--group NAME` | run only the metrics in the named group (repeatable) |

## `tingle check`

The [CI gate](check.md): measure the branch, exit 1 if it worsened the
metrics, and print only the lines it added under the metrics that grew.

A branch that took on no debt says so, rather than passing in silence — in a
CI log, no output cannot be told apart from a step that never ran:

```console
$ tingle check
🎉 no new debt: 11 metrics against main
```

| Option | Meaning |
|---|---|
| `--policy sum\|any` | override the configured `[check]` policy for this run |
| `--base REF` | base branch to compare against |
| `--config PATH` | path to the config file |
| `--metric NAME` | run only the named metric (repeatable) |
| `--group NAME` | run only the metrics in the named group (repeatable) |

## `tingle report`

The full report: every occurrence with file and line
(`src/api/views.py:23`), or the actual list entries for the config-list
metrics (`pyproject.toml: E501`).

In diff mode occurrences are signed and colored (`+` added, `-` removed);
for list metrics you see *which* rules changed.

| Option | Meaning |
|---|---|
| `--json` | machine-readable output, occurrences and per-file details included |
| `--cobertura` | Cobertura XML, each occurrence line marked uncovered — GitLab MR widgets, Jenkins, and diff-cover consume it directly (line-scoped metrics only; others are noted on stderr) |
| `--diff` | measure the current branch's impact instead |
| `--base REF` | base branch for `--diff` (implies `--diff`) |
| `--config PATH` | path to the config file |
| `--metric NAME` | run only the named metric (repeatable) |
| `--group NAME` | run only the metrics in the named group (repeatable) |

`--cobertura` reports the whole tree, so it cannot be combined with `--json`,
`--diff`, or `--base`; doing so is a usage error.

## `tingle add`

Append a metric to the config.

```console
$ tingle add TYPE [VALUE]
```

The positional `VALUE` binds to the type's primary param — the pattern for
`regex_count`, the key for `toml_list_length`, and so on. See [Metric
types](metrics.md).

| Option | Meaning |
|---|---|
| `--name NAME` | metric name (auto-generated and de-duplicated if omitted) |
| `--range NAME` | target range (repeatable) |
| `--group NAME` | group heading to show this metric under |
| `--description TEXT` | what the metric means, in prose |
| `--param key=value` | extra metric param (repeatable) |

Without `--name`, the metric is named after its type and value
(`regex_count-noqa`), with a `-2`, `-3`, … suffix if that name is taken.

The new metric is validated against the merged config before anything is
written. It targets `tingle.toml` (created if needed), or `[tool.tingle]` in
`pyproject.toml` if that is where your config already lives. Formatting and
comments in the file are preserved.

!!! note "`--param` values are strings"

    Every `--param` value is written to the config as a string, so the params
    that want a list or a boolean — `regex_count`'s `flags` and
    `toml_table_array`'s `explode` — cannot be set this way. Add the metric
    without them, then write them into the TOML by hand.

Types with no positional param (`ini_list_length`, `file_count`,
`line_count`) reject a `VALUE`; set what they need with `--param`.

## `tingle init`

Create a commented starter `tingle.toml` in the current directory. Refuses
to overwrite an existing one. No options.

## `tingle list`

List the configured metrics.

| Option | Meaning |
|---|---|
| `--types` | list the available metric types and their params instead (works without a config) |
| `--config PATH` | path to the config file |

## Exit codes

| Code | Meaning |
|---|---|
| `0` | metrics ran (warnings allowed) |
| `1` | a metric function failed (the others still run and report), or `tingle check` judged the branch a regression |
| `2` | config error, usage error, or a diff that could not be produced (unknown base ref, no merge-base) |

Outside of `check`, metric *values* never affect the exit code: tingle
measures, it does not judge.

## Migrating from ≤0.1

`tingle run` is now `tingle stat`, and `tingle diff` is `tingle stat --diff`
(summary) or `tingle report --diff` (locations).
