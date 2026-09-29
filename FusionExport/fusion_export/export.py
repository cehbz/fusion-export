"""Export a saved design's Fusion archive into its repo's cad/ directory."""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Protocol

from .lfs import Git, ensure_lfs
from .resolve import resolve

logger = logging.getLogger(__name__)

STAGING_PREFIX = ".fusion-export-"


def _remove_stale_staging(cad: Path) -> None:
    """Remove staging directories left in cad/ by an interrupted export."""
    for entry in cad.iterdir():
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
    """Export the design to <repo>/cad/<part>.f3d; the target written, else None.

    The archive is written to a hidden temporary directory inside cad/ and
    renamed onto the target, so a failed export leaves an existing target as
    it was. Staging directories left by interrupted exports are removed first.
    Never raises: every failure is logged.
    """
    try:
        target = resolve(design_name, projects_root)
        if target is None:
            logger.info("Export of %r skipped: no repo for it under %s", design_name, projects_root)
            return None
        cad = target.parent
        cad.mkdir(exist_ok=True)
        ensure_lfs(cad.parent, target, git)
        _remove_stale_staging(cad)
        staging = Path(tempfile.mkdtemp(prefix=STAGING_PREFIX, dir=cad))
        try:
            archive = staging / target.name
            if not exporter.write_archive(archive):
                logger.error("Export of %r to %s failed", design_name, target)
                return None
            if not archive.is_file():
                logger.error(
                    "Export of %r to %s reported success but wrote no archive", design_name, target
                )
                return None
            os.replace(archive, target)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        logger.info("Exported %r to %s", design_name, target)
        return target
    except Exception:
        logger.exception("Export of %r failed", design_name)
        return None
