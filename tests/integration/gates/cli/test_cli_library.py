"""The `library` command, and `add --base`, end to end."""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from tingle.gates.cli.typer import CliGate
from tingle.inits.services import Services

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

runner = CliRunner()
app = CliGate(Services()).app

RANGES = '[ranges.python]\ninclude = ["src/**/*.py"]\ndefault = true\n'


def _source(workdir: Path, text: str) -> None:
    (workdir / "src").mkdir(exist_ok=True)
    (workdir / "src" / "a.py").write_text(text)


def test_library_lists_the_builtin_pack() -> None:
    result = runner.invoke(app, ["library"])

    assert result.exit_code == 0
    assert "ruff.noqa_comment" in result.output
    assert 'base = "tingle.builtins.<template>"' in result.output


def test_library_expands_a_pack_into_pasteable_config() -> None:
    result = runner.invoke(app, ["library", "--expand"])

    assert result.exit_code == 0
    assert "[[metrics]]" in result.output
    assert 'name = "noqa-comment"' in result.output
    assert r"pattern = '#\s*noqa:'" in result.output


def test_library_reports_a_package_that_is_not_there() -> None:
    result = runner.invoke(app, ["library", "no_such_pack"])

    assert result.exit_code == 2
    assert "no importable package" in result.output


def test_library_lists_what_works_in_a_pack_and_reports_the_rest(
    broken_pack: str,
) -> None:
    """Somebody else's pack: one bad template is not the whole answer."""
    result = runner.invoke(app, ["library", broken_pack])

    listed = result.output.partition("Template")[2]

    assert result.exit_code == 0
    assert "unknown type 'no_such_type'" in result.output
    assert "tools.usable" in listed
    assert "tools.wrong_type" not in listed


def test_a_metric_built_on_a_template_measures_and_is_named_by_it(
    workdir: Path,
) -> None:
    _source(workdir, "x = 1  # noqa: E501\n")
    (workdir / "tingle.toml").write_text(
        f'{RANGES}\n[[metrics]]\nbase = "tingle.builtins.ruff.noqa_comment"\n'
    )

    result = runner.invoke(app, ["stat", "--json"])

    assert result.exit_code == 0
    metric = json.loads(result.stdout)["metrics"][0]
    assert metric["name"] == "noqa-comment"
    assert metric["group"] == "linting"
    assert metric["value"] == 1


