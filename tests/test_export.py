import logging
import shutil
from pathlib import Path

import pytest

from fusion_export.export import Alert, Severity, export_design
from fusion_export.lfs import F3D_RULE, PRE_PUSH_HOOK

ARCHIVE = b"PK\x03\x04 new archive"
OLD = b"PK\x03\x04 old archive"


class FakeGit:
    def __init__(self) -> None:
        self.queries: list[tuple[Path, Path]] = []

    def lfs_available(self) -> bool:
        return True

    def common_dir(self, repo: Path) -> Path:
        return repo / ".git"

    def lfs_tracked(self, repo: Path, path: Path) -> bool:
        self.queries.append((repo, path))
        return False


class NoLfsGit(FakeGit):
    def lfs_available(self) -> bool:
        return False


class FailingGit(FakeGit):
    def common_dir(self, repo: Path) -> Path:
        raise OSError("git rev-parse failed")


class FakeExporter:
    """Writes `content` (unless None) to the path, then returns `result` or raises `error`."""

    def __init__(
        self,
        content: bytes | None = ARCHIVE,
        result: bool = True,
        error: Exception | None = None,
        linked: list[str] | None = None,
        link_error: Exception | None = None,
    ) -> None:
        self.linked = linked or []
        self.link_error = link_error
        self.content = content
        self.result = result
        self.error = error
        self.paths: list[Path] = []

    def linked_components(self) -> list[str]:
        if self.link_error is not None:
            raise self.link_error
        return self.linked

    def write_archive(self, path: Path) -> bool:
        self.paths.append(path)
        if self.content is not None:
            path.write_bytes(self.content)
        if self.error is not None:
            raise self.error
        return self.result


class RecordingAlerts:
    def __init__(self) -> None:
        self.sent: list[Alert] = []

    def send(self, alert: Alert) -> None:
        self.sent.append(alert)


class RaisingAlerts:
    def __init__(self) -> None:
        self.calls = 0

    def send(self, alert: Alert) -> None:
        self.calls += 1
        raise RuntimeError("notifier down")


@pytest.fixture
def alerts() -> RecordingAlerts:
    return RecordingAlerts()


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "aqm" / ".git" / "hooks").mkdir(parents=True)
    return tmp_path


NAME = "aqm-boards-fan_controller-enclosure"


@pytest.fixture
def directory(root: Path) -> Path:
    d = root / "aqm" / "boards" / "fan_controller"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def target(directory: Path) -> Path:
    return directory / "enclosure.f3d"


@pytest.fixture
def git() -> FakeGit:
    return FakeGit()


def listing(directory: Path) -> list[str]:
    return sorted(p.name for p in directory.iterdir()) if directory.is_dir() else []


