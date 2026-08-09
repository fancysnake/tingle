from __future__ import annotations

import subprocess
from pathlib import Path, PurePath

import pytest

from tingle.links.git.cli import GitCli
from tingle.pacts.diff import DiffSourceError, FileDiff, FileStatus
from tingle.pacts.metrics import BINARY_SNIFF_BYTES


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    return repo


def _commit_all(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)


def _branch_repo(tmp_path: Path, base_content: str) -> Path:
    """Repo with main holding src/a.py = base_content, on branch `feature`."""
    repo = _repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "a.py").write_text(base_content)
    _commit_all(repo, "base")
    _git(repo, "checkout", "-b", "feature")
    return repo


def _by_path(files: tuple[FileDiff, ...]) -> dict[str, FileDiff]:
    return {str(diff.path): diff for diff in files}


def test_added_and_removed_lines(tmp_path: Path) -> None:
    repo = _branch_repo(tmp_path, "one\ntwo\nthree\n")
    (repo / "src" / "a.py").write_text("one\nTWO\nthree\nfour\nfive\n")
    _commit_all(repo, "change")

    diff = GitCli(repo).branch_diff("main")

    file = _by_path(diff.files)["src/a.py"]
    assert file.status is FileStatus.MODIFIED
    assert file.removed_lines == frozenset({2})
    assert file.added_lines == frozenset({2, 4, 5})


def test_pure_addition_zero_count_hunk(tmp_path: Path) -> None:
    repo = _branch_repo(tmp_path, "one\ntwo\n")
    (repo / "src" / "a.py").write_text("one\ntwo\nthree\nfour\n")

    diff = GitCli(repo).branch_diff("main")

    file = _by_path(diff.files)["src/a.py"]
    assert file.removed_lines == frozenset()
    assert file.added_lines == frozenset({3, 4})


def test_pure_deletion_zero_count_hunk(tmp_path: Path) -> None:
    repo = _branch_repo(tmp_path, "one\ntwo\nthree\n")
    (repo / "src" / "a.py").write_text("one\n")

    diff = GitCli(repo).branch_diff("main")

    file = _by_path(diff.files)["src/a.py"]
    assert file.removed_lines == frozenset({2, 3})
    assert file.added_lines == frozenset()


def test_single_line_change_omitted_count(tmp_path: Path) -> None:
    repo = _branch_repo(tmp_path, "one\n")
    (repo / "src" / "a.py").write_text("ONE\n")

    diff = GitCli(repo).branch_diff("main")

    file = _by_path(diff.files)["src/a.py"]
    assert file.removed_lines == frozenset({1})
    assert file.added_lines == frozenset({1})


def test_created_and_deleted_files(tmp_path: Path) -> None:
    repo = _branch_repo(tmp_path, "one\n")
    (repo / "src" / "new.py").write_text("a\nb\n")
    (repo / "src" / "a.py").unlink()
    _commit_all(repo, "swap")

    files = _by_path(GitCli(repo).branch_diff("main").files)

    assert files["src/new.py"].status is FileStatus.ADDED
    assert files["src/new.py"].added_lines == frozenset({1, 2})
    assert files["src/a.py"].status is FileStatus.DELETED
    assert files["src/a.py"].removed_lines == frozenset({1})


def test_binary_file_has_status_but_no_lines(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "blob.bin").write_bytes(b"\x00\x01")
    _commit_all(repo, "base")
    _git(repo, "checkout", "-b", "feature")
    (repo / "blob.bin").write_bytes(b"\x00\x02\x03")

    files = _by_path(GitCli(repo).branch_diff("main").files)

    assert files["blob.bin"].status is FileStatus.MODIFIED
    assert files["blob.bin"].added_lines == frozenset()
    assert files["blob.bin"].removed_lines == frozenset()


def test_mode_only_change(tmp_path: Path) -> None:
    repo = _branch_repo(tmp_path, "one\n")
    (repo / "src" / "a.py").chmod(0o755)

    files = _by_path(GitCli(repo).branch_diff("main").files)

    assert files["src/a.py"].status is FileStatus.MODIFIED
    assert files["src/a.py"].added_lines == frozenset()


def test_unicode_and_space_filename(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "keep.py").write_text("x\n")
    _commit_all(repo, "base")
    _git(repo, "checkout", "-b", "feature")
    (repo / "zażółć plik.py").write_text("a\nb\n")
    _commit_all(repo, "unicode")

    files = _by_path(GitCli(repo).branch_diff("main").files)

    assert files["zażółć plik.py"].status is FileStatus.ADDED
    assert files["zażółć plik.py"].added_lines == frozenset({1, 2})


def test_untracked_files_count_as_fully_added(tmp_path: Path) -> None:
    repo = _branch_repo(tmp_path, "one\n")
    (repo / "notes.txt").write_text("a\nb\nc\n")
    (repo / "blob.bin").write_bytes(b"\x00\x01")

    files = _by_path(GitCli(repo).branch_diff("main").files)

    assert files["notes.txt"].status is FileStatus.ADDED
    assert files["notes.txt"].added_lines == frozenset({1, 2, 3})
    assert files["blob.bin"].status is FileStatus.ADDED
    assert files["blob.bin"].added_lines == frozenset()


def test_an_untracked_file_that_is_not_utf8_still_adds_its_lines(
    tmp_path: Path,
) -> None:
    """No NUL, so git would diff it as text, so its lines are added lines.

    Whether a metric may read it is decided later, in mills, and the
    adapter does not get a second opinion on that here.
    """
    repo = _branch_repo(tmp_path, "one\n")
    (repo / "latin.txt").write_bytes(b"calf\xe9\n")

    files = _by_path(GitCli(repo).branch_diff("main").files)

    assert files["latin.txt"].status is FileStatus.ADDED
    assert files["latin.txt"].added_lines == frozenset({1})


