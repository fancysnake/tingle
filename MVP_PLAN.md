# tingle MVP — Implementation Plan (GLIMPSE layout)

## Context

`tingle` is a new CLI tool for the era of constant refactoring of AI-generated code: it measures user-defined code metrics in a local codebase in a single run (no history/caching — out of scope). Canonical use cases: counting ignored lint rules (ruff/pylint/mypy config), inline `# noqa` / `# type: ignore` comments, and uses of a legacy function/class during strangler-fig refactoring.

The repo at `/home/radek/tingle` is greenfield: bare `pyproject.toml` (poetry-core, PEP 621), `mise.toml` (venv + `poetry install` hook), empty `src/` and `tests/`. **Not a git repo yet** — `git init` + feature branch in step 1.

## Agreed decisions

- **Full GLIMPSE layout** (pacts/specs/mills/links/gates/inits), enforced with import-linter.
- **YAGNI**: no Python-file "advanced mode", no plugin API, no public facade, no extension seams beyond what the MVP commands need. Internal modules are imported directly.
- **Config-only metrics** in TOML. Discovery: `tingle.toml` first, fall back to `[tool.tingle]` in `pyproject.toml`; tingle.toml wins if both exist. Cwd only, no upward walk.
- **Named ranges**: file sets with include/exclude globs (e.g. `python`, `js`); each metric targets one or more ranges; one range may be marked `default = true`.
- **Built-in metric types**: `regex_count`, `symbol_uses` (AST), `toml_list_length`, `ini_list_length`, `file_count`/`line_count`. No per-linter umbrella types — lint-ignore counting is done by pointing the generic list-length types at the relevant config file/key.
- **`tingle add TYPE [VALUE]`** appends a metric to the config (tomlkit, style-preserving), e.g. `tingle add regex_count '#\s*noqa'`.
- **Output**: Rich CLI table (default) + `--format json`. HTML explicitly not designed for now.
- **Runtime deps**: typer, rich, tomlkit. Dev deps: pytest, ruff, mypy, import-linter.

## Config schema

```toml
# tingle.toml (same schema nests under [tool.tingle] in pyproject.toml)
[ranges.python]
include = ["src/**/*.py", "tests/**/*.py"]
exclude = ["src/generated/**"]
default = true               # metrics without a range/ranges key use this range

[ranges.js]
include = ["frontend/**/*.js", "frontend/**/*.ts"]

[[metrics]]
name = "noqa-comments"
type = "regex_count"
range = "python"             # single range (string shorthand)
pattern = '#\s*noqa'

[[metrics]]
name = "todo-comments"
type = "regex_count"
ranges = ["python", "js"]    # multiple ranges: union of matched files
pattern = '\bTODO\b'

[[metrics]]
name = "old-client-uses"
type = "symbol_uses"
symbol = "myapp.legacy.OldClient"   # no range key → default range (python)

[[metrics]]
name = "ruff-ignores"
type = "toml_list_length"    # rangeless type: reads the named file
file = "pyproject.toml"
key = "tool.ruff.lint.ignore"

[[metrics]]
name = "pylint-disables"
type = "ini_list_length"     # rangeless type: reads the named file
file = ".pylintrc"
section = "MESSAGES CONTROL"
option = "disable"

[[metrics]]
name = "python-loc"
type = "line_count"
range = "python"
```

Semantics:
- A metric targets ranges via `range = "name"` (string) or `ranges = ["a", "b"]` (list). Multiple ranges resolve to the **union** of matched files, deduped and sorted. Giving both keys, or an empty list, is a ConfigError.
- One range table may set `default = true`; metrics without a range key use it. More than one default → ConfigError. If no range is marked default, an implicit all-files range (`**/*`) applies. No reserved range names.
- `DEFAULT_EXCLUDES` (`.git/**`, `.venv/**`, `**/__pycache__/**`, `node_modules/**`, `dist/**`, `.tox/**`, `.mise/**`) always appended to every range, including the implicit one (documented, no opt-out).
- Validation collects **all** problems into one `ConfigError(list[str])`: bad shapes, duplicate/invalid metric names (`^[A-Za-z0-9_.-]+$`), unknown type/range, multiple default ranges, `range`+`ranges` together, missing/unknown params (strict — catches typos), per-type checks (e.g. regex must compile).
- Reading uses stdlib `tomllib`; `tomlkit` only for `add`/`init` edits.

