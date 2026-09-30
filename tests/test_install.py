import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
INSTALL = REPO / "install.sh"
MANIFEST = REPO / "addin" / "FusionExport.manifest"
FAKE_ADSK = Path(__file__).resolve().parent / "fake_adsk"
ADDINS = Path("Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns")


def install(home: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["bash", str(INSTALL)],
        env={"HOME": str(home), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return result


def addin_dir(home: Path) -> Path:
    return home / ADDINS / "FusionExport"


def snapshot(directory: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(directory.iterdir()) if p.is_file()}


def test_fresh_install_creates_real_dir_with_manifest_and_loader(tmp_path):
    install(tmp_path)
    dest = addin_dir(tmp_path)
    assert dest.is_dir() and not dest.is_symlink()
    assert sorted(p.name for p in dest.iterdir()) == ["FusionExport.manifest", "FusionExport.py"]
    assert (dest / "FusionExport.manifest").read_bytes() == MANIFEST.read_bytes()


def test_loader_names_repo(tmp_path):
    install(tmp_path)
    loader = (addin_dir(tmp_path) / "FusionExport.py").read_text()
    assert f'REPO = "{REPO}"' in loader
    assert "@REPO_DIR@" not in loader


def test_rerun_is_idempotent(tmp_path):
    install(tmp_path)
    first = snapshot(addin_dir(tmp_path))
    install(tmp_path)
    assert snapshot(addin_dir(tmp_path)) == first


def test_replaces_symlink_with_real_dir(tmp_path):
    old = tmp_path / "old-addin"
    old.mkdir()
    (old / "FusionExport.py").write_text("old adapter\n")
    dest = addin_dir(tmp_path)
    dest.parent.mkdir(parents=True)
    dest.symlink_to(old)
    result = install(tmp_path)
    assert dest.is_dir() and not dest.is_symlink()
    assert sorted(p.name for p in dest.iterdir()) == ["FusionExport.manifest", "FusionExport.py"]
    assert (old / "FusionExport.py").read_text() == "old adapter\n"
    assert "symlink" in result.stdout


def test_replaces_dangling_symlink(tmp_path):
    dest = addin_dir(tmp_path)
    dest.parent.mkdir(parents=True)
    dest.symlink_to(tmp_path / "gone")
    install(tmp_path)
    assert dest.is_dir() and not dest.is_symlink()


def test_updates_real_dir_and_keeps_other_files(tmp_path):
    dest = addin_dir(tmp_path)
    dest.mkdir(parents=True)
    (dest / "FusionExport.py").write_text("stale loader\n")
    (dest / "notes.txt").write_text("keep me\n")
    install(tmp_path)
    assert (dest / "notes.txt").read_text() == "keep me\n"
    assert f'REPO = "{REPO}"' in (dest / "FusionExport.py").read_text()
    assert (dest / "FusionExport.manifest").read_bytes() == MANIFEST.read_bytes()


def _is_repo(entry: str) -> bool:
    return Path(entry or ".").resolve() == REPO


@pytest.fixture
def fusion_process(monkeypatch):
    """sys.path and sys.modules as Fusion has them: adsk importable, the repo not on sys.path.

    Both are restored afterwards, so other tests keep their fusion_export modules.
    """
    saved = dict(sys.modules)
    monkeypatch.setattr(sys, "path", [str(FAKE_ADSK)] + [p for p in sys.path if not _is_repo(p)])
    for name in list(sys.modules):
        if name == "fusion_export" or name.startswith("fusion_export."):
            del sys.modules[name]
    yield
    for name in list(sys.modules):
        if name not in saved:
            del sys.modules[name]
    sys.modules.update(saved)


def load_addin(addin: Path):
    """Import the add-in folder the way Fusion does: a package whose module is FusionExport.py."""
    spec = importlib.util.spec_from_file_location(
        "FusionExport", addin / "FusionExport.py", submodule_search_locations=[str(addin)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def addin_module():
    assert "fusion_export.addin" in sys.modules
    return sys.modules["fusion_export.addin"]


@pytest.fixture
def loader(tmp_path, fusion_process):
    install(tmp_path)
    return load_addin(addin_dir(tmp_path))


def test_loader_imports_addin_from_repo(loader):
    assert any(_is_repo(p) for p in sys.path)
    assert Path(addin_module().__file__).parent == REPO / "fusion_export"


def test_addin_logger_is_under_package(loader):
    assert addin_module().logger.name == "fusion_export.addin"


@pytest.mark.parametrize("entry", ["run", "stop"])
def test_loader_delegates_to_addin(loader, monkeypatch, entry):
    calls = []
    monkeypatch.setattr(addin_module(), entry, calls.append)
    context = object()
    getattr(loader, entry)(context)
    assert calls == [context]
