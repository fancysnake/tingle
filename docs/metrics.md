# Metric types

Every metric has a `type` from the table below, a `name`, and the params its
type requires. `tingle list --types` prints the same table from your
installed version, and works without a config file.

| Type | Params | Counts |
|---|---|---|
| `regex_count` | `pattern` (positional), `flags` | regex matches in the range's files |
| `symbol_uses` | `symbol` (positional) | references to a function/class in Python files |
| `toml_list_length` | `key` (positional), `file` = `pyproject.toml` | entries of the list at a dotted TOML key |
| `toml_table_array` | `key` (positional), `file` = `pyproject.toml`, `label`, `explode` | entries of a TOML array of tables (e.g. `[[tool.mypy.overrides]]`) |
| `ini_list_length` | `file`, `section`, `option` | comma/newline-separated entries of an INI option |
| `file_count` | — | files in the range |
| `line_count` | — | lines in the range's files |

The **positional** param is what `tingle add TYPE VALUE` binds its `VALUE`
argument to. Everything else is set with `--param key=value`, repeatable.

## `regex_count`

Counts regex matches across the files in the metric's ranges.

```toml
[[metrics]]
name = "noqa-comments"
type = "regex_count"
pattern = '#\s*noqa'
flags = ["IGNORECASE"]
```

`flags` accepts `IGNORECASE`, `MULTILINE`, and `DOTALL`. Invalid patterns
are rejected at config validation time, not at run time.

!!! warning "Diff mode counts per line"

    Patterns containing newlines never match in [diff mode](diff.md), so the
    Total column can disagree with the diff columns for such patterns.

## `symbol_uses`

Counts references to a function or class in Python files — the metric for
watching a strangler-fig migration retire a legacy class.

```toml
[[metrics]]
name = "legacy-client"
type = "symbol_uses"
symbol = "myapp.legacy.OldClient"
```

This is static analysis, and the distinction between a dotted and a bare
symbol matters:

- A **dotted symbol** (`myapp.legacy.OldClient`) follows import bindings —
  plain, aliased, `from`-imports, and best-effort relative imports — and
  counts the import of the symbol itself as one use. Attribute chains count
  once.
- A **bare symbol** (`OldClient`) counts every same-named name or attribute,
  which can overcount.

`from x import *` falls back to bare counting for that file, with a warning.
Re-exports, string references, and `getattr` are invisible to it.

## `toml_list_length`

The length of the list at a dotted key in a TOML file — how you count
ignored lint rules.

```toml
[[metrics]]
name = "ruff-ignores"
type = "toml_list_length"
key = "tool.ruff.lint.ignore"
file = "pyproject.toml"      # the default
```

If the key holds a *table of lists* (ruff's `per-file-ignores`, say), the
lengths are summed.

A missing file, a missing key, or malformed content is a warning plus a
value of 0 — not an error. The file may legitimately not exist yet.

## `toml_table_array`

Counts the tables of a TOML array of tables, such as
`[[tool.mypy.overrides]]`.

```toml
[[metrics]]
name = "mypy-overrides"
type = "toml_table_array"
key = "tool.mypy.overrides"
label = "module"
explode = true
```

`label` names a field used to describe each occurrence, so the report reads
`pyproject.toml: foo.*` instead of a raw dict. A list-valued label is joined
with `, `.

By default one table counts as one. `explode = true` instead counts each
element of the label list separately — one override silencing five modules
counts as five. It requires `label`.

## `ini_list_length`

Entries of a comma- or newline-separated INI option. All three params are
required.

```toml
[[metrics]]
name = "pylintrc-disables"
type = "ini_list_length"
file = ".pylintrc"
section = "MESSAGES CONTROL"
option = "disable"
```

## `file_count` and `line_count`

Files in the metric's ranges, and total lines in those files. No params —
the [range](configuration.md#ranges) is the whole definition. Point them at
a package that should disappear.

```toml
[[metrics]]
name = "legacy-loc"
type = "line_count"
range = "legacy-package"
```

`line_count` is the usual candidate for `[check] ignore` — lines of code are
expected to grow. See the [CI gate](check.md).

## The config-file types read files, not ranges

`toml_list_length`, `toml_table_array`, and `ini_list_length` read the file
named by their `file` param, resolved relative to the project root. They
ignore ranges completely — setting `range` on one has no effect.
