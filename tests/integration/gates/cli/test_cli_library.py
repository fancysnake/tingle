"""The `library` command, and `add --base`, end to end."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from tingle.gates.cli.typer import CliGate
from tingle.inits.services import Services

if TYPE_CHECKING:
    from pathlib import Path

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


def test_library_reports_a_pack_whose_templates_do_not_verify(broken_pack: str) -> None:
    result = runner.invoke(app, ["library", broken_pack])

    assert result.exit_code == 2
    assert "unknown type 'no_such_type'" in result.output


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
        'name = "untyped"\n'
    )

    result = runner.invoke(app, ["stat"])

    assert result.exit_code == 2
    assert "unknown type 'no_such_type'" in result.output
    assert 'metric "untyped": missing type' in result.output


def test_a_broken_template_is_reported_even_when_nothing_uses_it(workdir: Path) -> None:
    """Declared and wrong is wrong; waiting for a user hides it until later."""
    (workdir / "tingle.toml").write_text(
        f"{RANGES}\n"
        "[templates.bad]\n"
        'type = "no_such_type"\n\n'
        "[[metrics]]\n"
        'name = "files"\ntype = "file_count"\n'
    )

    result = runner.invoke(app, ["stat"])

    assert result.exit_code == 2
    assert 'template "bad": unknown type' in result.output


def test_add_base_refuses_a_local_template_that_is_not_declared(workdir: Path) -> None:
    (workdir / "tingle.toml").write_text(RANGES)

    result = runner.invoke(app, ["add", "--base", "nope"])

    assert result.exit_code == 2
    assert "unknown template 'nope'" in result.output


def test_add_takes_a_type_or_a_base_but_not_both(workdir: Path) -> None:
    (workdir / "tingle.toml").write_text(RANGES)

    both = runner.invoke(
        app, ["add", "regex_count", "x", "--base", "tingle.builtins.ruff.noqa_comment"]
    )
    neither = runner.invoke(app, ["add"])

    assert both.exit_code == 2
    assert "not both" in both.output
    assert neither.exit_code == 2
    assert "--base to build on a template" in neither.output
