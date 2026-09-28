# Contributing

Python 3.11–3.14 are supported, and CI runs the full matrix.

## Setup

The project uses [mise](https://mise.jdx.dev/) and Poetry.

```console
mise install
poetry install
```

`vekna cast` pushes through an https remote, since a cast has no terminal for
an ssh key passphrase. A fresh clone adds one once, substituting its own URL
on a fork:

```console
git remote add https-origin https://github.com/fancysnake/tingle.git
gh auth login && gh auth setup-git
```

## Checks

Tasks are defined in `mise.toml`; `mise tasks` lists them all.

```console
mise run test:py      # the test suite
mise run lint:py      # ruff, mypy, pylint, import-linter, codespell, vulture
mise run format       # black, ruff --fix, taplo
```

tingle dogfoods its own CI gate — `tingle check` runs on every pull request,
so a branch that takes on debt fails the build.

## Tests

`tests/` is split by test type, and the layer under test picks the type — not
convenience, and not whichever is easier to reach coverage with.

| Layer | Type | Where |
| --- | --- | --- |
| `mills`, `specs`, `pacts`, and pure helpers from any layer | unit | `tests/unit/` |
| `links`, `gates`, `inits` — anything that touches the filesystem, git, or a terminal | integration | `tests/integration/` |

Unit tests mock the protocols in `pacts` and assert how they were called;
`tests/unit/` is organised by convenience rather than mirroring `src/`.
Integration tests run against the real thing — a git repository in a tmpdir, a
typer `CliRunner`, a textual pilot — and assert side effects.

An uncovered line belongs to the test type that owns its layer: never raise
`links` or `gates` coverage with a mock-everything unit test. Those two suites
are also what the `test:unit` and `test:int` tasks run separately, so a
boundary change can be checked without the whole suite.

## Docs

The documentation site is MkDocs + Material, built from `docs/` and
published to GitHub Pages from `main`.

```console
mise run site:dev     # live-reloading preview on localhost:8000
mise run site:build   # build into site/; strict, so a broken link fails it
```

The docs dependency group is optional, so a plain `poetry install` does not
pull in MkDocs. Both tasks install it on demand.

## Architecture

The source follows the GLIMPSE layout, and the layer boundaries are enforced
by import-linter contracts in `pyproject.toml` — a violating import fails
CI.

| Layer | Responsibility |
| --- | --- |
| `pacts` | contracts — depends on nothing |
| `specs` | invariants — depends only on `pacts` |
| `mills` | logic, no IO |
| `links` | IO adapters |
| `gates` | CLI |
| `inits` | wiring |

`specs` is imported only by `mills`; `gates` and `inits` reach it indirectly
through `mills`, which is by design.
