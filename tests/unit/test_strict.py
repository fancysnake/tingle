from __future__ import annotations

from pathlib import Path, PurePath
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from tingle.mills.config import validate
from tingle.mills.strict import Scores, changed_modules, judged_at_base, loosenings
from tingle.pacts.check import Loosening, StrictVerdict
from tingle.pacts.metrics import MetricResult, MetricType

if TYPE_CHECKING:
    from collections.abc import Mapping

    from tingle.pacts.config import Config

SOURCE = Path("/project/tingle.toml")
METRIC_TYPES = {
    "with_diff": MetricType(
        name="with_diff", func=lambda _ctx: MetricResult(value=0), diff_func=MagicMock()
    ),
    "no_diff": MetricType(name="no_diff", func=lambda _ctx: MetricResult(value=0)),
}


def _config(
    *names: str, check: dict[str, object] | None = None, kind: str = "with_diff"
) -> Config:
    return validate(
        {
            "metrics": [{"name": name, "type": kind} for name in names],
            "check": check or {},
        },
        METRIC_TYPES,
        source=SOURCE,
    )


def _loosened(
    base: Config,
    own: Config,
    *,
    before: Mapping[str, int] | None = None,
    after: Mapping[str, int] | None = None,
    modules: tuple[PurePath, ...] = (),
) -> tuple[Loosening, ...]:
    return loosenings(
        base,
        own,
        judged=judged_at_base(base, METRIC_TYPES),
        scores=Scores(before=before or {}, after=after or {}),
        modules=modules,
    )


@pytest.mark.parametrize(
    ("path", "found"),
    (
        ("pack/tools.py", True),
        ("src/pack/tools.py", True),
        ("pack/tools/__init__.py", True),
        ("pack/__init__.py", True),
        ("pack.py", True),
        ("pack/tools/noqa.py", False),
        ("pack/other.py", False),
        ("tools.py", False),
        ("__init__.py", False),
        ("pack/tools.toml", False),
    ),
)
def test_changed_modules_finds_the_files_a_dotted_base_runs_through(
    path: str, *, found: bool
) -> None:
    changed = (PurePath(path),)

    assert changed_modules(("pack.tools.noqa",), changed) == (changed if found else ())


def test_a_lower_score_is_named_with_both_numbers() -> None:
    config = _config("noqa")

    found = _loosened(config, config, before={"noqa": 5}, after={"noqa": 3})

    assert found == (Loosening("noqa", "5 to 3"),)


def test_a_higher_or_equal_score_is_not_loosening() -> None:
    config = _config("noqa", "other")

    found = _loosened(
        config, config, before={"noqa": 5, "other": 2}, after={"noqa": 6, "other": 2}
    )

    assert not found


def test_a_metric_that_answered_on_one_side_only_is_not_compared() -> None:
    config = _config("noqa")

    assert not _loosened(config, config, before={}, after={"noqa": 0})


def test_removing_a_metric_loosens() -> None:
    assert _loosened(_config("noqa", "other"), _config("other")) == (
        Loosening("noqa", "removed"),
    )


def test_ignoring_a_metric_loosens() -> None:
    own = _config("noqa", check={"ignore": ["noqa"]})

    assert _loosened(_config("noqa"), own) == (
        Loosening("noqa", "moved to [check] ignore"),
    )


def test_a_metric_the_base_ignored_is_free_to_go() -> None:
    base = _config("noqa", "loc", check={"ignore": ["loc"]})

    assert not _loosened(base, _config("noqa"))


def test_a_metric_with_no_diff_variant_never_decided_a_check() -> None:
    assert not _loosened(_config("noqa", kind="no_diff"), _config("other"))


def test_softening_the_policy_loosens() -> None:
    base = _config("noqa", check={"policy": "any"})

    assert _loosened(base, _config("noqa")) == (
        Loosening("[check] policy", "any to sum"),
    )


def test_hardening_the_policy_does_not() -> None:
    own = _config("noqa", check={"policy": "any"})

    assert not _loosened(_config("noqa"), own)


def test_turning_strict_off_loosens() -> None:
    base = _config("noqa", check={"strict": True})

    assert _loosened(base, _config("noqa")) == (
        Loosening("[check] strict", "turned off"),
    )


def test_a_changed_template_module_loosens() -> None:
    config = _config("noqa")

    found = _loosened(config, config, modules=(PurePath("pack/tools.py"),))

    assert found == (Loosening("pack/tools.py", "template module changed"),)


def test_only_loosening_with_company_fails() -> None:
    loosened = (Loosening("noqa", "removed"),)

    assert not StrictVerdict(loosened=loosened).failed
    assert not StrictVerdict(alongside=(PurePath("a.py"),)).failed
    assert StrictVerdict(loosened=loosened, alongside=(PurePath("a.py"),)).failed
