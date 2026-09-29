"""Fusion add-in: on every save, exports the design's .f3d into its project's repo."""

from __future__ import annotations

import logging
from pathlib import Path

import adsk.core
import adsk.fusion

from .fusion_export.export import export_design
from .fusion_export.git import SubprocessGit
from .fusion_export.log import PACKAGE, configure_logging

PROJECTS_ROOT = Path.home() / "projects"
LOG_DIR = Path.home() / "Library" / "Logs" / "fusion-export"

logger = logging.getLogger(f"{PACKAGE}.addin")

# Fusion drops handlers nothing references.
_save_handler: DesignSavedHandler | None = None


class FusionArchiveExporter:
    """ArchiveExporter over a design's ExportManager."""

    def __init__(self, design: adsk.fusion.Design) -> None:
        self.design = design

    def write_archive(self, path: Path) -> bool:
        manager = self.design.exportManager
        options = manager.createFusionArchiveExportOptions(str(path))
        if options is None:
            return False
        return manager.execute(options)


class DesignSavedHandler(adsk.core.DocumentEventHandler):
    """Exports each saved Fusion design."""

    def notify(self, args: adsk.core.DocumentEventArgs) -> None:
        try:
            export_saved(args.document)
        except Exception:
            logger.exception("documentSaved handler failed")


def export_saved(document: adsk.core.Document | None) -> None:
    if document is None:
        logger.debug("documentSaved without a document")
        return
    fusion_document = adsk.fusion.FusionDocument.cast(document)
    if fusion_document is None:
        logger.debug("Skipped %r: not a Fusion design", document.name)
        return
    data_file = document.dataFile
    if data_file is None:
        logger.warning("Skipped %r: no data file", document.name)
        return
    logger.info("Saved design %r (document name %r)", data_file.name, document.name)
    export_design(
        data_file.name,
        PROJECTS_ROOT,
        SubprocessGit.locate(),
        FusionArchiveExporter(fusion_document.design),
    )


def run(context):
    global _save_handler
    try:
        configure_logging(LOG_DIR)
    except Exception:
        logger.exception("Logging setup failed")
    try:
        event = adsk.core.Application.get().documentSaved
        if _save_handler is not None:
            event.remove(_save_handler)
        handler = DesignSavedHandler()
        event.add(handler)
        _save_handler = handler
        logger.info("Started; exporting saved designs under %s", PROJECTS_ROOT)
    except Exception:
        logger.exception("Start failed")


def stop(context):
    global _save_handler
    try:
        if _save_handler is not None:
            adsk.core.Application.get().documentSaved.remove(_save_handler)
            _save_handler = None
        logger.info("Stopped")
    except Exception:
        logger.exception("Stop failed")