## Package layout (GLIMPSE, src layout)

```
src/tingle/
├── __init__.py               # __version__
├── __main__.py               # python -m tingle → gates.cli.typer main
├── pacts/                    # DTOs, protocols, errors — depends on nothing
│   ├── config.py             # RangeSpec (incl. default flag), MetricSpec (ranges: tuple[str, ...]),
│   │                         #   Config (frozen dataclasses);
│   │                         #   ConfigError(errors: list[str]), ConfigNotFoundError
│   ├── metrics.py            # MetricContext, MetricResult, MetricType;
│   │                         #   ProjectFiles protocol (walk/read/exists)
│   └── report.py             # RunReport, MetricOutcome
├── specs/                    # pure invariants — consumed only by mills
│   ├── config.py             # METRIC_NAME_RE, implicit all-files range, per-type defaults
│   └── ranges.py             # DEFAULT_EXCLUDES
├── mills/                    # business logic, no IO — depends on pacts + specs
│   ├── config.py             # validate raw dict → Config (metric-type table passed in as data)
│   ├── ranges.py             # pure glob filtering: walked paths + range specs → sorted file
│   │                         #   tuple; union across a metric's ranges
│   ├── runner.py             # Config + ProjectFiles + metric-type table → RunReport
│   │                         #   (per-metric error isolation, empty-range warnings)
│   └── metrics/
│       ├── counts.py         # file_count, line_count
│       ├── regex_count.py
│       ├── config_lists.py   # toml_list_length, ini_list_length
│       └── symbol_uses.py
├── links/                    # IO — depends on pacts only
│   ├── fs/
│   │   └── local.py          # implements ProjectFiles: walk tree, read_text
│   │                         #   (binary detect: \0 in first 8 KB; UTF-8 decode → None + warning)
│   └── config_file/
│       └── toml.py           # discovery (tingle.toml > [tool.tingle]), tomllib → raw dict;
│                             #   tomlkit append-metric / write-starter for add & init
├── gates/                    # delivery — depends on pacts + mills (+ inits for wiring)
│   └── cli/
│       └── typer.py          # Typer app: run (default), add, init, list;
│                             #   table (Rich) + json rendering; exit-code mapping
└── inits/                    # wiring — links into gates
    └── wiring.py             # METRIC_TYPES: dict[str, MetricType] (static, no registration
                              #   machinery); constructs ProjectFiles + runner inputs
```

Notes:
- `gates/cli/typer.py` shadowing the `typer` package is safe — Python 3 absolute imports resolve `import typer` to the installed package.
- Tests mirror layers: `tests/mills/`, `tests/links/`, `tests/gates/` + `tests/conftest.py`.
- import-linter contracts in pyproject: specs→pacts only; mills→pacts+specs; links→pacts; gates→pacts+mills+inits; inits→pacts+mills+links; nothing imports gates.

## Core contracts (pacts)

```python
class ProjectFiles(Protocol):                  # implemented by links/fs/local.py
    def walk(self) -> Iterable[PurePath]: ...  # all files under root, relative paths
    def read(self, path: PurePath) -> str | None: ...  # None = binary/undecodable/missing
    def exists(self, path: PurePath) -> bool: ...

MetricFunction = Callable[[MetricContext], MetricResult]

@dataclass(frozen=True)
class MetricContext:
    files: tuple[PurePath, ...]     # union of the metric's ranges, deduped, sorted
    read: Callable[[PurePath], str | None]   # bound to ProjectFiles.read
    exists: Callable[[PurePath], bool]
    params: Mapping[str, Any]

@dataclass(frozen=True)
class MetricResult:
    value: int
    details: Mapping[str, int] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

@dataclass(frozen=True)
class MetricType:                   # data for dispatch, `add`, `list --types`, validation
    name: str
    func: MetricFunction
    required_params: tuple[str, ...] = ()
    optional_params: tuple[str, ...] = ()
    primary_param: str | None = None          # binds `tingle add` positional VALUE
    validate_params: Callable[[Mapping[str, Any]], list[str]] | None = None
    description: str = ""
```

