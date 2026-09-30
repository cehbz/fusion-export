"""Export a saved design's Fusion archive into its git repo."""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from enum import Enum
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


class Severity(Enum):
    """How badly an export went: WARNING when it went ahead or was skipped, ERROR when it failed."""

    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class Alert:
    """An export outcome the user must see."""

    severity: Severity
    title: str
    message: str


class Alerts(Protocol):
    """Where alerts reach the user."""

    def send(self, alert: Alert) -> None: ...


class ArchiveExporter(Protocol):
    """Writes the saved design as a Fusion archive (.f3d)."""

    def linked_components(self) -> list[str]:
        """Names of the design's components linked from other designs."""
        ...

    def write_archive(self, path: Path) -> bool:
        """Write the archive to path; whether the export succeeded."""
        ...


def _send(alerts: Alerts, alert: Alert) -> None:
    """Send alert, logging instead of raising when alerts fails."""
    try:
        alerts.send(alert)
    except Exception:
        logger.warning("Could not send alert %r", alert.title, exc_info=True)


def _describe(error: Exception) -> str:
    return f"{type(error).__name__}: {error}"


def _warn_if_linked(design_name: str, exporter: ArchiveExporter, alerts: Alerts) -> None:
    """Warn that the archive is not self-contained when the design has linked components."""
    try:
        linked = exporter.linked_components()
    except Exception as e:
        logger.warning("Could not list linked components of %r", design_name, exc_info=True)
        _send(
            alerts,
            Alert(
                Severity.WARNING,
                "Fusion export: linked components unknown",
                f"Could not list linked components of {design_name!r}: {_describe(e)}",
            ),
        )
        return
    if linked:
        message = (
            f"Export of {design_name!r} links other designs, so the .f3d is not self-contained: "
            + ", ".join(linked)
        )
        logger.warning("%s", message)
        _send(alerts, Alert(Severity.WARNING, "Fusion export not self-contained", message))


def _failed(alerts: Alerts, message: str) -> None:
    logger.error("%s", message)
    _send(alerts, Alert(Severity.ERROR, "Fusion export failed", message))


def export_design(
    design_name: str, projects_root: Path, git: Git, exporter: ArchiveExporter, alerts: Alerts
) -> Path | None:
    """Export the design to its resolved .f3d path; the path written, else None.

    The archive is written to a hidden temporary directory beside the target and
    renamed onto the target, so a failed export leaves an existing target as
    it was. Staging directories left by interrupted exports are removed first.
    Never raises. Skips, linked components, missing git-lfs and failures are
    logged and sent to alerts; a successful export is only logged.
    """
    try:
        target = resolve(design_name, projects_root)
        if isinstance(target, Skip):
            message = f"Export of {design_name!r} skipped: {target.reason}"
            logger.info("%s", message)
            _send(alerts, Alert(Severity.WARNING, "Fusion export skipped", message))
            return None
        path = target.path
        _warn_if_linked(design_name, exporter, alerts)
        if ensure_lfs(target.repo, path, git).skipped:
            _send(
                alerts,
                Alert(
                    Severity.WARNING,
                    "Fusion export: git-lfs missing",
                    f"Export of {design_name!r}: git-lfs not found, so {path} is not LFS-tracked "
                    f"and no pre-push hook was installed in {target.repo}",
                ),
            )
        _remove_stale_staging(path.parent)
        staging = Path(tempfile.mkdtemp(prefix=STAGING_PREFIX, dir=path.parent))
        try:
            archive = staging / path.name
            if not exporter.write_archive(archive):
                _failed(alerts, f"Export of {design_name!r} to {path} failed")
                return None
            if not archive.is_file():
                _failed(
                    alerts,
                    f"Export of {design_name!r} to {path} reported success but wrote no archive",
                )
                return None
            os.replace(archive, path)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        logger.info("Exported %r to %s", design_name, path)
        return path
    except Exception as e:
        logger.exception("Export of %r failed", design_name)
        _send(
            alerts,
            Alert(
                Severity.ERROR,
                "Fusion export failed",
                f"Export of {design_name!r} failed: {_describe(e)}",
            ),
        )
        return None
