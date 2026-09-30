"""Map a Fusion design name to its .f3d path in a git repo."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Target:
    """Where a design's archive goes: the git repo root and the .f3d path in it."""

    repo: Path
    path: Path


@dataclass(frozen=True)
class Skip:
    """Why a design name has no target."""

    reason: str


def resolve(design_name: str, projects_root: Path) -> Target | Skip:
    """The Target for a design named <repo>[-<dir>...][-<part>].

    <repo> is the longest hyphen-prefix of the name that is a directory
    directly under projects_root containing .git (directory or file). The
    remaining segments then walk down: at each level the longest hyphen-joined
    run of leading segments naming a subdirectory is entered. The file is
    <part>.f3d in the deepest directory reached, with <part> the segments left
    over, or <dir name>.f3d when none are. Names are matched exactly, even on
    case-insensitive filesystems; dot-directories and symlinks are not entered.
    A Skip stating the reason when no repo matches, the name contains "/",
    <part> is empty, "." or "..", or a directory is unreadable.
    """
    if "/" in design_name:
        return Skip("the name contains '/'")
    names = _listing(projects_root)
    if names is None:
        return Skip(f"cannot read {projects_root}")
    parts = design_name.split("-")
    for n in range(len(parts), 0, -1):
        repo_name = "-".join(parts[:n])
        repo = projects_root / repo_name
        if repo_name in names and (repo / ".git").exists():
            return _walk(repo, parts[n:])
    return Skip(f"no repo under {projects_root} matches")


def _walk(repo: Path, rest: list[str]) -> Target | Skip:
    """The Target for the segments rest under repo, or a Skip."""
    directory = repo
    while rest:
        subdirs = _subdirectories(directory)
        if subdirs is None:
            return Skip(f"cannot read {directory}")
        for k in range(len(rest), 0, -1):
            run = "-".join(rest[:k])
            if run in subdirs:
                directory = directory / run
                rest = rest[k:]
                break
        else:
            break
    part = "-".join(rest) if rest else directory.name
    if part in ("", ".", ".."):
        return Skip(f"the file name would be {part!r}")
    return Target(repo, directory / f"{part}.f3d")


def _listing(directory: Path) -> set[str] | None:
    """Entry names in directory, None when unreadable."""
    try:
        return {p.name for p in directory.iterdir()}
    except OSError:
        return None


def _subdirectories(directory: Path) -> set[str] | None:
    """Names of directory's subdirectories, excluding dot-directories and symlinks."""
    try:
        return {
            p.name
            for p in directory.iterdir()
            if not p.name.startswith(".") and p.is_dir() and not p.is_symlink()
        }
    except OSError:
        return None
