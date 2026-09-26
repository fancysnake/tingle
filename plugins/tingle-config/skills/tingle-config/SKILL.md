---
name: tingle-config
description: >-
  Set up or extend a project's tingle configuration (`tingle.toml`, or
  `[tool.tingle]` in `pyproject.toml`): survey the code and tool configs for
  debt markers worth counting, in any language, and turn them into metrics
  that validate and measure something. Use whenever the user asks to set up,
  configure, add to, review, or tune tingle, to "add a metric", to "track X
  with tingle", or asks what a project should measure.
---

# Tingle config skill

tingle counts things a team wants to shrink: silenced linters, typing escape
hatches, skipped tests, uses of a class being retired, lines in a package
that should disappear. This skill writes the config that says what to count.
It is a survey first and an edit second — a metric is only worth its row if
the project actually leaves that marker behind.

## 1. Find the current state

- `tingle --version`. Not installed: `pipx run tingle …` or `uvx tingle …`
  runs it without touching the project — the right choice in a non-Python
  repo. Every command below accepts that prefix.
- The config is `./tingle.toml`, else `[tool.tingle]` in `./pyproject.toml`.
  Discovery looks in the working directory only, never upward, and the
  config file's directory is the root every glob and `file` param resolves
  against. A non-Python project always gets `tingle.toml`.
- Existing config: `tingle list` validates it (exit 2 is a config error, all
  problems reported at once), then `tingle stat` shows the numbers and any
  `ranges matched no files` warning on stderr. Read the file before editing;
  keep its comments, order and grouping.
- No config: `tingle init` writes a commented starter, or write the file from
  scratch — the starter is only a scaffold.
- `tingle list --types` and `tingle library` print what the installed
  version supports. They are the authority over the tables below.

## 2. Survey the project

Look, do not assume. Four passes:

1. **Manifests** say which languages and tools are in play: `pyproject.toml`
   `[tool.*]` sections, `setup.cfg`, `tox.ini`, `.pylintrc`, `mypy.ini`;
   `package.json`, `tsconfig.json`, eslint and prettier configs;
   `Cargo.toml`, `go.mod`, `.golangci.yml`, `Gemfile`, `.rubocop.yml`,
   `composer.json`, `*.tf`, `Dockerfile`, `.pre-commit-config.yaml`, the CI
   workflows. A tool nobody runs leaves no markers — add metrics only for
   tools the project uses.
2. **Layout** gives the ranges: source vs tests, generated or vendored
   directories, template and stylesheet trees, migrations, and any package
   whose name says it is on the way out (`legacy`, `old`, `v1`,
   `deprecated`, a module with a `# TODO: remove` at the top).
3. **Stated rules** are where the best metrics come from: `CLAUDE.md`,
   `CONTRIBUTING`, an architecture doc, import-linter contracts (including
   commented-out ones), deprecation notes, a rename in progress. Each rule
   the code still breaks is a metric: a forbidden import counted inside the
   layer that must not make it, files still under the old name, reach of an
   anti-pattern the team has agreed to retire.
4. **Markers**: grep for each candidate in the catalog below and note the
   hit count. Something with hits is a metric; something with none is a
   gate, worth adding only if the team wants to keep it at zero.

## 3. Candidate catalog

### Python tools — use the bundled templates

`base = "tingle.builtins.<module>.<name>"`. Every template carries its
`type`, `name`, `group` and pattern; state only what differs.

| Tool in use | Templates (`tingle.builtins.…`) |
| --- | --- |
| ruff | `ruff.noqa_comment`, `ruff.noqa_spread`, `ruff.ignore_comment`, `ruff.suppressed_ranges`, `ruff.file_exemptions`, `ruff.lint_ignores`, `ruff.per_file_ignores`, `ruff.format_excludes` |
| pylint | `pylint.disable_comment`, `pylint.pyproject_disables`, `pylint.rcfile_disables` (reads `.pylintrc`) |
| mypy | `mypy.type_ignore_comment`, `mypy.type_ignore_spread`, `mypy.strictness_holes`, `mypy.overrides`, `mypy.disabled_error_codes` |
| black | `black.fmt_comment`, `black.fmt_spread` |
| pytest | `pytest.skip_marks`, `pytest.xfail_marks` |
| coverage | `coverage.pragma_comment` |
| unittest.mock | `unittest_mock.any_used`, `unittest_mock.patch_used` |
| import-linter | `import_linter.deferred_contracts`, `import_linter.ignored_imports` |
| codespell, taplo | `codespell.ignore_comment`, `taplo.ignore_comment` |
| any Python | `python.any_used`, `python.cast_used`, `python.todo_comments`, `python.long_files` (over 1000 lines) |

