# tingle

> *Spider-sense for refactoring: you know that tingle — the itch that says
> the codebase isn't right yet. This tool puts a number on it, so you can
> watch it drop.*

Code metrics for the era of constant refactoring.

`tingle` measures things you want to shrink (or watch) while refactoring a
codebase: ignored lint rules, inline `# noqa` / `# type: ignore` comments,
uses of a legacy class during a strangler-fig migration, lines of code in a
package that should disappear.

It runs once, prints the numbers, and stores nothing — pipe the JSON into
whatever tracks history for you (CI artifacts, dashboards, a spreadsheet).

## Install

```console
$ pip install tingle
```

## Quick start

```console
$ tingle init                                    # starter tingle.toml
$ tingle add regex_count '#\s*noqa'              # add a metric from the CLI
$ tingle add toml_list_length tool.ruff.lint.ignore --name ruff-ignores
$ tingle                                         # interactive mode (on a terminal)
$ tingle stat                                    # summary table
$ tingle stat --json                             # machine-readable output
$ tingle stat --diff                             # impact of the current branch
$ tingle report                                  # every occurrence, file:line
$ tingle report --diff                           # what the branch added/removed
```

## What it does

Three things, in rising order of opinion:

- **[Measure](metrics.md).** `tingle stat` counts what you told it to count
  and prints the numbers. Metric values never affect the exit code — tingle
  measures, it does not judge.
- **[Attribute](diff.md).** `tingle stat --diff` measures only what the
  current branch changed, against the merge-base with a base branch, so
  commits that landed on the base after you branched don't pollute your
  numbers.
- **[Judge](check.md).** `tingle check` is the CI gate — the same branch
  measurement, but it exits 1 if the branch made things worse, so a pull
  request that takes on debt fails the build.

## Where to go next

- **[Configuration](configuration.md)** — `tingle.toml`, ranges, groups.
- **[Metric types](metrics.md)** — what you can count, and the limits of
  each counter.
- **[Branch impact](diff.md)** — how `--diff` attributes changes to your
  branch.
- **[CI gate](check.md)** — failing the build on new debt.
- **[CLI reference](cli.md)** — every command and flag.
