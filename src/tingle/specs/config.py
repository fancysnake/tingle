"""Invariants of tingle configuration."""

import re

METRIC_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

IMPLICIT_RANGE_NAME = "(all files)"
IMPLICIT_RANGE_INCLUDE = ("**/*",)

TOML_LIST_DEFAULT_FILE = "pyproject.toml"
