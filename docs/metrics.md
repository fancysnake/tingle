# Metric types

Every metric has a `type` from the table below, a `name`, and the params its
type requires. `tingle list --types` prints the same table from your
installed version, and works without a config file.

| Type | Params | Counts |
|---|---|---|
| `regex_count` | `pattern` (positional), `flags`, `ignore_lines` | regex matches in the range's files |
| `regex_spread` | `pattern` (positional), `flags`, `ignore_lines` | files the regex matches in, however often |
| `symbol_uses` | `symbol` (positional), `ignore_lines` | references to a function/class in Python files |
| `symbol_spread` | `symbol` (positional), `ignore_lines` | Python files referencing it, however often |
| `toml_list_length` | `key` (positional), `file` = `pyproject.toml` | entries of the list at a dotted TOML key |
| `toml_table_array` | `key` (positional), `file` = `pyproject.toml`, `label`, `explode` | entries of a TOML array of tables (e.g. `[[tool.mypy.overrides]]`) |
| `ini_list_length` | `file`, `section`, `option` | comma/newline-separated entries of an INI option |
| `file_count` | `over_lines` | files in the range, or only those longer than `over_lines` |
| `line_count` | — | lines in the range's files |

The **positional** param is what `tingle add TYPE VALUE` binds its `VALUE`
argument to. Everything else is set with `--param key=value`, repeatable —
except the two params that are not strings, `flags` and `explode`, which
[`add` cannot write](cli.md#tingle-add): put those in the TOML yourself.

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

## Excusing lines with `ignore_lines`

The four regex and symbol types all accept `ignore_lines`: a list of regexes
matched against the **line a hit sits on**. Any hit on a matching line is not
counted, does not appear among the occurrences, and leaves no trace in the
per-file details.

Some uses of a thing are not debt, and no range glob can separate them —
they live on different lines of the same file. `ANY` in an assertion is real
debt; `ANY` standing in for a form that cannot be compared is not:

```toml
[[metrics]]
name = "any-uses"
type = "symbol_uses"
symbol = "ANY"
ignore_lines = ['"form":\s*ANY']
```

```python
assert response == {"form": ANY, "id": 3}   # excused
assert result == ANY                        # counted
```

A pattern is searched **anywhere in the line**, so it needs no anchoring and
indentation cannot defeat it. Both sides of a [diff](diff.md) are filtered
against their own text, so a line excused on the branch is equally excused in
the base — otherwise the net would count a removal it never counted as an
addition.

!!! note "Multi-line matches are tested on their first line"

    A `regex_count` match is located at the line it *starts* on, so that is
    the only line `ignore_lines` sees.

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

## Spread: `regex_spread` and `symbol_spread`

`regex_count` and `symbol_uses` measure **volume** — how many times a thing is
written. `regex_spread` and `symbol_spread` run the same search and measure
**reach** — how many files it has got into. A file with forty matches counts
once, exactly like a file with one.

```toml
[[metrics]]
name = "legacy-arch"
type = "symbol_spread"
symbol = "myapp.legacy.OldBase"
```

Every param works as it does on the counting sibling: `pattern`, `flags` and
`ignore_lines` on `regex_spread`, `symbol` and `ignore_lines` on
`symbol_spread`, with the same positional argument for `tingle add`.

### Why you would want the smaller number

Volume is the wrong measure when the goal is containment rather than removal.
Fixing a bug in a legacy module rewrites lines that already counted, so a
counting metric jumps and [`tingle check`](check.md) fails a branch that spread
nothing. Meanwhile a branch that adds one fresh import of the old base class in
a brand-new file barely moves the number at all — though that is the thing you
actually wanted to stop.

A spread metric inverts both. The bug fix nets zero. The new file is +1.

### In a diff, what counts is crossing

The spread types do not measure the branch the way the counting types do. There
is no line-by-line matching: both sides of every changed file are read whole and
re-analysed, and what counts is **crossing**.

- A file that matches now and did not at the merge-base: **+1**.
- A file that matched then and does not now: **−1**.
- A file that matched before and matches still: **0**, however much of it the
  branch rewrote.

Creating a file that matches, and deleting one that did, fall out of the same
comparison — a created file has no base side, a deleted one no current side.
Only changed files are examined, which is sound: a match cannot appear in a file
the branch never touched.

```console
$ tingle stat --diff
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━┳━━━━━┳━━━━━━━┓
┃ Metric        ┃ Type          ┃ Added ┃ Removed ┃ Net ┃ Total ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━╇━━━━━╇━━━━━━━┩
│ legacy-uses   │ symbol_uses   │    +8 │      -3 │  +5 │ 💀 11 │
│ legacy-arch   │ symbol_spread │    +1 │       0 │  +1 │ 🔥  3 │
└───────────────┴───────────────┴───────┴─────────┴─────┴───────┘

$ tingle report --diff --metric legacy-arch
legacy-arch (symbol_spread): +1 / -0 (net +1)
  + src/d.py
```

One branch, two readings of it: eight references added and three removed, all
but two of them churn inside files that already used the class — and exactly one
file newly reaching for it.

!!! note "`regex_spread` has no multi-line caveat"

    Because both sides are matched full-text, a pattern containing a newline
    works in diff mode exactly as it does in the Total column, and
    `MULTILINE` / `DOTALL` mean the same thing in both. The
    [warning above](#regex_count) about `regex_count` in diff mode does not
    apply here.

### `ignore_lines` and the report

Excusing happens before the collapse, so a file whose every hit is excused does
not count at all, while a file with one hit left over still counts once.

Each counted file is reported at its **first** hit, so `tingle report` gives a
line to open:

```console
$ tingle report --metric legacy-arch
legacy-arch (symbol_spread): 🔥 3
  src/a.py:1
  src/b.py:1
  src/d.py:1
```

The per-file **hit** count is kept in the `details` of `tingle report --json`, so
the machine-readable output still says how heavily each file is involved, not
merely that it is. For a spread metric those details therefore sum to more than
the value — three files holding eleven references between them is `"value": 3`
with details summing to 11. That is deliberate, and it is the one place the two
disagree.

It also means a spread metric and its counting sibling emit **identical**
details and differ only in `value`, which is the cleanest way to see what the
collapse did.

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

A key that carries on past an *array of tables* means it once per entry,
and the entries' values are counted together — so one key reaches
`ignore_imports` in every import-linter contract at once:

```toml
key = "tool.importlinter.contracts.ignore_imports"
```

A contract stating none contributes nothing, rather than one.

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

Files in the metric's ranges, and total lines in those files. The
[range](configuration.md#ranges) is the whole definition. Point them at a
package that should disappear.

```toml
[[metrics]]
name = "legacy-loc"
type = "line_count"
range = "legacy-package"
```

`line_count` is the usual candidate for `[check] ignore` — lines of code are
expected to grow. See the [CI gate](check.md).

### Counting only the oversized files

`file_count` takes an optional `over_lines`: a gate that counts **only the
files longer than it**. It answers "how many files are over 1k lines", which
neither metric could on its own — `line_count` sums its per-file
measurements into one total, and a plain `file_count` counts everything.

```toml
[[metrics]]
name = "huge-files"
type = "file_count"
over_lines = 1000
guide = 5
```

The gate is **strict**: `over_lines = 1000` counts a file of 1001 lines, not
one of exactly 1000. Each counted file carries its length, so `tingle report`
says by how much a file is over, not merely that it is:

```console
$ tingle report --metric huge-files
huge-files (file_count): 🚨 2
  src/legacy/api.py: 1420 lines
  src/legacy/models.py: 1077 lines
```

In a [diff](diff.md), what counts is **crossing** the gate rather than being
created: a file that grows past it is new debt though it already existed, and
one refactored back under it is debt paid off. Creating a file above the gate
and deleting an oversized one fall out of the same comparison.

Without `over_lines`, `file_count` behaves exactly as before and opens no
files at all.

## The config-file types read files, not ranges

`toml_list_length`, `toml_table_array`, and `ini_list_length` read the file
named by their `file` param, resolved relative to the project root. They
ignore ranges completely — setting `range` on one has no effect.
