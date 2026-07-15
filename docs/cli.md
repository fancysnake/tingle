# CLI reference

Reports go to stdout; warnings and per-metric errors go to stderr, so
`tingle stat --json | jq .` stays clean.

## `tingle`

Interactive mode on a terminal; the static summary table otherwise (CI,
pipes).

The TUI is a three-level accordion of group → metric → file results,
navigated with the arrow keys. Groups and their metric rows (each showing
its stats) are visible at rest.

| Key | Action |
|---|---|
| `↑` / `↓` (`k` / `j`) | move between headers, and the occurrence lines of an unfolded metric |
| `→` / `←` (`l` / `h`) | unfold / fold the focused header |
| ++space++ / ++enter++ / click | toggle the focused header — or, on an occurrence line, open it |
| `f` | fold or unfold every group at once, leaving file results as they are |
| `p` | command palette |
| `q` | quit |

Each group and metric folds independently. Unfolding a metric shows its
occurrences in place. With no groups configured it is a flat accordion of
metrics, and `f` folds those instead.

Arrow down onto an occurrence and press ++space++ or ++enter++ to **open it
in VS Code** — the file at its line, in the window you are already in. This
works from VS Code's integrated terminal, which puts the `code` command on
`PATH`; run elsewhere, the key just says there is no editor to open into.

`tingle --diff [--base REF]` opens the [branch-impact](diff.md) view.

Options: `--version`, `--diff`, `--base REF`, `--config PATH`, `--metric
NAME`.

## `tingle stat`

The compact summary — values only.

| Option | Meaning |
|---|---|
| `--json` | machine-readable output; values only, no occurrences or per-file details (use [`report --json`](#tingle-report) for those); diff JSON includes the resolved base ref and merge-base sha |
| `--diff` | measure the current branch's impact instead |
| `--base REF` | base branch for `--diff` (implies `--diff`) |
| `--config PATH` | path to the config file |
| `--metric NAME` | run only the named metric (repeatable) |

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
