import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from fusion_export.log import PACKAGE, configure_logging


def file_handlers(logger: logging.Logger) -> list[RotatingFileHandler]:
    return [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]


@pytest.fixture(autouse=True)
def restore_package_logger():
    logger = logging.getLogger(PACKAGE)
    handlers, level = list(logger.handlers), logger.level
    yield
    for h in logger.handlers:
        if h not in handlers:
            h.close()
    logger.handlers[:] = handlers
    logger.setLevel(level)


def log_file(log_dir: Path) -> Path:
    paths = list(log_dir.iterdir())
    assert len(paths) == 1
    return paths[0]


def test_package_is_fusion_export():
    assert PACKAGE == "fusion_export"


def test_creates_log_dir_and_file(tmp_path):
    log_dir = tmp_path / "Logs" / "fusion-export"
    logger = configure_logging(log_dir)
    assert logger.name == PACKAGE
    assert [h.baseFilename for h in file_handlers(logger)] == [str(log_dir / "fusion-export.log")]


def test_records_from_package_modules_reach_file(tmp_path):
    configure_logging(tmp_path)
    logging.getLogger(f"{PACKAGE}.export").info("exported aqm-lid")
    for h in file_handlers(logging.getLogger(PACKAGE)):
        h.flush()
    text = log_file(tmp_path).read_text()
    assert "exported aqm-lid" in text
    assert "INFO" in text


def test_idempotent_across_reloads(tmp_path):
    configure_logging(tmp_path)
    logger = configure_logging(tmp_path)
    assert len(file_handlers(logger)) == 1


def test_reconfigure_moves_to_new_dir(tmp_path):
    configure_logging(tmp_path / "a")
    logger = configure_logging(tmp_path / "b")
    assert [h.baseFilename for h in file_handlers(logger)] == [
        str(tmp_path / "b" / "fusion-export.log")
    ]


def test_leaves_other_handlers(tmp_path):
    logger = logging.getLogger(PACKAGE)
    other = logging.NullHandler()
    logger.addHandler(other)
    configure_logging(tmp_path)
    configure_logging(tmp_path)
    assert other in logger.handlers