Metric functions live in mills and never touch the filesystem — content comes through `read`/`exists`, so unit tests use an in-memory fake, no tmp_path needed. The metric-type table is a plain static dict in `inits/wiring.py`; mills receive it as an argument (data, not an import), keeping mills free of inits.

## CLI surface

- `tingle` / `tingle run [--format table|json] [--config PATH] [--metric NAME]…` — bare `tingle` invokes run. Report → stdout; warnings → stderr (keeps JSON pipeable).
- `tingle add TYPE [VALUE] [--name N] [--range R]… [--param key=value]…` — VALUE binds to `primary_param`; `--range` repeatable (one → `range = "R"`, several → `ranges = [...]`). Auto-name `<type>-<value-slug>`, deduped `-2`, `-3`…. Validates the new spec before writing. Writes to whichever config exists (tingle.toml wins); creates tingle.toml if none.
- `tingle init` — starter tingle.toml with commented examples; exists → exit 2.
- `tingle list [--types]` — configured metrics; `--types` lists METRIC_TYPES (works without config).
- `--version` eager option.

**Exit codes**: 0 = ran (warnings OK); 1 = internal error or a metric function raised (other metrics still run and report); 2 = config/usage error (`ConfigError`/`ConfigNotFoundError`). Metric values never affect exit code — no thresholds in MVP.

## Metric semantics & edge cases

- **file_count / line_count**: `len(files)`; lines via `splitlines()` per readable file; `read()` → None skipped with warning. Empty resolved file set → 0 + runner warning "ranges matched no files" (all range-based metrics).
- **regex_count**: required `pattern`, optional `flags` (`IGNORECASE`/`MULTILINE`/`DOTALL`). Compiled by `validate_params` → invalid regex is exit 2 before scanning. `finditer` count; details list nonzero files. Primary param: `pattern`.
- **toml_list_length**: required `key` (dotted path, e.g. `tool.ruff.lint.ignore`); optional `file` (default `pyproject.toml`). Rangeless — reads the named file via `read`. Value at key: list → its length; table whose values are lists → sum of the lists' lengths (covers e.g. ruff `per-file-ignores`); any other type → warning + 0. Missing file or key path → warning + 0 (a runtime state, not a config error — the file may legitimately not exist yet). Malformed TOML → warning + 0. Primary param: `key`.
- **ini_list_length**: required `file`, `section`, `option`. Rangeless. Parses with `configparser`; the option value is split on commas and newlines, empty entries dropped. Missing file/section/option → warning + 0; unparseable INI → warning + 0. No primary param (three required params — set via `--param`).
- **symbol_uses**: required `symbol`, bare (`OldClient`) or dotted (`myapp.legacy.OldClient`). `*.py` only; `SyntaxError` → warn + skip file. Dotted mode tracks per-file import bindings (`import a.b as m`, `from a.b import C as X`) and counts matching `Name` nodes + full `Attribute` chains (dedup at topmost chain node — no double counting); the import statement itself counts as one use. Bare mode counts matching `Name`/`Attribute` nodes (documented overcount risk). `import *` → warning + bare fallback for that file. Documented limits: static only — no re-exports, strings, `getattr`. Primary param: `symbol`.

## Steps (commit after each; each independently verifiable)

1. **Scaffolding.** `git init` + feature branch. Fix `requires-python = "3.14"` → `">=3.14"` (invalid PEP 440 as-is). Runtime deps; dev group (pytest, ruff, mypy, import-linter); `[project.scripts] tingle = "tingle.gates.cli.typer:main"`; tool configs (ruff py314, mypy strict, pytest, importlinter layer contracts). Create all layer packages with `__init__.py`s, `__main__.py`, stub CLI with `--version`.
   *Verify*: `poetry install`; `tingle --help`/`--version`; CliRunner smoke test; `lint-imports`, ruff, mypy clean.
