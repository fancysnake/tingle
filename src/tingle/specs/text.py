"""What makes a file unreadable to a metric."""

from __future__ import annotations

#: Bytes sniffed for a NUL before a file is called binary. Git looks at the
#: same-sized window, so a file tingle skips is one git also treats as binary.
BINARY_SNIFF_BYTES = 8192
