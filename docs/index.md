# tingle

> *Spider-sense for refactoring: you know that tingle — the itch that says
> the codebase isn't right yet. This tool puts a number on it, so you can
> watch it drop.*

Code metrics for the era of constant refactoring.

`tingle` measures things you want to shrink (or watch) while refactoring a
codebase: ignored lint rules, inline `# noqa` / `# type: ignore` comments,
uses of a legacy class during a strangler-fig migration, lines of code in a
package that should disappear.

It runs once, prints the numbers, and stores nothing. To watch a number over
months, the [metrics-history action](history.md) records a point per commit
that lands and publishes a chart of them.

## Install

```console
pip install tingle
```

## Quick start

```console
tingle init                                    # starter tingle.toml
tingle library                                 # ready-made metrics for known tools
tingle add --base tingle.builtins.ruff.noqa_comment
tingle add regex_count '#\s*noqa'              # or state one yourself
tingle add toml_list_length tool.ruff.lint.ignore --name ruff-ignores
tingle                                         # interactive mode (on a terminal)
tingle stat                                    # summary table
tingle stat --json                             # machine-readable output
tingle stat --diff                             # impact of the current branch
tingle report                                  # every occurrence, file:line
tingle report --diff                           # what the branch added/removed
tingle report --group linting                  # one group, or --metric NAME
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
- **[Template library](library.md)** — ready-made metrics for the tools you
  already run, and publishing your own.
- **[Branch impact](diff.md)** — how `--diff` attributes changes to your
  branch.
- **[CI gate](check.md)** — failing the build on new debt.
- **[History](history.md)** — recording the numbers per commit and publishing
  a chart of them. [tingle's own][own] is the shape of the result.
- **[CLI reference](cli.md)** — every command and flag.

  [own]: history/chart/index.html
