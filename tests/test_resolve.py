from pathlib import Path

from fusion_export.resolve import resolve


def repo(root: Path, name: str, *, gitfile: bool = False) -> None:
    d = root / name
    d.mkdir(parents=True)
    if gitfile:
        (d / ".git").write_text("gitdir: /elsewhere\n")
    else:
        (d / ".git").mkdir()


def test_simple(tmp_path):
    repo(tmp_path, "aqm")
    assert resolve("aqm-lid", tmp_path) == tmp_path / "aqm" / "cad" / "lid.f3d"


def test_longest_prefix_wins(tmp_path):
    repo(tmp_path, "aqm")
    repo(tmp_path, "aqm-sensor")
    assert resolve("aqm-sensor-lid", tmp_path) == tmp_path / "aqm-sensor" / "cad" / "lid.f3d"


def test_falls_back_to_shorter_prefix(tmp_path):
    repo(tmp_path, "aqm")
    assert resolve("aqm-sensor-lid", tmp_path) == tmp_path / "aqm" / "cad" / "sensor-lid.f3d"


def test_git_file_counts(tmp_path):
    repo(tmp_path, "aqm", gitfile=True)
    assert resolve("aqm-lid", tmp_path) == tmp_path / "aqm" / "cad" / "lid.f3d"


def test_dir_without_git_ignored(tmp_path):
    (tmp_path / "aqm-sensor").mkdir()
    repo(tmp_path, "aqm")
    assert resolve("aqm-sensor-lid", tmp_path) == tmp_path / "aqm" / "cad" / "sensor-lid.f3d"


def test_no_match(tmp_path):
    repo(tmp_path, "other")
    assert resolve("aqm-lid", tmp_path) is None


def test_prefix_splits_only_at_hyphen(tmp_path):
    repo(tmp_path, "aqm")
    assert resolve("aqmx-lid", tmp_path) is None


def test_no_hyphen_whole_name_is_repo(tmp_path):
    repo(tmp_path, "aqm")
    assert resolve("aqm", tmp_path) is None


def test_trailing_hyphen_empty_part(tmp_path):
    repo(tmp_path, "aqm")
    assert resolve("aqm-", tmp_path) is None


def test_empty_part_no_fallback_to_shorter_prefix(tmp_path):
    repo(tmp_path, "aqm")
    repo(tmp_path, "aqm-sensor")
    assert resolve("aqm-sensor-", tmp_path) is None


def test_whole_name_is_repo_no_fallback(tmp_path):
    repo(tmp_path, "aqm")
    repo(tmp_path, "aqm-sensor")
    assert resolve("aqm-sensor", tmp_path) is None


def test_empty_name(tmp_path):
    assert resolve("", tmp_path) is None


def test_case_sensitive(tmp_path):
    repo(tmp_path, "aqm")
    assert resolve("AQM-lid", tmp_path) is None


def test_slash_in_part_rejected(tmp_path):
    repo(tmp_path, "aqm")
    assert resolve("aqm-a/b", tmp_path) is None
    assert resolve("aqm-../x", tmp_path) is None


def test_dot_parts_rejected(tmp_path):
    repo(tmp_path, "aqm")
    assert resolve("aqm-.", tmp_path) is None
    assert resolve("aqm-..", tmp_path) is None


def test_slash_in_name_prefix_rejected(tmp_path):
    repo(tmp_path, "aqm")
    (tmp_path / "x").mkdir()
    assert resolve("../aqm-lid", tmp_path) is None