def test_extra_ignore_lines_narrows_a_template_without_replacing_its_own(
    workdir: Path,
) -> None:
    _source(workdir, "x = 1  # noqa: E501\ny = 2  # noqa: E501  # legacy\n")
    (workdir / "tingle.toml").write_text(
        f"{RANGES}\n[[metrics]]\n"
        'base = "tingle.builtins.ruff.noqa_comment"\n'
        'extra_ignore_lines = ["# legacy"]\n'
    )

    result = runner.invoke(app, ["stat", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["metrics"][0]["value"] == 1


def test_a_local_template_shares_one_ignore_set_across_metric_types(
    workdir: Path,
) -> None:
    _source(workdir, "x = 1  # noqa  # generated\nANY = 2  # generated\nz = ANY\n")
    (workdir / "tingle.toml").write_text(
        f"{RANGES}\n"
        "[templates.generated]\n"
        'ignore_lines = ["# generated"]\n\n'
        "[[metrics]]\n"
        'base = "generated"\nname = "noqa"\ntype = "regex_count"\n'
        "pattern = '#\\s*noqa'\n\n"
        "[[metrics]]\n"
        'base = "generated"\nname = "any-uses"\ntype = "symbol_uses"\n'
        'symbol = "ANY"\n'
    )

    result = runner.invoke(app, ["stat", "--json"])

    assert result.exit_code == 0
    values = {m["name"]: m["value"] for m in json.loads(result.stdout)["metrics"]}
    assert values == {"noqa": 0, "any-uses": 1}


def test_overriding_a_templates_type_is_refused(workdir: Path) -> None:
    (workdir / "tingle.toml").write_text(
        f"{RANGES}\n[[metrics]]\n"
        'base = "tingle.builtins.ruff.noqa_comment"\ntype = "regex_spread"\n'
    )

    result = runner.invoke(app, ["stat"])

    assert result.exit_code == 2
    assert 'type is fixed by the template ("regex_count")' in result.output
    assert 'base "tingle.builtins.ruff.noqa_comment"' in result.output


def test_add_base_writes_the_base_not_its_expansion(workdir: Path) -> None:
    _source(workdir, "x = 1  # noqa: E501\n")
    (workdir / "tingle.toml").write_text(RANGES)

    added = runner.invoke(app, ["add", "--base", "tingle.builtins.ruff.noqa_comment"])

    assert added.exit_code == 0
    written = (workdir / "tingle.toml").read_text()
    assert 'base = "tingle.builtins.ruff.noqa_comment"' in written
    assert "pattern" not in written

    ran = runner.invoke(app, ["stat", "--json"])

    assert json.loads(ran.stdout)["metrics"][0]["value"] == 1


def test_add_base_refuses_a_template_that_is_not_there(workdir: Path) -> None:
    (workdir / "tingle.toml").write_text(RANGES)

    result = runner.invoke(app, ["add", "--base", "tingle.builtins.ruff.nope"])

    assert result.exit_code == 2
    assert "no attribute 'nope'" in result.output
    assert "base" not in (workdir / "tingle.toml").read_text()


def test_an_unknown_local_base_is_named_at_the_metric(workdir: Path) -> None:
    (workdir / "tingle.toml").write_text(f'{RANGES}\n[[metrics]]\nbase = "nope"\n')

    result = runner.invoke(app, ["stat"])

    assert result.exit_code == 2
    assert 'metrics[0]: unknown base "nope"' in result.output


def test_a_base_that_is_not_a_string_is_refused(workdir: Path) -> None:
    (workdir / "tingle.toml").write_text(f"{RANGES}\n[[metrics]]\nbase = 17\n")

    result = runner.invoke(app, ["stat"])

    assert result.exit_code == 2
    assert "metrics[0]: base must be a string" in result.output


def test_a_broken_template_and_a_broken_metric_are_reported_together(
    workdir: Path,
) -> None:
    """Two runs to fix two problems is what one pass is meant to avoid."""
    (workdir / "tingle.toml").write_text(
        f"{RANGES}\n"
        "[templates.bad]\n"
        'type = "no_such_type"\n\n'
        "[[metrics]]\n"
        'base = "bad"\nname = "built-on-it"\n\n'
        "[[metrics]]\n"
        'name = "untyped"\n'
    )

    result = runner.invoke(app, ["stat"])

    assert result.exit_code == 2
    assert "unknown type 'no_such_type'" in result.output
    assert 'metric "untyped": missing type' in result.output


def test_a_broken_import_is_reported_once_however_many_metrics_named_it(
    workdir: Path,
) -> None:
    """The problem is the template; repeating it per user buries it."""
    (workdir / "tingle.toml").write_text(
        f"{RANGES}\n"
        "[[metrics]]\n"
        'base = "tingle.builtins.ruff.nope"\nname = "a"\n\n'
        "[[metrics]]\n"
        'base = "tingle.builtins.ruff.nope"\nname = "b"\n'
    )

    result = runner.invoke(app, ["stat"])

    assert result.exit_code == 2
    assert result.output.count("no attribute 'nope'") == 1
    assert "unknown base" not in result.output


def test_add_base_refuses_a_local_template_that_is_not_declared(workdir: Path) -> None:
    (workdir / "tingle.toml").write_text(RANGES)

    result = runner.invoke(app, ["add", "--base", "nope"])

    assert result.exit_code == 2
    assert "unknown template 'nope'" in result.output


def test_add_refuses_a_type_the_base_already_fixes(workdir: Path) -> None:
    (workdir / "tingle.toml").write_text(RANGES)

    both = runner.invoke(
        app, ["add", "regex_count", "x", "--base", "tingle.builtins.ruff.noqa_comment"]
    )
    neither = runner.invoke(app, ["add"])

    assert both.exit_code == 2
    assert 'the base fixes the metric type ("regex_count")' in both.output
    assert neither.exit_code == 2
    assert "--base to build on a template" in neither.output


def test_add_base_on_a_mixin_takes_the_type_the_mixin_leaves_open(
    workdir: Path,
) -> None:
    """A mixin states no type, so this is the one case where both are right."""
    _source(workdir, "x = 1  # noqa: E501  # generated\ny = 2  # noqa: E501\n")
    (workdir / "tingle.toml").write_text(
        f"{RANGES}\n[templates.generated]\nignore_lines = ['# generated']\n"
    )

    added = runner.invoke(
        app, ["add", "regex_count", "#\\s*noqa", "--base", "generated"]
    )

    assert added.exit_code == 0
    ran = runner.invoke(app, ["stat", "--json"])
    assert json.loads(ran.stdout)["metrics"][0]["value"] == 1


def test_add_base_on_a_mixin_still_needs_a_type_from_somewhere(workdir: Path) -> None:
    (workdir / "tingle.toml").write_text(
        f"{RANGES}\n[templates.generated]\nignore_lines = ['# generated']\n"
    )

    result = runner.invoke(app, ["add", "--base", "generated"])

    assert result.exit_code == 2
    assert "states no type; give one alongside --base" in result.output


def _written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, name: str, body: str
) -> str:
    monkeypatch.syspath_prepend(str(tmp_path))
    package = tmp_path / name
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "tools.py").write_text(
        f"from tingle.pacts.config import MetricTemplate\n{body}"
    )
    monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.delitem(sys.modules, f"{name}.tools", raising=False)
    return name


def test_a_description_holding_brackets_is_prose_not_markup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rich would read `[tool.ruff]` as a tag and swallow it, or refuse to draw."""
    pack = _written(
        tmp_path,
        monkeypatch,
        name="bracket_pack",
        body='square = MetricTemplate(type="line_count", name="lines",'
        ' group="[size]", description="counts [tool.ruff] sections")\n',
    )

    result = runner.invoke(app, ["library", pack])

    assert result.exit_code == 0
    assert "[tool.ruff]" in result.output
    assert "[size]" in result.output


def test_expanding_a_mixin_says_what_a_reader_still_has_to_supply(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pasted as it stands a mixin is not a metric, and the config would say so."""
    pack = _written(
        tmp_path,
        monkeypatch,
        name="mixin_pack",
        body='shared = MetricTemplate(params={"ignore_lines": ["x"]})\n',
    )

    result = runner.invoke(app, ["library", pack, "--expand"])

    assert result.exit_code == 0
    assert "# a mixin: add name and type of your own" in result.output
