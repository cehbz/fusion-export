import os
import subprocess
from pathlib import Path

import pytest

from fusion_export.git import GIT_LFS_DIRS, SubprocessGit, find_tool
from fusion_export.lfs import F3D_RULE, PRE_PUSH_HOOK, Wiring, ensure_lfs

pytestmark = pytest.mark.integration

GIT = SubprocessGit.locate()


def _installed(name: str, dirs: tuple[str, ...]) -> Path | None:
    return next((Path(d, name) for d in dirs if os.access(Path(d, name), os.X_OK)), None)


# Located independently of the adapter under test.
TEST_GIT = _installed("git", ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"))
TEST_GIT_LFS = _installed("git-lfs", GIT_LFS_DIRS)


def write_global_config(path: Path, extra: str = "") -> None:
    path.write_text(
        "[user]\n\tname = Test\n\temail = test@example.com\n"
        "[init]\n\tdefaultBranch = main\n"
        '[filter "lfs"]\n'
        "\tclean = git-lfs clean -- %f\n"
        "\tsmudge = git-lfs smudge -- %f\n"
        "\tprocess = git-lfs filter-process\n"
        "\trequired = true\n" + extra
    )


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch) -> Path:
    if TEST_GIT is None or TEST_GIT_LFS is None:
        pytest.skip("git or git-lfs not installed")
    config = tmp_path / "gitconfig"
    write_global_config(config)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    for var in ("GIT_DIR", "GIT_WORK_TREE", "GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS"):
        monkeypatch.delenv(var, raising=False)
    return config


def run_git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        [str(TEST_GIT), *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


@pytest.fixture
def repo(tmp_path) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    run_git(path, "init", "-q")
    return path


def attributes(directory: Path) -> str | None:
    """The directory's .gitattributes text, None when absent."""
    path = directory / ".gitattributes"
    return path.read_text() if path.exists() else None


def native_hooks(repo: Path) -> Path:
    return repo / ".git" / "hooks"


def test_find_tool(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    first.mkdir()
    second.mkdir()
    (first / "tool").write_text("")
    exe = second / "tool"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    assert find_tool("tool", [str(first), str(second)]) == exe
    assert find_tool("missing", [str(first), str(second)]) is None


def test_locate_uses_absolute_paths():
    assert GIT.git is not None and GIT.git.is_absolute()
    assert GIT.git_lfs is not None and str(GIT.git_lfs.parent) in GIT_LFS_DIRS


def test_lfs_available():
    assert GIT.lfs_available()
    assert not SubprocessGit(TEST_GIT, None).lfs_available()


def test_common_dir(repo):
    assert GIT.common_dir(repo).resolve() == (repo / ".git").resolve()


def test_common_dir_of_worktree(repo):
    run_git(repo, "commit", "-q", "--allow-empty", "--no-verify", "-m", "init")
    worktree = repo.parent / "wt"
    run_git(repo, "worktree", "add", "-q", str(worktree))
    assert (worktree / ".git").is_file()
    assert GIT.common_dir(worktree).resolve() == (repo / ".git").resolve()


def test_hook_constant_matches_installed_git_lfs(repo):
    path = f"{TEST_GIT_LFS.parent}:{TEST_GIT.parent}:{os.environ.get('PATH', '')}"
    subprocess.run(
        [str(TEST_GIT_LFS), "install", "--local"],
        cwd=repo, env={**os.environ, "PATH": path}, check=True, capture_output=True,
    )
    assert (native_hooks(repo) / "pre-push").read_text() == PRE_PUSH_HOOK


def test_lfs_tracked_untracked_path(repo):
    assert not GIT.lfs_tracked(repo, repo / "cad" / "lid.f3d")


def test_lfs_tracked_root_rule_matches_nested_path(repo):
    (repo / ".gitattributes").write_text(F3D_RULE)
    assert GIT.lfs_tracked(repo, repo / "boards" / "fan_controller" / "enclosure.f3d")
    assert not GIT.lfs_tracked(repo, repo / "boards" / "notes.txt")


def test_lfs_tracked_per_directory_rule(repo):
    boards = repo / "boards"
    boards.mkdir()
    (boards / ".gitattributes").write_text(F3D_RULE)
    (repo / "docs").mkdir()
    assert GIT.lfs_tracked(repo, boards / "lid.f3d")
    assert GIT.lfs_tracked(repo, boards / "fan_controller" / "enclosure.f3d")
    assert not GIT.lfs_tracked(repo, repo / "docs" / "lid.f3d")
    assert not GIT.lfs_tracked(repo, repo / "lid.f3d")


@pytest.mark.parametrize("rule", ["*.f3d -filter\n", "*.f3d filter=other\n", "*.f3d !filter\n"])
def test_lfs_tracked_other_filter_values(repo, rule):
    (repo / ".gitattributes").write_text(rule)
    assert not GIT.lfs_tracked(repo, repo / "lid.f3d")


def test_lfs_tracked_non_ascii_path(repo):
    d = repo / "fan contrôleur"
    d.mkdir()
    (d / ".gitattributes").write_text(F3D_RULE)
    assert GIT.lfs_tracked(repo, d / "lid é.f3d")


def test_ensure_lfs_end_to_end(repo, tmp_path, isolated_config):
    gate = tmp_path / "gate-hooks"
    gate.mkdir()
    (gate / "commit-msg").write_text("#!/bin/sh\necho gate\n")
    write_global_config(isolated_config, f"[core]\n\thooksPath = {gate}\n")
    directory = repo / "boards" / "fan_controller"
    directory.mkdir(parents=True)
    path = directory / "enclosure.f3d"
    first = ensure_lfs(repo, path, GIT)
    second = ensure_lfs(repo, path, GIT)
    assert first.tracked
    assert second == Wiring()
    assert attributes(directory) == F3D_RULE
    assert not (repo / ".gitattributes").exists()
    assert sorted(p.name for p in gate.iterdir()) == ["commit-msg"]
    assert sorted(p.name for p in native_hooks(repo).iterdir() if not p.name.endswith(".sample")) == [
        "pre-push"
    ]
    assert (native_hooks(repo) / "pre-push").read_text() == PRE_PUSH_HOOK
    assert os.access(native_hooks(repo) / "pre-push", os.X_OK)


def test_ensure_lfs_leaves_path_covered_by_root_rule(repo):
    (repo / ".gitattributes").write_text(F3D_RULE)
    directory = repo / "boards"
    directory.mkdir()
    result = ensure_lfs(repo, directory / "lid.f3d", GIT)
    assert not result.tracked
    assert not (directory / ".gitattributes").exists()
    assert attributes(repo) == F3D_RULE
