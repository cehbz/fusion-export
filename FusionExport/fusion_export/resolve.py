"""Map a Fusion design name to its .f3d path in a git repo."""

from pathlib import Path


def resolve(design_name: str, projects_root: Path) -> Path | None:
    """Return projects_root/<repo>/cad/<part>.f3d for a design named <repo>-<part>.

    <repo> is the longest hyphen-prefix of the name that is a directory
    directly under projects_root (exact name match, even on
    case-insensitive filesystems) containing .git (directory or file).
    None when no prefix matches, the part is empty, or the part could
    escape cad/ (contains "/" or is "." or "..").
    """
    if "/" in design_name:
        return None
    try:
        names = {p.name for p in projects_root.iterdir()}
    except OSError:
        return None
    parts = design_name.split("-")
    for n in range(len(parts), 0, -1):
        repo = "-".join(parts[:n])
        if repo in names and (projects_root / repo / ".git").exists():
            part = "-".join(parts[n:])
            if not part or part in (".", ".."):
                return None
            return projects_root / repo / "cad" / f"{part}.f3d"
    return None
