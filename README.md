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

## Configuration

tingle looks for `tingle.toml` in the current directory first, then for a
`[tool.tingle]` section in `pyproject.toml`. `tingle.toml` wins if both
exist. `--config PATH` overrides discovery. The project root (where files
are scanned) is the config file's directory.

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

### Ranges

A range is a named file set: `include` globs minus `exclude` globs.
`.git/`, `.venv/`, `__pycache__/`, `node_modules/`, `dist/`, `.tox/`, and
`.mise/` are always excluded. At most one range may set `default = true`;
it applies to metrics without a `range`/`ranges` key. With no default
range, all (non-excluded) files are used.

### Metric types

| Type | Params | Counts |
|---|---|---|
| `regex_count` | `pattern` (positional), `flags` | regex matches in the range's files |
| `symbol_uses` | `symbol` (positional) | references to a function/class in Python files |
| `toml_list_length` | `key` (positional), `file` = `pyproject.toml` | entries of the list at a dotted TOML key |
| `toml_table_array` | `key` (positional), `file` = `pyproject.toml`, `label`, `explode` | entries of a TOML array of tables (e.g. `[[tool.mypy.overrides]]`) |
| `ini_list_length` | `file`, `section`, `option` | comma/newline-separated entries of an INI option |
| `file_count` | — | files in the range |
| `line_count` | — | lines in the range's files |

Notes and limitations:

- `regex_count` `flags` accepts `IGNORECASE`, `MULTILINE`, `DOTALL`.
  Invalid patterns are rejected at config validation time.
- `symbol_uses` is static analysis. A dotted symbol
  (`myapp.legacy.OldClient`) follows import bindings — plain, aliased,
  `from`-imports, and best-effort relative imports — and counts the import
  of the symbol itself as one use. Attribute chains count once. A bare
  symbol (`OldClient`) counts every same-named name/attribute, which can
  overcount. `from x import *` falls back to bare counting for that file
  with a warning. Re-exports, string references, and `getattr` are
  invisible.
- `toml_list_length` sums the lengths of a table of lists (e.g. ruff's
  `per-file-ignores`). Missing file/key or malformed content is a warning
  plus value 0, not an error — the file may legitimately not exist yet.
- `toml_table_array` counts the tables of an array of tables such as
  `[[tool.mypy.overrides]]`. `label` names a field used to describe each
  occurrence (`pyproject.toml: foo.*` instead of a raw dict); a
  list-valued label is joined with `, `. By default one table counts as
  one; `explode = true` (which requires `label`) instead counts each
  element of the label list separately.
- `ini_list_length` works on e.g. `.pylintrc`:
  `file = ".pylintrc"`, `section = "MESSAGES CONTROL"`, `option = "disable"`.
- `toml_list_length`, `toml_table_array`, and `ini_list_length` read the
  named file relative to the project root and ignore ranges.

### Groups

Any metric may set `group = "<name>"`. Grouping is presentation only —
values, occurrences, and warnings are unchanged — but every human view
collects grouped metrics together: the report listing prints a `##
<name>` heading per group, the summary tables gain a `Group` column, and
the interactive TUI nests each group as its own foldable section.
Metrics keep config order within a group, groups appear in first-mention
order, and anything ungrouped trails last. With no groups anywhere the
output is exactly as before. Add one with `--group`:

```console
$ tingle add regex_count '#\s*type:\s*ignore' --name type-ignores --group typing
```

### Counting ignored lint rules

There is no per-linter magic; point the generic types at the config your
linters actually use:

```console
$ tingle add toml_list_length tool.ruff.lint.ignore --name ruff-ignores
$ tingle add toml_list_length 'tool.pylint.messages control.disable' --name pylint-disables
$ tingle add toml_list_length tool.mypy.disable_error_code --name mypy-disabled
$ tingle add ini_list_length --name pylintrc-disables \
    --param file=.pylintrc --param 'section=MESSAGES CONTROL' --param option=disable
```

## Branch impact: `tingle diff`

Like diff-cover, but for your metrics: `tingle diff` measures only what
the current branch changed, compared against the merge-base with a base
branch — so commits that landed on the base after you branched don't
pollute your numbers. The working tree counts, including uncommitted
changes; untracked (non-ignored) files count as fully added.

```console
$ tingle stat --diff
                  /home/you/project vs main
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━┳━━━━━┳━━━━━━━┓
┃ Metric        ┃ Type             ┃ Added ┃ Removed ┃ Net ┃ Total ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━╇━━━━━╇━━━━━━━┩
│ noqa-comments │ regex_count      │    +3 │      -1 │  +2 │    13 │
│ ruff-ignores  │ toml_list_length │       │         │  +1 │     5 │
└───────────────┴──────────────────┴───────┴─────────┴─────┴───────┘
```