def existing_target(target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(OLD)
    return target


def test_exports_to_target(root, target, git, alerts):
    result = export_design(NAME, root, git, FakeExporter(), alerts)
    assert result == target
    assert target.read_bytes() == ARCHIVE


def test_exports_into_repo_root_without_cad_dir(root, git, alerts):
    result = export_design("aqm-lid", root, git, FakeExporter(), alerts)
    assert result == root / "aqm" / "lid.f3d"
    assert (root / "aqm" / "lid.f3d").read_bytes() == ARCHIVE
    assert not (root / "aqm" / "cad").exists()
    assert (root / "aqm" / ".gitattributes").read_text() == F3D_RULE


def test_design_named_after_repo(root, git, alerts):
    result = export_design("aqm", root, git, FakeExporter(), alerts)
    assert result == root / "aqm" / "aqm.f3d"
    assert (root / "aqm" / "aqm.f3d").read_bytes() == ARCHIVE


def test_wires_lfs_in_resolved_repo(root, directory, target, git, alerts):
    export_design(NAME, root, git, FakeExporter(), alerts)
    assert git.queries == [(root / "aqm", target)]
    assert (directory / ".gitattributes").read_text() == F3D_RULE
    assert not (root / "aqm" / ".gitattributes").exists()
    assert (root / "aqm" / ".git" / "hooks" / "pre-push").read_text() == PRE_PUSH_HOOK


def test_exports_into_hidden_temp_dir_beside_target(root, directory, git, alerts):
    exporter = FakeExporter()
    export_design(NAME, root, git, exporter, alerts)
    assert len(exporter.paths) == 1
    path = exporter.paths[0]
    assert path.parent.parent == directory
    assert path.parent.name.startswith(".")
    assert path.suffix == ".f3d"


def test_removes_temp_dir_after_export(root, directory, git, alerts):
    export_design(NAME, root, git, FakeExporter(), alerts)
    assert listing(directory) == [".gitattributes", "enclosure.f3d"]


def test_replaces_existing_target(root, target, git, alerts):
    existing_target(target)
    export_design(NAME, root, git, FakeExporter(), alerts)
    assert target.read_bytes() == ARCHIVE


def test_failed_export_leaves_target(root, directory, target, git, caplog, alerts):
    existing_target(target)
    with caplog.at_level(logging.INFO, logger="fusion_export"):
        exporter = FakeExporter(content=b"partial", result=False)
        result = export_design(NAME, root, git, exporter, alerts)
    assert result is None
    assert target.read_bytes() == OLD
    assert listing(directory) == [".gitattributes", "enclosure.f3d"]
    assert any(r.levelno >= logging.ERROR and NAME in r.getMessage() for r in caplog.records)


def test_raising_export_leaves_target_and_is_logged(root, directory, target, git, caplog, alerts):
    existing_target(target)
    exporter = FakeExporter(content=b"partial", error=RuntimeError("export exploded"))
    with caplog.at_level(logging.INFO, logger="fusion_export"):
        result = export_design(NAME, root, git, exporter, alerts)
    assert result is None
    assert target.read_bytes() == OLD
    assert listing(directory) == [".gitattributes", "enclosure.f3d"]
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert errors and errors[0].exc_info is not None
    assert "export exploded" in caplog.text


def test_export_reporting_success_without_file_leaves_target(
    root, directory, target, git, caplog, alerts
):
    existing_target(target)
    with caplog.at_level(logging.INFO, logger="fusion_export"):
        result = export_design(NAME, root, git, FakeExporter(content=None), alerts)
    assert result is None
    assert target.read_bytes() == OLD
    assert listing(directory) == [".gitattributes", "enclosure.f3d"]
    assert any(r.levelno >= logging.ERROR for r in caplog.records)


def test_no_repo_skips_and_logs_name(root, git, caplog, alerts):
    exporter = FakeExporter()
    with caplog.at_level(logging.INFO, logger="fusion_export"):
        result = export_design("other-lid", root, git, exporter, alerts)
    assert result is None
    assert exporter.paths == []
    assert not (root / "aqm" / ".gitattributes").exists()
    assert listing(root / "aqm") == [".git"]
    records = [r for r in caplog.records if "other-lid" in r.getMessage()]
    assert len(records) == 1
    record = records[0]
    assert record.levelno == logging.INFO
    assert record.getMessage() == f"Export of 'other-lid' skipped: no repo under {root} matches"


def test_bad_file_name_skip_logs_its_own_reason(root, git, caplog, alerts):
    with caplog.at_level(logging.INFO, logger="fusion_export"):
        result = export_design("aqm-", root, git, FakeExporter(), alerts)
    assert result is None
    records = [r for r in caplog.records if "skipped" in r.getMessage()]
    assert len(records) == 1
    assert records[0].levelno == logging.INFO
    assert records[0].getMessage() == "Export of 'aqm-' skipped: the file name would be ''"
    assert "no repo" not in caplog.text


def test_lfs_failure_is_logged_not_raised(root, target, caplog, alerts):
    exporter = FakeExporter()
    with caplog.at_level(logging.INFO, logger="fusion_export"):
        result = export_design(NAME, root, FailingGit(), exporter, alerts)
    assert result is None
    assert exporter.paths == []
    assert not target.exists()
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert errors and errors[0].exc_info is not None


def test_logs_export(root, target, git, caplog, alerts):
    with caplog.at_level(logging.INFO, logger="fusion_export"):
        export_design(NAME, root, git, FakeExporter(), alerts)
    assert NAME in caplog.text
    assert str(target) in caplog.text


def test_removes_leftover_staging_dirs(root, directory, target, git, caplog, alerts):
    stale = directory / ".fusion-export-abc123"
    stale.mkdir(parents=True)
    (stale / "lid.f3d").write_bytes(b"partial")
    with caplog.at_level(logging.INFO, logger="fusion_export"):
        export_design(NAME, root, git, FakeExporter(), alerts)
    assert not stale.exists()
    assert listing(directory) == [".gitattributes", "enclosure.f3d"]
    assert ".fusion-export-abc123" in caplog.text


def test_leaves_unrelated_entries(root, directory, git, alerts):
    (directory / "notes").mkdir()
    (directory / "other.f3d").write_bytes(OLD)
    (directory / ".fusion-export-file").write_bytes(b"not a dir")
    (directory / ".fusion-export-old").mkdir()
    export_design(NAME, root, git, FakeExporter(), alerts)
    assert listing(directory) == [".fusion-export-file", ".gitattributes", "enclosure.f3d", "notes", "other.f3d"]


def test_skipped_export_touches_no_staging_dirs(root, git, alerts):
    stale = root / "other" / ".fusion-export-abc"
    stale.mkdir(parents=True)
    export_design("other-lid", root, git, FakeExporter(), alerts)
    assert stale.is_dir()


def test_staging_cleanup_failure_is_logged_and_export_continues(
    root, directory, target, git, monkeypatch, caplog, alerts
):
    stuck = directory / ".fusion-export-stuck"
    gone = directory / ".fusion-export-gone"
    stuck.mkdir(parents=True)
    gone.mkdir()
    real_rmtree = shutil.rmtree

    def rmtree(path, *args, **kwargs):
        if Path(path) == stuck:
            raise OSError("busy")
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr("fusion_export.export.shutil.rmtree", rmtree)
    with caplog.at_level(logging.INFO, logger="fusion_export"):
        result = export_design(NAME, root, git, FakeExporter(), alerts)
    assert result == target
    assert target.read_bytes() == ARCHIVE
    assert stuck.is_dir()
    assert not gone.exists()
    assert any(r.levelno >= logging.WARNING and "stuck" in r.getMessage() for r in caplog.records)


def test_linked_components_warn_once_naming_them_and_export_happens(
    root, target, git, caplog, alerts
):
    exporter = FakeExporter(linked=["PCB:1", "Lid:2"])
    with caplog.at_level(logging.INFO, logger="fusion_export"):
        result = export_design(NAME, root, git, exporter, alerts)
    assert result == target
    assert target.read_bytes() == ARCHIVE
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert NAME in warnings[0].getMessage()
    assert "not self-contained" in warnings[0].getMessage()
    assert "PCB:1, Lid:2" in warnings[0].getMessage()


def test_no_linked_components_no_warning(root, git, caplog, alerts):
    with caplog.at_level(logging.INFO, logger="fusion_export"):
        export_design(NAME, root, git, FakeExporter(), alerts)
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_listing_links_failure_is_logged_and_export_happens(root, target, git, caplog, alerts):
    exporter = FakeExporter(link_error=RuntimeError("no occurrences"))
    with caplog.at_level(logging.INFO, logger="fusion_export"):
        result = export_design(NAME, root, git, exporter, alerts)
    assert result == target
    assert target.read_bytes() == ARCHIVE
    records = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(records) == 1
    assert records[0].exc_info is not None
    assert "no occurrences" in caplog.text


def test_successful_export_sends_no_alert(root, git, alerts):
    export_design(NAME, root, git, FakeExporter(), alerts)
    assert alerts.sent == []


def test_skip_alerts_with_reason(root, git, alerts):
    export_design("other-lid", root, git, FakeExporter(), alerts)
    assert alerts.sent == [
        Alert(
            Severity.WARNING,
            "Fusion export skipped",
            f"Export of 'other-lid' skipped: no repo under {root} matches",
        )
    ]


def test_linked_components_alert_naming_them(root, git, alerts):
    export_design(NAME, root, git, FakeExporter(linked=["PCB:1", "Lid:2"]), alerts)
    assert alerts.sent == [
        Alert(
            Severity.WARNING,
            "Fusion export not self-contained",
            f"Export of {NAME!r} links other designs, so the .f3d is not self-contained: "
            "PCB:1, Lid:2",
        )
    ]


def test_listing_links_failure_alerts(root, git, alerts):
    export_design(NAME, root, git, FakeExporter(link_error=RuntimeError("no occurrences")), alerts)
    assert alerts.sent == [
        Alert(
            Severity.WARNING,
            "Fusion export: linked components unknown",
            f"Could not list linked components of {NAME!r}: RuntimeError: no occurrences",
        )
    ]


def test_missing_git_lfs_alerts_and_export_happens(root, target, alerts):
    result = export_design(NAME, root, NoLfsGit(), FakeExporter(), alerts)
    assert result == target
    assert target.read_bytes() == ARCHIVE
    assert alerts.sent == [
        Alert(
            Severity.WARNING,
            "Fusion export: git-lfs missing",
            f"Export of {NAME!r}: git-lfs not found, so {target} is not LFS-tracked "
            f"and no pre-push hook was installed in {root / 'aqm'}",
        )
    ]


def test_failed_write_alerts_with_target(root, target, git, alerts):
    export_design(NAME, root, git, FakeExporter(result=False), alerts)
    assert alerts.sent == [
        Alert(Severity.ERROR, "Fusion export failed", f"Export of {NAME!r} to {target} failed")
    ]


def test_missing_archive_alerts_with_target(root, target, git, alerts):
    export_design(NAME, root, git, FakeExporter(content=None), alerts)
    assert alerts.sent == [
        Alert(
            Severity.ERROR,
            "Fusion export failed",
            f"Export of {NAME!r} to {target} reported success but wrote no archive",
        )
    ]


def test_exception_alerts_with_error(root, git, alerts):
    export_design(NAME, root, git, FakeExporter(error=RuntimeError("export exploded")), alerts)
    assert alerts.sent == [
        Alert(
            Severity.ERROR,
            "Fusion export failed",
            f"Export of {NAME!r} failed: RuntimeError: export exploded",
        )
    ]


def test_raising_alerts_do_not_break_export(root, target, caplog):
    raising = RaisingAlerts()
    with caplog.at_level(logging.INFO, logger="fusion_export"):
        result = export_design(NAME, root, NoLfsGit(), FakeExporter(linked=["PCB:1"]), raising)
    assert result == target
    assert target.read_bytes() == ARCHIVE
    assert raising.calls == 2
    assert "notifier down" in caplog.text


def test_raising_alerts_on_failure_do_not_propagate(root, git, caplog):
    raising = RaisingAlerts()
    exporter = FakeExporter(error=RuntimeError("export exploded"))
    with caplog.at_level(logging.INFO, logger="fusion_export"):
        result = export_design(NAME, root, git, exporter, raising)
    assert result is None
    assert raising.calls == 1
    assert "notifier down" in caplog.text
