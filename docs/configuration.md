# Configuration

tingle looks for `tingle.toml` in the current directory first, then for a
`[tool.tingle]` section in `pyproject.toml`. `tingle.toml` wins if both
exist. `--config PATH` overrides discovery. The project root — where files
are scanned from — is the config file's directory.

`tingle init` writes a commented starter `tingle.toml` (it refuses to
overwrite an existing one).

```toml
[ranges.python]
include = ["src/**/*.py", "tests/**/*.py"]
exclude = ["src/generated/**"]
default = true               # metrics without a range key use this range

[ranges.js]
include = ["frontend/**/*.js", "frontend/**/*.ts"]

[[metrics]]
name = "noqa-comments"
type = "regex_count"
range = "python"             # single range...
pattern = '#\s*noqa'

[[metrics]]
name = "todo-comments"
type = "regex_count"
ranges = ["python", "js"]    # ...or several: the union of matched files
group = "lint"               # optional heading to show related metrics under
pattern = '\bTODO\b'
```

## Ranges

A range is a named file set: `include` globs minus `exclude` globs.

`.git/`, `.venv/`, `__pycache__/`, `node_modules/`, `dist/`, `.tox/`, and
`.mise/` are always excluded.

At most one range may set `default = true`; it applies to metrics that
specify neither `range` nor `ranges`. With no default range configured, such
metrics use all (non-excluded) files.

A metric takes `range = "python"` for one range, or `ranges = ["python",
"js"]` for the union of the files they match.

!!! note

    The config-file metric types (`toml_list_length`, `toml_table_array`,
    `ini_list_length`) read a named file relative to the project root and
    ignore ranges entirely. See [Metric types](metrics.md).

## Groups

Any metric may set `group = "<name>"`. Grouping is presentation only —
values, occurrences, and warnings are unchanged — but every human view
collects grouped metrics together:

- `tingle report` prints a `## <name>` heading per group.
- The summary tables gain a `Group` column.
- The interactive TUI nests each group as its own foldable section.

Metrics keep config order within a group, groups appear in first-mention
order, and anything ungrouped trails last. With no groups configured
anywhere, output is exactly as it is without the feature.

Add a grouped metric from the CLI with `--group`:

```console
$ tingle add regex_count '#\s*type:\s*ignore' --name type-ignores --group typing
```

## Counting ignored lint rules

There is no per-linter magic; point the generic types at the config files
your linters actually use:

```console
$ tingle add toml_list_length tool.ruff.lint.ignore --name ruff-ignores
$ tingle add toml_list_length 'tool.pylint.messages control.disable' --name pylint-disables
$ tingle add toml_list_length tool.mypy.disable_error_code --name mypy-disabled
$ tingle add ini_list_length --name pylintrc-disables \
    --param file=.pylintrc --param 'section=MESSAGES CONTROL' --param option=disable
```

## `[diff]`

Sets the default base branch for [branch impact](diff.md) measurements.

```toml
[diff]
base = "origin/main"
```

The base resolves as `--base` flag > `[diff] base` > `main`; if the ref does
not exist locally, `origin/<base>` is tried.

## `[check]`

Configures the [CI gate](check.md).

```toml
[check]
policy = "sum"        # or "any"
ignore = ["loc"]      # metrics that never fail the check
```

`policy = "sum"` (the default) fails when the metrics grow *in total*, so
paying off debt in one metric offsets taking it on in another. `policy =
"any"` fails when any single metric grows, whatever else improved.

`ignore` names metrics that are expected to grow — lines of code, say. They
take no part: they neither move the total nor fail the build, and they stay
out of the output. A name that matches no configured metric is a config
error, so a typo cannot silently ignore nothing.