Red numbers mean the branch added debt; green means it removed some.
Lower is better. The Total column is today's full-repo value, for scale.

Each metric type has diff semantics:

| Type | Diff meaning |
|---|---|
| `regex_count` | matches on lines you added (+) vs lines you removed (−) |
| `symbol_uses` | references starting on added vs removed lines |
| `line_count` | added vs removed lines |
| `file_count` | created vs deleted files |
| `toml_list_length` / `toml_table_array` / `ini_list_length` | value at the merge-base vs now (net only) |

The base branch resolves as `--base` flag > `[diff] base` in the config
> `main`; if the ref doesn't exist locally, `origin/<base>` is tried.

```toml
[diff]
base = "origin/main"
```

Approximations to know about:

- Diff counting is **per line**: regex patterns containing newlines never
  match in diff mode (`MULTILINE`/`DOTALL` have no cross-line effect), so
  the Total column — which uses full-text matching — can disagree for
  such patterns.
- A `symbol_uses` reference is attributed to the line where it *starts*;
  edits to a later line of a multi-line call don't count it.
- Renames are treated as delete + add (net zero for line metrics; a
  renamed config file makes the value-delta metrics see a missing base).
- CI note: the merge-base needs history — shallow clones
  (`fetch-depth: 1`) will fail; fetch enough history or use
  `fetch-depth: 0`.

## CLI

- `tingle` — **interactive mode** on a terminal: a three-level accordion
  of group → metric → file results, navigated with the arrow keys. Groups
  and their metric rows (each showing its stats) are visible at rest; `↑`/`↓`
  move between headers, `→` unfolds and `←` folds the focused one (`hjkl`
  work too; Space or Enter/click toggles it), and each group and metric
  folds independently. `f` folds or unfolds every group at once, leaving
  the file results as they are.
  Unfolding a metric shows its occurrences in place. `p` opens the
  command palette, `q` quits. With no groups configured it is a flat
  accordion of metrics, and `f` folds those instead.
  `tingle --diff [--base REF]` opens the branch-impact view. When stdout
  is not a terminal (CI, pipes) the static summary table is printed
  instead.
- `tingle stat` — the compact summary. Options: `--json`, `--diff`,
  `--base REF` (implies `--diff`), `--config PATH`, `--metric NAME`
  (repeatable filter). Diff JSON includes the resolved base ref and
  merge-base sha.
- `tingle report` — the **full report**: every occurrence with file and
  line (`src/api/views.py:23`), or the actual list entries for the
  config-list metrics (`pyproject.toml: E501`). Same options as stat,
  plus `--cobertura`: Cobertura XML where each occurrence line is an
  uncovered line — GitLab MR widgets, Jenkins, and diff-cover consume it
  directly (line-scoped metrics only; others are noted on stderr).
  In diff mode occurrences are signed and colored (`+` added, `-`
  removed); for list metrics you see *which* rules changed.
- `tingle add TYPE [VALUE]` — append a metric to the config. The
  positional VALUE binds to the type's primary param (see table). Options:
  `--name`, `--range` (repeatable), `--group`, `--param key=value`
  (repeatable). The new metric is validated against the merged config
  before anything is written; names are auto-generated and de-duplicated
  when omitted.
  Targets `tingle.toml` (created if needed) or `[tool.tingle]` in
  `pyproject.toml` if that is where your config lives.
- `tingle init` — create a commented starter `tingle.toml` (refuses to
  overwrite).
- `tingle list` — configured metrics; `tingle list --types` shows the
  available metric types and their params (works without a config).

Reports go to stdout; warnings and per-metric errors go to stderr, so
`tingle stat --json | jq .` stays clean.

Migrating from ≤0.1: `tingle run` is now `tingle stat`, and `tingle diff`
is `tingle stat --diff` (summary) or `tingle report --diff` (locations).

**Exit codes**: `0` — metrics ran (warnings allowed); `1` — a metric
function failed (the others still run and report); `2` — config or usage
error. Metric *values* never affect the exit code: tingle measures, it
does not judge.

## CI example

```yaml
- run: tingle stat --json > metrics.json
- run: jq -r '.metrics[] | "\(.name)\t\(.value)"' metrics.json
- run: tingle report --cobertura > tingle.xml   # e.g. GitLab MR annotations
```

## Development

Python 3.11–3.14 are supported (CI runs the full matrix). The project
uses [mise](https://mise.jdx.dev/) + Poetry (`mise install`,
`poetry install`). Checks:

```console
$ poetry run pytest
$ poetry run ruff check
$ poetry run mypy
$ poetry run lint-imports   # GLIMPSE layer contracts
```

The source follows the GLIMPSE layout: `pacts` (contracts), `specs`
(invariants), `mills` (logic, no IO), `links` (IO adapters), `gates`
(CLI), `inits` (wiring).
