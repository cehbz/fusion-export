"""Adapters for the export.Alerts port."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Callable

from .export import Alert, Alerts

logger = logging.getLogger(__name__)

OSASCRIPT = Path("/usr/bin/osascript")
NOTIFICATION_SCRIPT = (
    "on run argv",
    "display notification (item 1 of argv) with title (item 2 of argv)",
    "end run",
)
TIMEOUT = 5.0

Runner = Callable[[list[str]], None]


def run_command(argv: list[str]) -> None:
    """Run argv to completion within TIMEOUT; raises on failure, with its stderr."""
    result = subprocess.run(argv, capture_output=True, text=True, timeout=TIMEOUT)
    if result.returncode != 0:
        raise RuntimeError(f"{argv[0]} exited {result.returncode}: {result.stderr.strip()}")


class MacNotification:
    """Alerts as macOS notifications, posted by osascript with the text passed as arguments."""

    def __init__(self, runner: Runner = run_command) -> None:
        self.runner = runner

    def send(self, alert: Alert) -> None:
        """Post alert; a failure is logged, not raised."""
        argv = [str(OSASCRIPT)]
        for line in NOTIFICATION_SCRIPT:
            argv += ["-e", line]
        argv += [alert.message, alert.title]
        try:
            self.runner(argv)
        except Exception:
            logger.warning("Could not post notification %r", alert.title, exc_info=True)


class Broadcast:
    """Alerts sent to each channel in order; a failing channel is logged and the rest still run."""

    def __init__(self, *channels: Alerts) -> None:
        self.channels = channels

    def send(self, alert: Alert) -> None:
        for channel in self.channels:
            try:
                channel.send(alert)
            except Exception:
                logger.warning(
                    "Alert %r failed on %s", alert.title, type(channel).__name__, exc_info=True
                )
