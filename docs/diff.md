# Branch impact

Like diff-cover, but for your metrics. `--diff` measures only what the
current branch changed, compared against the **merge-base** with a base
branch — so commits that landed on the base after you branched don't pollute
your numbers.

The working tree counts, including uncommitted changes; untracked
(non-ignored) files count as fully added.

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

Red numbers mean the branch added debt; green means it removed some. Lower
is better. The Total column is today's full-repo value, for scale.

`tingle report --diff` gives the same measurement with every occurrence
located: signed and colored (`+` added, `-` removed), and for list metrics
you see *which* rules changed.

`tingle --diff` opens the branch-impact view in the interactive TUI.

## Choosing the base

The base branch resolves in this order:

1. the `--base REF` flag (which implies `--diff`),
2. `[diff] base` in the config,
3. `main`.

If the ref does not exist locally, `origin/<base>` is tried.

```toml
[diff]
base = "origin/main"
```

## Diff semantics per type

Each metric type means something specific in diff mode:

| Type | Diff meaning |
| --- | --- |
| `regex_count` | matches on lines you added (+) vs lines you removed (−) |
| `symbol_uses` | references starting on added vs removed lines |
| `regex_spread` / `symbol_spread` | files that started matching (+) vs stopped (−) |
| `line_count` | added vs removed lines |
| `file_count` | created vs deleted files |
| `toml_list_length` / `toml_table_array` / `ini_list_length` | value at the merge-base vs now (net only) |

The config-list types compare two values rather than counting lines, which
is why they show only a net figure — the Added and Removed columns stay
blank for them.

The [spread types](metrics.md#spread-regex_spread-and-symbol_spread) do not
count lines either. They read both sides of every changed file whole and
compare presence, so a branch that rewrites a file which already matched nets
zero however many matching lines it churned, while one new file that matches
is +1. That is the point of them: reworking legacy code is not spreading it.

## Approximations to know about

Diff counting is a line-level approximation. It is worth knowing exactly
where it is inexact:

- **Diff counting is per line.** Regex patterns containing newlines never
  match in diff mode (`MULTILINE` / `DOTALL` have no cross-line effect), so
  the Total column — which uses full-text matching — can disagree for such
  patterns. This does not apply to `regex_spread`, which matches both sides
  full-text.
- **A `symbol_uses` reference is attributed to the line where it *starts*.**
  Edits to a later line of a multi-line call don't count it.
- **Renames are treated as delete + add.** Net zero for line metrics; a
  renamed config file makes the value-delta metrics see a missing base.

!!! warning "CI needs history"

    The merge-base needs history: shallow clones (`fetch-depth: 1`) will
    fail. Use `fetch-depth: 0` on `actions/checkout`, or `GIT_DEPTH: 0` on
    GitLab.