def test_the_sniff_window_is_the_one_git_itself_uses(tmp_path: Path) -> None:
    """The claim the constant makes, checked against the git on this machine.

    A NUL inside the window makes a file binary and a NUL just past it
    does not -- for the adapter, and for git, which is the whole reason
    the number is what it is.
    """
    repo = _branch_repo(tmp_path, "one\n")
    (repo / "inside.txt").write_bytes(b"a" * (BINARY_SNIFF_BYTES - 1) + b"\0")
    (repo / "outside.txt").write_bytes(b"a" * BINARY_SNIFF_BYTES + b"\0")

    files = _by_path(GitCli(repo).branch_diff("main").files)

    assert files["inside.txt"].added_lines == frozenset()
    assert files["outside.txt"].added_lines == frozenset({1})
    assert _git_says_binary(repo, "inside.txt")
    assert not _git_says_binary(repo, "outside.txt")


def _git_says_binary(repo: Path, name: str) -> bool:
    """Ask git whether it would diff this file as text."""
    result = subprocess.run(
        ["git", "diff", "--no-index", "--no-ext-diff", "/dev/null", name],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    return "Binary files" in result.stdout


def test_gitignored_untracked_files_are_excluded(tmp_path: Path) -> None:
    repo = _branch_repo(tmp_path, "one\n")
    (repo / ".gitignore").write_text("*.log\n")
    (repo / "debug.log").write_text("x\n")

    files = _by_path(GitCli(repo).branch_diff("main").files)

    assert "debug.log" not in files


def test_rm_cached_file_is_not_double_counted(tmp_path: Path) -> None:
    repo = _branch_repo(tmp_path, "one\ntwo\n")
    _git(repo, "rm", "--cached", "src/a.py")

    files = GitCli(repo).branch_diff("main").files

    matching = [diff for diff in files if str(diff.path) == "src/a.py"]
    assert len(matching) == 1


def test_commits_on_base_after_branching_do_not_pollute(tmp_path: Path) -> None:
    repo = _branch_repo(tmp_path, "one\n")
    (repo / "src" / "a.py").write_text("one\nfeature\n")
    _commit_all(repo, "feature work")
    _git(repo, "checkout", "main")
    (repo / "src" / "other.py").write_text("landed later\n")
    _commit_all(repo, "later main work")
    _git(repo, "checkout", "feature")

    files = _by_path(GitCli(repo).branch_diff("main").files)

    assert "src/other.py" not in files
    assert files["src/a.py"].added_lines == frozenset({2})


def test_config_root_in_repo_subdirectory(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    pkg = repo / "pkg"
    pkg.mkdir()
    (pkg / "inside.py").write_text("one\n")
    (repo / "outside.py").write_text("one\n")
    _commit_all(repo, "base")
    _git(repo, "checkout", "-b", "feature")
    (pkg / "inside.py").write_text("one\ntwo\n")
    (repo / "outside.py").write_text("one\ntwo\n")

    git = GitCli(pkg)
    files = _by_path(git.branch_diff("main").files)

    assert list(files) == ["inside.py"]
    assert git.read_base(PurePath("inside.py")) == b"one\n"


def test_read_base_returns_merge_base_content(tmp_path: Path) -> None:
    repo = _branch_repo(tmp_path, "original\n")
    (repo / "src" / "a.py").write_text("changed\n")
    (repo / "src" / "new.py").write_text("brand new\n")

    git = GitCli(repo)
    git.branch_diff("main")

    assert git.read_base(PurePath("src/a.py")) == b"original\n"
    assert git.read_base(PurePath("src/new.py")) is None


def test_read_base_before_branch_diff_raises(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    with pytest.raises(DiffSourceError, match="before branch_diff"):
        GitCli(repo).read_base(PurePath("x"))


def test_origin_prefixed_base_fallback(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "a.py").write_text("one\n")
    _commit_all(repo, "base")
    _git(repo, "branch", "origin/trunk")
    _git(repo, "checkout", "-b", "feature")
    (repo / "a.py").write_text("one\ntwo\n")

    diff = GitCli(repo).branch_diff("trunk")

    assert diff.base_ref == "origin/trunk"
    assert _by_path(diff.files)["a.py"].added_lines == frozenset({2})


def test_missing_base_ref_raises(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "a.py").write_text("x\n")
    _commit_all(repo, "base")

    with pytest.raises(DiffSourceError, match='base ref "nope" not found'):
        GitCli(repo).branch_diff("nope")


def test_unrelated_histories_raise(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "a.py").write_text("x\n")
    _commit_all(repo, "base")
    _git(repo, "checkout", "--orphan", "island")
    _commit_all(repo, "unrelated root")

    with pytest.raises(DiffSourceError, match="no common ancestor"):
        GitCli(repo).branch_diff("main")


def test_unborn_head_raises(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    with pytest.raises(DiffSourceError):
        GitCli(repo).branch_diff("main")


def test_not_a_repo_raises(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()

    with pytest.raises(DiffSourceError):
        GitCli(plain).branch_diff("main")


def test_hostile_user_diff_config_is_neutralized(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _git(repo, "config", "diff.noprefix", "true")
    _git(repo, "config", "diff.mnemonicPrefix", "true")
    _git(repo, "config", "core.quotepath", "true")
    (repo / "zażółć.py").write_text("one\n")
    _commit_all(repo, "base")
    _git(repo, "checkout", "-b", "feature")
    (repo / "zażółć.py").write_text("one\ntwo\n")

    files = _by_path(GitCli(repo).branch_diff("main").files)

    assert files["zażółć.py"].added_lines == frozenset({2})
