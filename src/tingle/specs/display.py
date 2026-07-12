"""How a measured value is turned into a severity emoji.

The ladder is fixed and ordered: the first band whose ceiling the ratio
fits under wins. Zero is not a band but a state — no debt at all is worth
celebrating, however generous the guide.

The ratio is logarithmic, and the guide it is measured against is a
density: one unit of full-size debt per LOC_PER_GUIDE lines. Both are
answers to the same failure. A linear ratio against a fixed guide of 100
put 21 of one real project's 26 metrics on the same rung — a ladder that
ranks nothing. Debt does not hurt linearly either: the tenth `# type:
ignore` costs more than the hundredth.

Every emoji here must be a single codepoint of East Asian Width "W", so a
terminal draws it in the two cells the width calculation assumes. The
warning sign (U+26A0 U+FE0F) is not: it is a text-default character wearing
a variation selector, width "N", which terminals draw in one cell and clip
in half. Anything needing a variation selector to look like an emoji is the
wrong choice, however apt.
"""

from __future__ import annotations

#: Lines of code one unit of full-size debt is worth: the derived guide is
#: LOC / this. Small on purpose -- the log base has to be a density. An
#: earlier sketch used LOC * 10, which put the top rung at ten billion
#: occurrences and left every real metric back on the bottom one.
LOC_PER_GUIDE = 100

#: Shown when a metric measures nothing at all.
EMOJI_ZERO = "🎉"

#: (inclusive ratio ceiling, emoji), lowest ceiling first.
EMOJI_BANDS: tuple[tuple[float, str], ...] = (
    (0.25, "🦠"),
    (0.50, "🚧"),
    (1.00, "🚨"),
    (2.00, "🔥"),
)

#: Shown past the last band's ceiling: more than twice the guide.
EMOJI_OVER = "💀"
