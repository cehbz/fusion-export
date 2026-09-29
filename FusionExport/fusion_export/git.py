"""Subprocess adapter for the lfs.Git port."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Iterable

GIT_DIRS = ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin")
GIT_LFS_DIRS = ("/opt/homebrew/bin", "/usr/local/bin")


def find_tool(name: str, dirs: Iterable[str]) -> Path | None:
    """First executable name in dirs."""
    for d in dirs:
        path = Path(d, name)
        if path.is_file() and os.access(path, os.X_OK):
            return path
    return None


class SubprocessGit:
    """lfs.Git over git and git-lfs run by absolute path."""

    def __init__(self, git: Path | None, git_lfs: Path | None) -> None:
        self.git = git
        self.git_lfs = git_lfs

    @classmethod
    def locate(cls) -> SubprocessGit:
        """Adapter over the tools found in GIT_DIRS and GIT_LFS_DIRS."""
        return cls(find_tool("git", GIT_DIRS), find_tool("git-lfs", GIT_LFS_DIRS))

    def lfs_available(self) -> bool:
        return self.git is not None and self.git_lfs is not None

    def common_dir(self, repo: Path) -> Path:
        out = self._run(
            [str(self.git), "rev-parse", "--path-format=absolute", "--git-common-dir"], repo
        )
        return Path(out.strip())

    def _env(self) -> dict[str, str]:
        dirs = [str(p.parent) for p in (self.git_lfs, self.git) if p is not None]
        return {**os.environ, "PATH": os.pathsep.join([*dirs, os.environ.get("PATH", "")])}

    def _run(self, args: list[str], repo: Path, env: dict[str, str] | None = None) -> str:
        return subprocess.run(
            args, cwd=repo, env=env or self._env(), check=True, capture_output=True, text=True
        ).stdout

