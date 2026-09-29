"""Export a saved design's Fusion archive into its git repo."""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Protocol

from .lfs import Git, ensure_lfs
from .resolve import Skip, resolve

logger = logging.getLogger(__name__)

STAGING_PREFIX = ".fusion-export-"


def _remove_stale_staging(directory: Path) -> None:
    """Remove staging directories left in directory by an interrupted export."""
    for entry in directory.iterdir():
        if entry.name.startswith(STAGING_PREFIX) and entry.is_dir() and not entry.is_symlink():
            try:
                shutil.rmtree(entry)
                logger.info("Removed stale staging directory %s", entry)
            except OSError:
                logger.warning("Could not remove stale staging directory %s", entry, exc_info=True)


class ArchiveExporter(Protocol):
    """Writes the saved design as a Fusion archive (.f3d)."""

    def write_archive(self, path: Path) -> bool:
        """Write the archive to path; whether the export succeeded."""
        ...


def export_design(
    design_name: str, projects_root: Path, git: Git, exporter: ArchiveExporter
) -> Path | None:
    """Export the design to its resolved .f3d path; the path written, else None.

    The archive is written to a hidden temporary directory beside the target and
    renamed onto the target, so a failed export leaves an existing target as
    it was. Staging directories left by interrupted exports are removed first.
    Never raises: every failure is logged.
    """
    try:
        target = resolve(design_name, projects_root)
        if isinstance(target, Skip):
            logger.info("Export of %r skipped: %s", design_name, target.reason)
            return None
        path = target.path
        ensure_lfs(target.repo, path, git)
        _remove_stale_staging(path.parent)
        staging = Path(tempfile.mkdtemp(prefix=STAGING_PREFIX, dir=path.parent))
        try:
            archive = staging / path.name
            if not exporter.write_archive(archive):
                logger.error("Export of %r to %s failed", design_name, path)
                return None
            if not archive.is_file():
                logger.error(
                    "Export of %r to %s reported success but wrote no archive", design_name, path
                )
                return None
            os.replace(archive, path)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        logger.info("Exported %r to %s", design_name, path)
        return path
    except Exception:
        logger.exception("Export of %r failed", design_name)
        return None
