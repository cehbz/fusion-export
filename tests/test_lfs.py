import logging
import os
from pathlib import Path

import pytest

from fusion_export.lfs import CAD_PATTERN, PRE_PUSH_HOOK, Wiring, ensure_lfs

RULE = f"{CAD_PATTERN} filter=lfs diff=lfs merge=lfs -text\n"


class FakeGit:
    def __init__(self, common_dir: Path, available: bool = True) -> None:
        self.available = available
        self._common_dir = common_dir

    def lfs_available(self) -> bool:
        return self.available

    def common_dir(self, repo: Path) -> Path:
        return self._common_dir


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / ".git" / "hooks").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def git(repo: Path) -> FakeGit:
    return FakeGit(repo / ".git")


def hook(repo: Path) -> Path:
    return repo / ".git" / "hooks" / "pre-push"


def test_hook_constant_is_git_lfs_pre_push():
    assert PRE_PUSH_HOOK.startswith("#!/bin/sh\n")
    assert PRE_PUSH_HOOK.endswith('git lfs pre-push "$@"\n')


def test_creates_gitattributes_when_missing(repo, git):
    result = ensure_lfs(repo, git)
    assert (repo / ".gitattributes").read_text() == RULE
    assert result.tracked


def test_appends_rule_after_other_rules(repo, git):
    other = (
        "*.png filter=lfs diff=lfs merge=lfs -text\n"
        f"{CAD_PATTERN} -text\n"
        f"# {CAD_PATTERN} filter=lfs\n"
    )
    (repo / ".gitattributes").write_text(other)
    result = ensure_lfs(repo, git)
    assert (repo / ".gitattributes").read_text() == other + RULE
    assert result.tracked


def test_adds_newline_before_rule_when_missing(repo, git):
    (repo / ".gitattributes").write_text("*.png binary")
    ensure_lfs(repo, git)
    assert (repo / ".gitattributes").read_text() == "*.png binary\n" + RULE


def test_leaves_existing_rule(repo, git):
    text = "*.png binary\n" + RULE
    (repo / ".gitattributes").write_text(text)
    result = ensure_lfs(repo, git)
    assert (repo / ".gitattributes").read_text() == text
    assert not result.tracked


def test_writes_executable_hook_when_missing(repo, git):
    result = ensure_lfs(repo, git)
    assert hook(repo).is_file()
    assert hook(repo).read_text() == PRE_PUSH_HOOK
    assert os.access(hook(repo), os.X_OK)
    assert result.hook_written


def test_creates_hooks_dir(tmp_path):
    git = FakeGit(tmp_path / "common")
    ensure_lfs(tmp_path, git)
    assert (tmp_path / "common" / "hooks" / "pre-push").is_file()
    assert (tmp_path / "common" / "hooks" / "pre-push").read_text() == PRE_PUSH_HOOK


def test_leaves_existing_hook(repo, git):
    hook(repo).write_text("#!/bin/sh\necho mine\n")
    result = ensure_lfs(repo, git)
    assert hook(repo).read_text() == "#!/bin/sh\necho mine\n"
    assert not result.hook_written


def test_skips_when_lfs_unavailable(repo, caplog):
    git = FakeGit(repo / ".git", available=False)
    with caplog.at_level(logging.INFO, logger="fusion_export.lfs"):
        result = ensure_lfs(repo, git)
    assert result == Wiring(skipped=True)
    assert not (repo / ".gitattributes").exists()
    assert not hook(repo).exists()
    assert "skipped" in caplog.text


def test_logs_wiring(repo, git, caplog):
    with caplog.at_level(logging.INFO, logger="fusion_export.lfs"):
        ensure_lfs(repo, git)
    assert CAD_PATTERN in caplog.text
    assert "pre-push" in caplog.text


def test_idempotent(repo, git):
    first = ensure_lfs(repo, git)
    second = ensure_lfs(repo, git)
    assert first == Wiring(tracked=True, hook_written=True)
    assert second == Wiring()
    assert (repo / ".gitattributes").read_text() == RULE
