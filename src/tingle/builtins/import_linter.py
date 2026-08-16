"""Templates for import-linter: layer contracts not currently enforced."""

from __future__ import annotations

from tingle.pacts.config import MetricTemplate

__all__ = ["deferred_contracts", "ignored_imports"]

deferred_contracts = MetricTemplate(
    type="regex_count",
    name="deferred-import-contracts",
    group="architecture",
    description="Import-linter contracts commented out instead of enforced.",
    params={
        "pattern": r"^#\s*\[\[tool\.importlinter\.contracts\]\]",
        "flags": ["MULTILINE"],
    },
)

ignored_imports = MetricTemplate(
    type="regex_count",
    name="import-linter-ignores",
    group="architecture",
    description="`ignore_imports` entries excusing an import from a contract.",
    params={"pattern": r"^\s*ignore_imports\s*=", "flags": ["MULTILINE"]},
)
