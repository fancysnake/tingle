from __future__ import annotations

from pathlib import PurePath

from tingle.mills.text import decode_text, text_reader
from tingle.pacts.metrics import BINARY_SNIFF_BYTES


def test_decodes_utf8() -> None:
    assert decode_text(b"print('hi')\n") == "print('hi')\n"


def test_decodes_non_ascii_utf8() -> None:
    assert decode_text("café\n".encode()) == "café\n"


def test_missing_bytes_stay_missing() -> None:
    assert decode_text(None) is None


def test_empty_file_is_readable_and_empty() -> None:
    assert decode_text(b"") == ""


def test_a_nul_near_the_start_means_binary() -> None:
    assert decode_text(b"\x00\x01\x02") is None


def test_undecodable_bytes_are_unreadable() -> None:
    assert decode_text(b"calf\xe9") is None


def test_a_nul_past_the_sniff_window_is_not_sniffed() -> None:
    """The window is bounded, so a huge text file is not scanned end to end."""
    data = b"a" * BINARY_SNIFF_BYTES + b"\x00"

    assert decode_text(data) == "a" * BINARY_SNIFF_BYTES + "\x00"


def test_text_reader_decodes_what_the_adapter_read() -> None:
    read = text_reader({PurePath("a.py"): b"one\n"}.get)

    assert read(PurePath("a.py")) == "one\n"


def test_text_reader_passes_a_missing_file_through_as_none() -> None:
    empty: dict[PurePath, bytes] = {}
    read = text_reader(empty.get)

    assert read(PurePath("nope.py")) is None


def test_text_reader_applies_the_binary_rule() -> None:
    read = text_reader({PurePath("blob.bin"): b"\x00\x01"}.get)

    assert read(PurePath("blob.bin")) is None
