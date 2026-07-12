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

**📖 Documentation: <https://fancysnake.github.io/tingle/>**

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

Metrics are declared in `tingle.toml` (or a `[tool.tingle]` section in
`pyproject.toml`):

```toml
[ranges.python]
include = ["src/**/*.py", "tests/**/*.py"]
default = true

[[metrics]]
name = "noqa-comments"
type = "regex_count"
pattern = '#\s*noqa'
```

You can count regex matches, uses of a Python symbol, entries in a TOML or
INI list (this is how you count ignored lint rules), files, and lines.
See the [metric types](https://fancysnake.github.io/tingle/metrics/).

## What it does

Three things, in rising order of opinion:

- **Measure.** `tingle stat` counts what you told it to count and prints the
  numbers. Metric values never affect the exit code — tingle measures, it
  does not judge.
- **[Attribute](https://fancysnake.github.io/tingle/diff/).** `tingle stat
  --diff` measures only what the current branch changed, against the
  merge-base with a base branch, so commits that landed on the base after
  you branched don't pollute your numbers.
- **[Judge](https://fancysnake.github.io/tingle/check/).** `tingle check` is
  the CI gate: the same branch measurement, but it exits 1 if the branch
  made things worse, so a pull request that takes on debt fails the build.

```console
$ tingle check
noqa-comment (regex_count): +2
  + src/api/views.py:23
  + src/api/views.py:41

$ echo $?
1
```

## Documentation

- [Configuration](https://fancysnake.github.io/tingle/configuration/) —
  `tingle.toml`, ranges, groups.
- [Metric types](https://fancysnake.github.io/tingle/metrics/) — what you
  can count, and the limits of each counter.
- [Branch impact](https://fancysnake.github.io/tingle/diff/) — how `--diff`
  attributes changes to your branch.
- [CI gate](https://fancysnake.github.io/tingle/check/) — failing the build
  on new debt.
- [CLI reference](https://fancysnake.github.io/tingle/cli/) — every command
  and flag.

## Development

Python 3.11–3.14 are supported (CI runs the full matrix). The project uses
[mise](https://mise.jdx.dev/) + Poetry.

```console
$ mise install
$ poetry install
$ mise run test:py      # tests
$ mise run lint:py      # ruff, mypy, pylint, import-linter
$ mise run docs:serve   # preview the docs site
```

See [contributing](https://fancysnake.github.io/tingle/contributing/) for
the GLIMPSE source layout and the layer contracts.

## License

MIT.