The `*_spread` twins count files reached rather than occurrences — pick one
of a pair, or both when containment matters more than volume. The
`pyproject_disables` / `rcfile_disables` / `lint_ignores` / `overrides`
kind read a config file, not a range: they need the file to exist, and
`range` on them does nothing. `mypy.strictness_holes` and
`import_linter.deferred_contracts` are regexes over the config file and
**do** need `range = "config"`, or they search the default range and find
nothing.

Scope a marker to where it is debt: `coverage.pragma_comment`,
`unittest_mock.any_used` and the pytest marks to the tests range; the
typing templates to the source range. Templates used with a narrowed range
usually get a `name` in the group's style (`type-any`, `mock-ANY`,
`pylint-disables`).

### Everything else — state the metric yourself

`regex_count`, `regex_spread`, `file_count` and `line_count` read any text
file. `toml_list_length`, `toml_table_array` and `ini_list_length` read any
TOML or INI file named by `file`. `symbol_uses` and `symbol_spread` are
Python-only. There is no JSON or YAML reader: count entries in those configs
with `regex_count` over the file, anchored with `flags = ["MULTILINE"]`.

Patterns below are starting points; confirm each against real lines with
`tingle report --metric NAME` and excuse false positives with
`ignore_lines`.

Each line is marker, `pattern`, group.

- **JS/TS**: eslint suppressed `//\s*eslint-disable` linting · prettier
  suppressed `//\s*prettier-ignore` formatting · type check suppressed
  `@ts-(ignore|expect-error|nocheck)` typing · `any` escape hatch
  `(:\s*|as\s+)any\b` typing · skipped tests
  `\b(it|test|describe)\.(skip|todo)\(|\bx(it|test|describe)\(` testing ·
  only-tests left in `\b(it|test|describe)\.only\(` testing.
- **Rust**: lint allowed `#!?\[allow\(` linting · unsafe blocks
  `\bunsafe\s*\{` architecture · panicking shortcuts `\.(unwrap|expect)\(`
  linting · unfinished `\b(todo|unimplemented)!\(` linting · ignored tests
  `#\[ignore\b` testing.
- **Go**: nolint `//\s*nolint` linting · skipped tests `\bt\.Skip\w*\(`
  testing · untyped `\binterface\{\}|\bany\b` typing.
- **Ruby**: rubocop disabled `rubocop:disable` linting · pending specs
  `\b(xit|xdescribe|pending)\b` testing.
- **PHP**: static analysis silenced
  `@(phpstan-ignore|psalm-suppress)|phpcs:ignore` linting · skipped tests
  `markTestSkipped\(` testing.
- **Java/Kotlin**: warnings suppressed `@Suppress(Warnings)?\(` linting ·
  disabled tests `@(Ignore|Disabled)\b` testing · Kotlin not-null
  assertions `!!` typing.
- **C#**: warnings suppressed `#pragma warning disable` linting.
- **Shell**: shellcheck disabled `shellcheck disable` linting.
- **Templates**: inline styles `\sstyle="` frontend · inline handlers
  `\son[a-z]+="` frontend · inline scripts `<script(?![^>]*\ssrc=)`
  frontend · Django/Jinja escaping bypassed `\|\s*safe\b|autoescape\s+off`
  frontend · untranslated attribute text
  `(placeholder|title|alt|aria-label)="[^"{%]{4,}"` frontend · raw form
  controls where a component or form class exists `<select\b|type="checkbox"`
  frontend.
- **CSS**: specificity fights `!important` frontend.
- **Markdown / YAML / Dockerfile / Terraform**: linters silenced
  `markdownlint-disable`, `yamllint disable`, `hadolint ignore`,
  `tflint-ignore|tfsec:ignore|checkov:skip` — all linting.
- **CI**: failures tolerated `continue-on-error:\s*true|allow_failure:\s*true`
  testing.
- **Any language**: unfinished work
  `(#|//|<!--|/\*)\s*(TODO|FIXME|XXX|HACK)\b` linting.

Whole-project shapes, independent of language:

- **A package on the way out**: `line_count` over its own range, with a
  hand-set `guide` (lines are not a density) and its name in
  `[check] ignore` only if it is *expected* to grow, which a doomed package
  is not.
- **A class or function being retired**: `symbol_uses` with a dotted symbol
  in Python (follows imports; a bare name overcounts). Elsewhere,
  `regex_count` on `\bOldName\b` with `ignore_lines` for its definition and
  imports.
