from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from tingle.mills.services import SkillService
from tingle.mills.skill import PLACEHOLDER, SKILL_NAME, render
from tingle.pacts.config import Config, MetricSpec, RangeSpec

ESCAPES = MetricSpec(
    name="lint-escapes", type="regex_count", description="Silenced lint findings."
)
FILES = MetricSpec(name="python-files", type="file_count")


def _section(text: str, name: str) -> str:
    opening, closing = (
        f"<!-- tingle:metric {name} -->",
        f"<!-- /tingle:metric {name} -->",
    )
    return text.split(opening)[1].split(closing, maxsplit=1)[0]


def test_render_opens_with_the_frontmatter_an_agent_lists_the_skill_by() -> None:
    assert render(()).startswith(f"---\nname: {SKILL_NAME}\ndescription: >-\n")


def test_render_gives_every_metric_a_named_placeholder_section() -> None:
    text = render((ESCAPES, FILES))

    assert text.count(PLACEHOLDER) == len((ESCAPES, FILES)) + 1
    assert "### lint-escapes\n\nSilenced lint findings.\n" in _section(
        text, "lint-escapes"
    )
    assert PLACEHOLDER in _section(text, "lint-escapes")
    assert PLACEHOLDER in _section(text, "python-files")


def test_render_omits_the_description_a_metric_does_not_have() -> None:
    assert _section(render((FILES,)), "python-files").startswith(
        "\n### python-files\n\n<!-- tingle:placeholder"
    )


def test_render_states_the_rule_whatever_is_configured() -> None:
    text = render(())

    assert "Change the code until the marker is not needed." in text
    assert "branch of its own" in text
    assert "tingle:metric" not in text


def test_write_stores_the_rendered_skill_beside_the_config() -> None:
    store = MagicMock()
    root = Path("/project")
    config = Config(
        root=root,
        source=root / "tingle.toml",
        ranges={},
        metrics=(ESCAPES,),
        default_range=RangeSpec(name="all", include=("**/*",)),
    )

    assert SkillService(store=store).write(config) is store.create.return_value
    store.create.assert_called_once_with(root, name=SKILL_NAME, text=render((ESCAPES,)))
