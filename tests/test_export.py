import logging
import shutil
from pathlib import Path

import pytest

from fusion_export.export import export_design
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
    ) -> None:
        self.content = content
        self.result = result
        self.error = error
        self.paths: list[Path] = []

    def write_archive(self, path: Path) -> bool:
        self.paths.append(path)
        if self.content is not None:
            path.write_bytes(self.content)
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "aqm" / ".git" / "hooks").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def cad(root: Path) -> Path:
    return root / "aqm" / "cad"


@pytest.fixture
def target(cad: Path) -> Path:
    return cad / "lid.f3d"


@pytest.fixture
def git() -> FakeGit:
    return FakeGit()


def listing(directory: Path) -> list[str]:
    return sorted(p.name for p in directory.iterdir()) if directory.is_dir() else []


def existing_target(target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(OLD)
    return target


def test_exports_to_target(root, target, git):
    result = export_design("aqm-lid", root, git, FakeExporter())
    assert result == target
    assert target.read_bytes() == ARCHIVE


def test_creates_cad_dir(root, cad, git):
    assert not cad.exists()
    export_design("aqm-lid", root, git, FakeExporter())
    assert cad.is_dir()


def test_wires_lfs_in_resolved_repo(root, cad, target, git):
    export_design("aqm-lid", root, git, FakeExporter())
    assert git.queries == [(root / "aqm", target)]
    assert (cad / ".gitattributes").read_text() == F3D_RULE
    assert not (root / "aqm" / ".gitattributes").exists()
    assert (root / "aqm" / ".git" / "hooks" / "pre-push").read_text() == PRE_PUSH_HOOK


def test_exports_into_hidden_temp_dir_beside_target(root, cad, git):
    exporter = FakeExporter()
    export_design("aqm-lid", root, git, exporter)
    assert len(exporter.paths) == 1
    path = exporter.paths[0]
    assert path.parent.parent == cad
    assert path.parent.name.startswith(".")
    assert path.suffix == ".f3d"


def test_removes_temp_dir_after_export(root, cad, git):
    export_design("aqm-lid", root, git, FakeExporter())
    assert listing(cad) == [".gitattributes", "lid.f3d"]


def test_replaces_existing_target(root, target, git):
    existing_target(target)
    export_design("aqm-lid", root, git, FakeExporter())
    assert target.read_bytes() == ARCHIVE


def test_failed_export_leaves_target(root, cad, target, git, caplog):
    existing_target(target)
    with caplog.at_level(logging.INFO, logger="fusion_export"):
        result = export_design("aqm-lid", root, git, FakeExporter(content=b"partial", result=False))
    assert result is None
    assert target.read_bytes() == OLD
    assert listing(cad) == [".gitattributes", "lid.f3d"]
    assert any(r.levelno >= logging.ERROR and "aqm-lid" in r.getMessage() for r in caplog.records)


def test_raising_export_leaves_target_and_is_logged(root, cad, target, git, caplog):
    existing_target(target)
    exporter = FakeExporter(content=b"partial", error=RuntimeError("export exploded"))
    with caplog.at_level(logging.INFO, logger="fusion_export"):
        result = export_design("aqm-lid", root, git, exporter)
    assert result is None
    assert target.read_bytes() == OLD
    assert listing(cad) == [".gitattributes", "lid.f3d"]
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert errors and errors[0].exc_info is not None
    assert "export exploded" in caplog.text


def test_export_reporting_success_without_file_leaves_target(root, cad, target, git, caplog):
    existing_target(target)
    with caplog.at_level(logging.INFO, logger="fusion_export"):
        result = export_design("aqm-lid", root, git, FakeExporter(content=None))
    assert result is None
    assert target.read_bytes() == OLD
    assert listing(cad) == [".gitattributes", "lid.f3d"]
    assert any(r.levelno >= logging.ERROR for r in caplog.records)


def test_no_repo_skips_and_logs_name(root, git, caplog):
    exporter = FakeExporter()
    with caplog.at_level(logging.INFO, logger="fusion_export"):
        result = export_design("other-lid", root, git, exporter)
    assert result is None
    assert exporter.paths == []
    assert not (root / "aqm" / ".gitattributes").exists()
    assert not (root / "aqm" / "cad").exists()
    records = [r for r in caplog.records if "other-lid" in r.getMessage()]
    assert len(records) == 1
    record = records[0]
    assert record.levelno == logging.INFO
    assert "skip" in record.getMessage()


def test_lfs_failure_is_logged_not_raised(root, target, caplog):
    exporter = FakeExporter()
    with caplog.at_level(logging.INFO, logger="fusion_export"):
        result = export_design("aqm-lid", root, FailingGit(), exporter)
    assert result is None
    assert exporter.paths == []
    assert not target.exists()
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert errors and errors[0].exc_info is not None


def test_logs_export(root, target, git, caplog):
    with caplog.at_level(logging.INFO, logger="fusion_export"):
        export_design("aqm-lid", root, git, FakeExporter())
    assert "aqm-lid" in caplog.text
    assert str(target) in caplog.text


def test_removes_leftover_staging_dirs(root, cad, target, git, caplog):
    stale = cad / ".fusion-export-abc123"
    stale.mkdir(parents=True)
    (stale / "lid.f3d").write_bytes(b"partial")
    with caplog.at_level(logging.INFO, logger="fusion_export"):
        export_design("aqm-lid", root, git, FakeExporter())
    assert not stale.exists()
    assert listing(cad) == [".gitattributes", "lid.f3d"]
    assert ".fusion-export-abc123" in caplog.text


def test_leaves_unrelated_cad_entries(root, cad, git):
    cad.mkdir(parents=True)
    (cad / "notes").mkdir()
    (cad / "other.f3d").write_bytes(OLD)
    (cad / ".fusion-export-file").write_bytes(b"not a dir")
    (cad / ".fusion-export-old").mkdir()
    export_design("aqm-lid", root, git, FakeExporter())
    assert listing(cad) == [".fusion-export-file", ".gitattributes", "lid.f3d", "notes", "other.f3d"]


def test_skipped_export_touches_no_staging_dirs(root, git):
    stale = root / "other" / "cad" / ".fusion-export-abc"
    stale.mkdir(parents=True)
    export_design("other-lid", root, git, FakeExporter())
    assert stale.is_dir()


def test_staging_cleanup_failure_is_logged_and_export_continues(
    root, cad, target, git, monkeypatch, caplog
):
    stuck = cad / ".fusion-export-stuck"
    gone = cad / ".fusion-export-gone"
    stuck.mkdir(parents=True)
    gone.mkdir()
    real_rmtree = shutil.rmtree

    def rmtree(path, *args, **kwargs):
        if Path(path) == stuck:
            raise OSError("busy")
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr("fusion_export.export.shutil.rmtree", rmtree)
    with caplog.at_level(logging.INFO, logger="fusion_export"):
        result = export_design("aqm-lid", root, git, FakeExporter())
    assert result == target
    assert target.read_bytes() == ARCHIVE
    assert stuck.is_dir()
    assert not gone.exists()
    assert any(r.levelno >= logging.WARNING and "stuck" in r.getMessage() for r in caplog.records)