- **A rename in flight**: `file_count` over a range listing the old names
  (`src/**/old_name.py`, `src/**/old_name/**/*.py`), one glob pair per
  name, with the mapping old → new in a comment above.
- **A layer rule the code still breaks**: `regex_count` on the forbidden
  import (`from pkg\.adapters`) with `range` set to the layer that must not
  make it. The same for any anti-pattern the team has named: count it, or
  `regex_spread` it when the goal is to stop it reaching new files.
- **Oversized files**: `file_count` with `over_lines` and a small `guide`.
- **Config-file lists** in TOML or INI: `toml_list_length` with the dotted
  `key`, `ini_list_length` with `file` / `section` / `option`. A key that
  crosses an array of tables sums the entries.

## 4. Write the config

Ranges first, then metrics, grouped under comment headings the way
`tingle init` does.

- **Ranges** follow one convention: a whole-language range as the default
  (`python` = `src/**/*.py` + `tests/**/*.py`, `default = true`), a source
  and a tests split of it (`python-src`, `python-tests`), a `config` range
  for the tool configs, then one per further tree (`js`, `templates`,
  `legacy`, `gates`). At most one range is the default; with none, every
  file is.
- **Globs match the whole path from the root** with pathlib rules: `*` stays
  in one segment, `**` spans, always `/`. Only `.git/`, `.venv/`,
  `node_modules/`, `dist/`, `.tox/` and `.mise/` at the root and
  `__pycache__/` anywhere are excluded for free. `target/`, `build/`,
  `vendor/`, `.next/`, `coverage/`, generated code and migrations need an
  `exclude`.
- **A range matching nothing is a warning, not an error** — a typo'd glob
  reads as a clean project. Check for it in step 5.
- **Names** are unique and match `[A-Za-z0-9_.-]+`. Using a base twice
  needs a `name` on at least one.
- **Overriding a base**: a key stated wins, so a list *replaces*;
  `extra_<key>` (e.g. `extra_ignore_lines`) appends. `type` cannot be
  changed. `range` and `ranges` are one slot — stating either drops both
  from the base. `extra_` without a base is an error.
- **Groups** are presentation only. Reuse the bundled names — `formatting`,
  `linting`, `typing`, `testing`, `architecture` — so hand-written metrics
  sit beside the templates, and add `frontend` or `refactoring` when needed.
  A `description` on every metric whose pattern does not explain itself.
- **`regex_count` in diff mode matches line by line**: a pattern that spans
  a newline never matches there, and `MULTILINE` / `DOTALL` have no
  cross-line effect. `regex_spread` has no such limit.
- **`ignore_lines`** is searched anywhere in the line the hit starts on; a
  multi-line match is judged by its first line. Usual excusals: the import
  of the symbol itself (`'^from '`, `'^\s+Any,$'`), a framework base class
  that forces the marker (`'class.*admin\.ModelAdmin'`), a fixture or
  factory name that legitimately carries it.
- **Say why** above any metric whose reason is not its pattern — a TOML
  comment for the reader of the file, `description` for the report. A
  metric nobody can explain gets deleted at the first false positive.
- **Local `[templates.<name>]`** (no dot in the key) hold a shared
  `ignore_lines` set or a narrowed base used several times. Dotted bases
  import and run Python.
- **`[check]`**: `policy = "sum"` (default) lets debt paid off in one metric
  cover debt taken on in another; `"any"` fails on any growth. `ignore`
  names metrics expected to grow; an unknown name is a config error.
- **`[diff] base`** only if the trunk is not `main`. **`[display]
  loc_range`** when the default range is not the code the derived guide
  should be sized by.
- Fewer metrics the team will read beat a complete inventory. Every metric
  should point at something someone intends to shrink or hold at zero.

`tingle add` writes a single metric with the file's formatting preserved and
validates it first, but every `--param` is a string: `flags` and `explode`
must be written by hand. It has no `--config` flag.

## 5. Verify

1. `tingle list` — exit 0, every metric listed with the expected ranges.
2. `tingle stat` — the numbers are plausible. stderr clean of
   `ranges matched no files` unless that range is deliberately empty.
3. `tingle report --metric NAME` for each hand-written regex — open a few
   lines, then add `ignore_lines` for what is not debt.
4. If `tingle check` will run in CI, the checkout needs full history
   (`fetch-depth: 0`), and a non-Python job needs Python to
   `pip install tingle` or `pipx run tingle check`.

## 6. Report

Say what was added, each metric's current value, what was surveyed and left
out (a tool with no markers, a pattern that was mostly false positives), and
any range or guide that was a judgement call.