2. **pacts + specs.** All contracts from "Core contracts" + `pacts/config.py`, `pacts/report.py`; specs constants.
   *Verify*: mypy strict + import-linter pass; dataclass construction/immutability tests.
3. **links/config_file/toml.py — discovery + read.** tingle.toml > `[tool.tingle]`, `--config PATH` override, tomllib → raw dict (editing deferred to step 11).
   *Verify*: tmp_path tests — tingle.toml / pyproject-only / both (tingle wins) / missing (ConfigNotFoundError) / malformed TOML.
4. **mills/config.py — validation.** Raw dict + metric-type table → `Config`; aggregated ConfigError; `range` string / `ranges` list normalization to `MetricSpec.ranges`; default-range resolution.
   *Verify*: stub MetricTypes — multi-error aggregation, duplicate/invalid names, unknown type/range, `range`+`ranges` conflict, empty `ranges` list, multiple `default = true` ranges, no-default fallback to implicit all-files range, missing/unknown params, `validate_params` hook invoked.
5. **links/fs/local.py + mills/ranges.py.** Walk (files only) and read with binary/decode handling; pure glob filter with excludes + DEFAULT_EXCLUDES via `PurePath.full_match`, union across multiple ranges, sorted/deduped.
   *Verify*: tmp_path walk tests incl. binary + bad-UTF-8; pure filter tests (no fs) — nested globs, excludes, union of two overlapping ranges deduped, implicit all-files range, `.git`/`.venv` skipped, empty result.
6. **mills/metrics: counts + regex_count.** Pure, tested with in-memory fake reader.
   *Verify*: both counts; unreadable-file warnings; multi-match, flags, zero matches; invalid regex rejected via `validate_params`.
7. **mills/metrics/config_lists.py — toml_list_length + ini_list_length.**
   *Verify* (fake `read`/`exists`): list length; table-of-lists sum; non-list value → warning + 0; missing file/key/section/option → warning + 0; malformed TOML/INI → warning + 0; comma+newline splitting with empties dropped; `file` default `pyproject.toml`.
8. **mills/metrics/symbol_uses.py.**
   *Verify*: plain/aliased/from imports, attribute chains, bare mode, zero uses, syntax-error skip, star-import fallback, no double counting.
9. **mills/runner.py + inits/wiring.py.** Runner: per-metric isolation (one raising metric → outcome error, others run); resolves each metric's range union once; METRIC_TYPES dict wiring funcs from mills.
   *Verify*: runner tests with fakes — isolation, empty-union warning, metric filtering input; wiring table covers all six types with correct param specs.
10. **gates/cli/typer.py — run (default) + list, rendering.** Rich table + JSON rendering in the gate; exit-code mapping.
    *Verify*: CliRunner end-to-end on tmp_path project — table output, `--format json` parses to schema, exit 2 bad/missing config, exit 1 raising metric (monkeypatched), `--metric` filter, `list`/`list --types`.
11. **`tingle add` + `tingle init`.** tomlkit editing in links/config_file/toml.py; gate commands with repeatable `--range`.
    *Verify*: append preserves comments/formatting (assert raw text), single vs multiple `--range` output shape, `--param`-only types (ini_list_length), pyproject target, no-config creation, name dedupe, invalid pattern rejected without writing, init exists → exit 2, round-trip add→run.
12. **Polish.** README (config reference, metric semantics + limitations, exit codes, CI JSON example), init template matches docs, final ruff/mypy/import-linter/pytest sweep, dogfood tingle.toml measuring tingle itself.

## Verification (end-to-end)

All Python tooling via poetry (`poetry run pytest`, `poetry run ruff check`, `poetry run mypy`, `poetry run lint-imports`) — never bare `python`/`pytest` (mise-managed machine). Final check in the tingle repo itself: `tingle init`, `tingle add regex_count '#\s*noqa'`, `tingle add toml_list_length tool.ruff.lint.ignore`, `tingle` (table), `tingle --format json | python -m json.tool`.
