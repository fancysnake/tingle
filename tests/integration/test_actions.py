"""The jq filter the `pr-feedback` action finds its own comment with.

Real jq runs it over a page shaped like GitHub's REST issue comments; `gh
--jq` applies it to each page the same way.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[2]
OWN_COMMENT = ROOT / "actions" / "pr-feedback" / "own-comment.jq"

MARKER = "<!-- tingle-pr-feedback: default -->"
TOKEN_USER_ID = 41898282


def _own_comments(page: list[dict[str, object]]) -> list[int]:
    result = subprocess.run(
        ["jq", "--from-file", str(OWN_COMMENT)],
        input=json.dumps(page),
        env={**os.environ, "MARKER": MARKER, "TOKEN_USER_ID": str(TOKEN_USER_ID)},
        check=True,
        capture_output=True,
        text=True,
    )
    return [int(line) for line in result.stdout.split()]


def test_only_the_tokens_own_marker_comment_matches() -> None:
    page: list[dict[str, object]] = [
        {"id": 1, "user": {"id": 7}, "body": f"{MARKER}\nquoting the old report"},
        {"id": 2, "user": {"id": TOKEN_USER_ID}, "body": "another bot's note"},
        {"id": 3, "user": {"id": TOKEN_USER_ID}, "body": f"{MARKER}\n## tingle"},
    ]

    assert _own_comments(page) == [3]
