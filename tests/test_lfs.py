import logging
import os
from pathlib import Path

import pytest

from fusion_export.lfs import F3D_PATTERN, F3D_RULE, PRE_PUSH_HOOK, Wiring, ensure_lfs


class FakeGit:
    """Reports a path tracked when preset, or when its directory's .gitattributes has F3D_RULE."""

    def __init__(self, common_dir: Path, available: bool = True, tracked: bool = False) -> None:
        self.available = available
        self.tracked = tracked
        self._common_dir = common_dir
        self.queries: list[tuple[Path, Path]] = []

    def lfs_available(self) -> bool:
        return self.available

    def common_dir(self, repo: Path) -> Path:
        return self._common_dir

    def lfs_tracked(self, repo: Path, path: Path) -> bool:
        self.queries.append((repo, path))
        attributes = path.parent / ".gitattributes"
        return self.tracked or (
            attributes.is_file() and F3D_RULE in attributes.read_text().splitlines(keepends=True)
        )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / ".git" / "hooks").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def directory(repo: Path) -> Path:
    d = repo / "boards" / "fan_controller"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def path(directory: Path) -> Path:
    return directory / "enclosure.f3d"


@pytest.fixture
def git(repo: Path) -> FakeGit:
    return FakeGit(repo / ".git")


def attributes(directory: Path) -> str | None:
    """The directory's .gitattributes text, None when absent."""
    path = directory / ".gitattributes"
    return path.read_text() if path.exists() else None


def hook(repo: Path) -> Path:
    return repo / ".git" / "hooks" / "pre-push"


def test_rule_has_no_slash():
    assert F3D_PATTERN == "*.f3d"
    assert F3D_RULE == "*.f3d filter=lfs diff=lfs merge=lfs -text\n"


def test_hook_constant_is_git_lfs_pre_push():
    assert PRE_PUSH_HOOK.startswith("#!/bin/sh\n")
    assert PRE_PUSH_HOOK.endswith('git lfs pre-push "$@"\n')


def test_asks_git_about_the_path(repo, path, git):
    ensure_lfs(repo, path, git)
    assert git.queries == [(repo, path)]


def test_creates_gitattributes_in_file_dir_when_untracked(repo, directory, path, git):
    result = ensure_lfs(repo, path, git)
    assert attributes(directory) == F3D_RULE
    assert not (repo / ".gitattributes").exists()
    assert result.tracked


def test_appends_rule_after_other_rules(repo, directory, path, git):
    other = "*.png filter=lfs diff=lfs merge=lfs -text\n*.f3d -text\n"
    (directory / ".gitattributes").write_text(other)
    result = ensure_lfs(repo, path, git)
    assert attributes(directory) == other + F3D_RULE
    assert result.tracked


def test_adds_newline_before_rule_when_missing(repo, directory, path, git):
    (directory / ".gitattributes").write_text("*.png binary")
    ensure_lfs(repo, path, git)
    assert attributes(directory) == "*.png binary\n" + F3D_RULE


def test_leaves_attributes_when_tracked(repo, directory, path):
    git = FakeGit(repo / ".git", tracked=True)
    result = ensure_lfs(repo, path, git)
    assert not (directory / ".gitattributes").exists()
    assert not (repo / ".gitattributes").exists()
    assert not result.tracked


def test_writes_executable_hook_when_missing(repo, path, git):
    result = ensure_lfs(repo, path, git)
    assert hook(repo).is_file()
    assert hook(repo).read_text() == PRE_PUSH_HOOK
    assert os.access(hook(repo), os.X_OK)
    assert result.hook_written


def test_creates_hooks_dir(tmp_path):
    git = FakeGit(tmp_path / "common")
    ensure_lfs(tmp_path, tmp_path / "lid.f3d", git)
    assert (tmp_path / "common" / "hooks" / "pre-push").is_file()
    assert (tmp_path / "common" / "hooks" / "pre-push").read_text() == PRE_PUSH_HOOK


def test_leaves_existing_hook(repo, path, git):
    hook(repo).write_text("#!/bin/sh\necho mine\n")
    result = ensure_lfs(repo, path, git)
    assert hook(repo).read_text() == "#!/bin/sh\necho mine\n"
    assert not result.hook_written


def test_skips_when_lfs_unavailable(repo, directory, path, caplog):
    git = FakeGit(repo / ".git", available=False)
    with caplog.at_level(logging.INFO, logger="fusion_export.lfs"):
        result = ensure_lfs(repo, path, git)
    assert result == Wiring(skipped=True)
    assert git.queries == []
    assert not (directory / ".gitattributes").exists()
    assert not hook(repo).exists()
    assert "skipped" in caplog.text


def test_logs_wiring(repo, directory, path, git, caplog):
    with caplog.at_level(logging.INFO, logger="fusion_export.lfs"):
        ensure_lfs(repo, path, git)
    assert F3D_PATTERN in caplog.text
    assert str(directory) in caplog.text
    assert "pre-push" in caplog.text


def test_idempotent(repo, directory, path, git):
    first = ensure_lfs(repo, path, git)
    second = ensure_lfs(repo, path, git)
    assert first == Wiring(tracked=True, hook_written=True)
    assert second == Wiring()
    assert attributes(directory) == F3D_RULE
