"""Git LFS wiring for a repo's cad/*.f3d exports."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)

CAD_PATTERN = "cad/*.f3d"

# The line `git lfs track` writes for CAD_PATTERN.
CAD_RULE = f"{CAD_PATTERN} filter=lfs diff=lfs merge=lfs -text\n"

# The pre-push hook `git lfs install` writes (git-lfs 3.8).
PRE_PUSH_HOOK = (
    "#!/bin/sh\n"
    "command -v git-lfs >/dev/null 2>&1 || { printf >&2 \"\\n%s\\n\\n\" "
    "\"This repository is configured for Git LFS but 'git-lfs' was not found on your path. "
    "If you no longer wish to use Git LFS, remove this hook by deleting the 'pre-push' file "
    "in the hooks directory (set by 'core.hookspath'; usually '.git/hooks').\"; exit 2; }\n"
    'git lfs pre-push "$@"\n'
)


class Git(Protocol):
    """Git operations LFS wiring needs."""

    def lfs_available(self) -> bool: ...

    def common_dir(self, repo: Path) -> Path: ...


@dataclass(frozen=True)
class Wiring:
    """What ensure_lfs did."""

    skipped: bool = False
    tracked: bool = False
    hook_written: bool = False


def ensure_lfs(repo: Path, git: Git) -> Wiring:
    """Add CAD_RULE to .gitattributes and write the native pre-push hook, where missing.

    Writes files only; git-lfs is not run, so no hooks reach core.hooksPath.
    """
    if not git.lfs_available():
        logger.warning("LFS wiring skipped for %s: git-lfs not found", repo)
        return Wiring(skipped=True)
    tracked = False
    attributes = repo / ".gitattributes"
    if not has_lfs_rule(attributes, CAD_PATTERN):
        append_rule(attributes, CAD_RULE)
        logger.info("LFS tracking %s in %s", CAD_PATTERN, repo)
        tracked = True
    hook = git.common_dir(repo) / "hooks" / "pre-push"
    hook_written = False
    if not hook.exists() and not hook.is_symlink():
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text(PRE_PUSH_HOOK)
        hook.chmod(0o755)
        logger.info("LFS pre-push hook installed at %s", hook)
        hook_written = True
    return Wiring(tracked=tracked, hook_written=hook_written)


def has_lfs_rule(gitattributes: Path, pattern: str) -> bool:
    """Whether gitattributes has a line for pattern with filter=lfs."""
    try:
        text = gitattributes.read_text()
    except FileNotFoundError:
        return False
    for line in text.splitlines():
        fields = line.split()
        if fields and fields[0] == pattern and "filter=lfs" in fields[1:]:
            return True
    return False


def append_rule(gitattributes: Path, rule: str) -> None:
    """Append rule as a final line, creating the file and terminating a partial last line."""
    try:
        text = gitattributes.read_text()
    except FileNotFoundError:
        text = ""
    if text and not text.endswith("\n"):
        text += "\n"
    gitattributes.write_text(text + rule)
