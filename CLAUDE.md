# tingle

A refactoring-metrics CLI: it counts suppression comments and other debt
markers, tracks them over time, and fails a branch that takes on more.

## Where the rules are

- `docs/contributing.md` — setup, the task list, the test-type split, and the
  GLIMPSE layer table. Read the Tests section before adding a test.
- `pyproject.toml` — the import-linter contracts that enforce the layer
  boundaries. A violating import fails CI.

## Tasks

`mise tasks` is the source of truth; never invoke pytest, mypy or ruff
directly. The ones that matter:

```console
mise run test:unit    # unit suite
mise run test:int     # integration suite
mise run gate         # linters, types and tests, changing no file
mise run site:build   # the docs site; strict, so a broken link fails it
mise run fullcheck    # the sweep before a commit: formatters and coverage too
```

`fullcheck` is the commit gate. Run it once, before committing — not after
each edit.
