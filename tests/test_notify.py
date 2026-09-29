import logging
import subprocess

import pytest

from fusion_export.export import Alert, Severity
from fusion_export.notify import Broadcast, MacNotification, run_command

ALERT = Alert(Severity.ERROR, "Fusion export failed", "Export of 'aqm-lid' failed: \"quoted\"")


class RecordingRunner:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.argvs: list[list[str]] = []

    def __call__(self, argv: list[str]) -> None:
        self.argvs.append(argv)
        if self.error is not None:
            raise self.error


class RecordingAlerts:
    def __init__(self) -> None:
        self.sent: list[Alert] = []

    def send(self, alert: Alert) -> None:
        self.sent.append(alert)


class RaisingAlerts:
    def send(self, alert: Alert) -> None:
        raise RuntimeError("channel down")


def test_notification_passes_text_as_argv():
    runner = RecordingRunner()
    MacNotification(runner).send(ALERT)
    assert runner.argvs == [
        [
            "/usr/bin/osascript",
            "-e",
            "on run argv",
            "-e",
            "display notification (item 1 of argv) with title (item 2 of argv)",
            "-e",
            "end run",
            ALERT.message,
            ALERT.title,
        ]
    ]


def test_failing_runner_is_logged_not_raised(caplog):
    runner = RecordingRunner(subprocess.TimeoutExpired(["osascript"], 5))
    with caplog.at_level(logging.INFO, logger="fusion_export"):
        MacNotification(runner).send(ALERT)
    records = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(records) == 1
    assert records[0].exc_info is not None
    assert ALERT.title in records[0].getMessage()


def test_run_command_raises_with_stderr_on_nonzero_exit():
    with pytest.raises(RuntimeError, match="exited 3: boom"):
        run_command(["/bin/sh", "-c", "echo boom >&2; exit 3"])


def test_run_command_succeeds_on_zero_exit():
    run_command(["/bin/sh", "-c", "exit 0"])


def test_broadcast_sends_to_every_channel_despite_failures(caplog):
    first, last = RecordingAlerts(), RecordingAlerts()
    with caplog.at_level(logging.INFO, logger="fusion_export"):
        Broadcast(first, RaisingAlerts(), last).send(ALERT)
    assert first.sent == [ALERT]
    assert last.sent == [ALERT]
    assert "channel down" in caplog.text
