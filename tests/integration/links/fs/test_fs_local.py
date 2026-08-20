from __future__ import annotations

from pathlib import Path, PurePath

from tingle.links.fs.local import LocalProjectFiles


def test_walk_yields_relative_files_sorted(tmp_path: Path) -> None:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "b.py").write_text("b")
    (tmp_path / "src" / "pkg" / "a.py").write_text("a")
    (tmp_path / "README.md").write_text("readme")

    files = list(LocalProjectFiles(tmp_path).walk())

    assert files == [
        PurePath("README.md"),
        PurePath("src/pkg/a.py"),
        PurePath("src/pkg/b.py"),
    ]


def test_walk_includes_dot_directories(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("x")

    files = list(LocalProjectFiles(tmp_path).walk())

    assert PurePath(".git/config") in files


def test_read_returns_raw_bytes(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("print('hi')\n")

    assert LocalProjectFiles(tmp_path).read(PurePath("a.py")) == b"print('hi')\n"


def test_read_does_not_judge_what_is_readable(tmp_path: Path) -> None:
    """Binary and undecodable files come back verbatim; mills decides."""
    (tmp_path / "blob.bin").write_bytes(b"\x00\x01\x02")
    (tmp_path / "latin.txt").write_bytes(b"calf\xe9")

    files = LocalProjectFiles(tmp_path)
    assert files.read(PurePath("blob.bin")) == b"\x00\x01\x02"
    assert files.read(PurePath("latin.txt")) == b"calf\xe9"


def test_read_missing_returns_none(tmp_path: Path) -> None:
    assert LocalProjectFiles(tmp_path).read(PurePath("nope.txt")) is None


def test_exists(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("")

    files = LocalProjectFiles(tmp_path)
    assert files.exists(PurePath("a.py"))
    assert not files.exists(PurePath("b.py"))


def test_walk_follows_a_link_to_a_file(tmp_path: Path) -> None:
    (tmp_path / "real.py").write_text("x")
    (tmp_path / "link.py").symlink_to(tmp_path / "real.py")

    files = list(LocalProjectFiles(tmp_path).walk())

    assert files == [PurePath("link.py"), PurePath("real.py")]


def test_walk_does_not_descend_into_a_linked_directory(tmp_path: Path) -> None:
    """A link to a directory is not walked, so a cycle cannot hang the walk."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text("a")
    (tmp_path / "mirror").symlink_to(tmp_path / "pkg", target_is_directory=True)

    files = list(LocalProjectFiles(tmp_path).walk())

    assert files == [PurePath("pkg/a.py")]


def test_walk_skips_a_broken_link(tmp_path: Path) -> None:
    (tmp_path / "gone.py").symlink_to(tmp_path / "nowhere.py")
    (tmp_path / "real.py").write_text("x")

    assert list(LocalProjectFiles(tmp_path).walk()) == [PurePath("real.py")]
