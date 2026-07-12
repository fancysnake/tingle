# Contributing

Python 3.11–3.14 are supported, and CI runs the full matrix.

## Setup

The project uses [mise](https://mise.jdx.dev/) and Poetry.

```console
$ mise install
$ poetry install
```

## Checks

Tasks are defined in `mise.toml`; `mise tasks` lists them all.

```console
$ mise run test:py      # the test suite
$ mise run lint:py      # ruff, mypy, pylint, import-linter, codespell, vulture
$ mise run format       # black, ruff --fix, taplo
```

tingle dogfoods its own CI gate — `tingle check` runs on every pull request,
so a branch that takes on debt fails the build.

## Docs

The documentation site is MkDocs + Material, built from `docs/` and
published to GitHub Pages from `main`.

```console
$ mise run docs:serve   # live-reloading preview on localhost:8000
$ mise run docs:build   # strict build; fails on broken internal links
```

The docs dependency group is optional, so a plain `poetry install` does not
pull in MkDocs. Both tasks install it on demand.

## Architecture

The source follows the GLIMPSE layout, and the layer boundaries are enforced
by import-linter contracts in `pyproject.toml` — a violating import fails
CI.

| Layer | Responsibility |
|---|---|
| `pacts` | contracts — depends on nothing |
| `specs` | invariants — depends only on `pacts` |
| `mills` | logic, no IO |
| `links` | IO adapters |
| `gates` | CLI |
| `inits` | wiring |

`specs` is imported only by `mills`; `gates` and `inits` reach it indirectly
through `mills`, which is by design.
