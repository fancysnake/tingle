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
- **Keep no state.** `tingle stat` and `tingle check` measure the tree in
  front of them, and the config is the only file they read, so there is
  nothing to merge and nothing to go stale. History is opt-in, and lives on
  a data branch.
- **Any marker in any language.** If the code leaves a trace, a regex can
  count it; templates spare the typing for the tools everyone runs.
- **Say only what is true today.** This documentation describes what the
  released version does. A plan is not a feature until it ships.

## What it does today

The features, each with its own page, are listed under
[Where to go next](index.md#where-to-go-next).

## What it is not

- **Not a linter.** It runs no rules. It counts what linters and type
  checkers were told to skip.
- **Not a quality score.** It rates nothing. It counts what you told it to
  count, and nothing else.
- **Not a service.** No third-party service, no account; history is a branch
  in your own repo.
