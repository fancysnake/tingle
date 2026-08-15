from __future__ import annotations

import re
import subprocess
from typing import TYPE_CHECKING

import pytest

from tingle.links.editor import VsCodeCli
from tingle.pacts.editor import EditorError

if TYPE_CHECKING:
    from collections.abc import Sequence


def _cli(
    *, term: str | None = "vscode", has_code: bool = True
) -> tuple[VsCodeCli, list[list[str]]]:
    calls: list[list[str]] = []
    environ = {"TERM_PROGRAM": term} if term is not None else {}
    cli = VsCodeCli(
        environ=environ,
        which=lambda name: "/usr/bin/code" if has_code and name == "code" else None,
        spawn=lambda args: calls.append(list(args)),
    )
    return cli, calls


def test_available_in_a_vscode_terminal_with_code_on_path() -> None:
    cli, _ = _cli()

    assert cli.available is True


def test_unavailable_outside_a_vscode_terminal() -> None:
    cli, _ = _cli(term="xterm-256color")

    assert cli.available is False


def test_unavailable_with_no_term_program_at_all() -> None:
    cli, _ = _cli(term=None)

    assert cli.available is False


def test_unavailable_when_code_is_not_on_path() -> None:
    cli, _ = _cli(has_code=False)

    assert cli.available is False


def test_open_jumps_to_the_line() -> None:
    cli, calls = _cli()

    cli.open("/proj/src/a.py", 42)

    # the resolved executable path, not a bare "code", so no PATH search at spawn
    assert calls == [["/usr/bin/code", "--goto", "/proj/src/a.py:42"]]


def test_open_without_a_line_opens_the_bare_file() -> None:
    cli, calls = _cli()

    cli.open("/proj/tingle.toml", None)

    assert calls == [["/usr/bin/code", "--goto", "/proj/tingle.toml"]]


def test_open_does_nothing_when_code_vanished_from_path() -> None:
    cli, calls = _cli(has_code=False)

    cli.open("/proj/src/a.py", 42)

    assert not calls


def test_a_shim_that_will_not_answer_becomes_an_editor_error() -> None:
    """The adapter owns subprocess; what it hands upwards is an EditorError."""

    def _hang(_args: Sequence[str]) -> None:
        raise subprocess.TimeoutExpired(cmd="code", timeout=5)

    cli = VsCodeCli(
        environ={"TERM_PROGRAM": "vscode"}, which=lambda _: "/usr/bin/code", spawn=_hang
    )

    with pytest.raises(
        EditorError, match=re.escape("could not open /proj/src/a.py:42")
    ):
        cli.open("/proj/src/a.py", 42)


def test_a_shim_that_vanished_between_probe_and_spawn_becomes_one_too() -> None:
    def _gone(_args: Sequence[str]) -> None:
        raise FileNotFoundError(2, "No such file or directory")

    cli = VsCodeCli(
        environ={"TERM_PROGRAM": "vscode"}, which=lambda _: "/usr/bin/code", spawn=_gone
    )

    with pytest.raises(EditorError):
        cli.open("/proj/src/a.py", None)
