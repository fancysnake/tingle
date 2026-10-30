---
description: "Why tingle exists, what it stands for, and what it deliberately is not."
---

# Mission

tingle is a refactoring-metrics CLI: it counts the debt a codebase carries,
tracks the numbers over time, and fails the branch that adds more.

## Why it exists

Refactors don't fail loudly. They stall quietly. A `# noqa` here, a
`# type: ignore` there, an ignored rule in `pyproject.toml`, one more import
of the class the migration was meant to retire. Each is reasonable on the
day; together they are the debt. Every tool makes its own suppressions easy
and keeps its own count, if any. None of them shows the whole of it, or
whether this branch made it worse.

tingle puts one number on each kind of debt, measures what a branch changed,
and lets CI refuse the branch that adds more, so the numbers only go down.

## What we believe

- **Count the debt, don't hide it.** A suppression is debt with a label.
  tingle counts the labels, so the easier a tool makes suppressing, the more
  the count is worth.
- **A branch answers for what it changed.** Work that lands on the base
  after you branch is not yours, and never counts against you.
- **Measure first, judge on request.** `tingle stat` reports, and no number
  changes its exit code. Failing the build is a separate command a team
  chooses to run.
- **Keep no state.** Every run measures the tree in front of it. The config
  is the only file in the repository, so there is nothing to merge and
  nothing to go stale.
- **Any marker in any language.** If the code leaves a trace, a regex can
  count it; templates spare the typing for the tools everyone runs.
- **Say only what is true today.** This documentation describes what the
  released version does. A plan is not a feature until it ships.

## What it does today

| Feature | What tingle does |
| --- | --- |
| **[Metric types](metrics.md)** | Regex matches, uses of a Python symbol, entries in a TOML or INI list, files and lines, each counted per file, with every occurrence at `file:line`. |
| **[Branch impact](diff.md)** | `tingle stat --diff` measures only what the branch changed, against the merge-base, uncommitted and untracked files included. |
| **[CI gate](check.md)** | `tingle check` exits 1 when the branch makes any metric worse, and lists the lines that did it. |
| **Migrations** | [`symbol_uses`](metrics.md#symbol_uses) counts uses of a legacy class; [`line_count`](metrics.md#file_count-and-line_count) counts the code in a package meant to disappear. |
| **[Template library](library.md)** | Ready-made metrics for Ruff, mypy, pylint, black, pytest, codespell, import-linter and TODO comments. A team's own templates ship as an ordinary Python package. |
| **[History](history.md)** | A GitHub Action records a point per commit on main to a data branch and publishes one chart per metric group. |
| **[Claude Code plugin](claude-plugin.md)** | The `tingle-config` skill surveys a project's languages, tools and layout, and writes `tingle.toml`. |

## What it is not

- **Not a linter.** It runs no rules. It counts what linters and type
  checkers were told to skip.
- **Not a quality score.** It rates nothing. It counts what you told it to
  count, and nothing else.
- **Not a service.** Nothing leaves the repository; history is a branch in
  your own repo.
