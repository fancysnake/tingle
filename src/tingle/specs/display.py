"""How a measured value is turned into a severity emoji.

The ladder is fixed and ordered: the first band whose ceiling the ratio
(value / guide) fits under wins. Zero is not a band but a state — no debt
at all is worth celebrating, however generous the guide.
"""

from __future__ import annotations

#: Shown when a metric measures nothing at all.
EMOJI_ZERO = "🎉"

#: (inclusive ratio ceiling, emoji), lowest ceiling first.
EMOJI_BANDS: tuple[tuple[float, str], ...] = (
    (0.25, "🦠"),
    (0.50, "⚠️"),
    (1.00, "🚨"),
    (2.00, "🔥"),
)

#: Shown past the last band's ceiling: more than twice the guide.
EMOJI_OVER = "💀"
