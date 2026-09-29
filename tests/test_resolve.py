from pathlib import Path

import pytest

from fusion_export.resolve import Target, resolve


def repo(root: Path, name: str, *, gitfile: bool = False) -> Path:
    d = root / name
    d.mkdir(parents=True)
    if gitfile:
        (d / ".git").write_text("gitdir: /elsewhere\n")
    else:
        (d / ".git").mkdir()
    return d


def target(root: Path, repo_name: str, *rel: str) -> Target:
    return Target(root / repo_name, root.joinpath(repo_name, *rel))


@pytest.fixture
def aqm(tmp_path: Path) -> Path:
    """Repo aqm with boards/fan_controller/ and boards/sensor/."""
    d = repo(tmp_path, "aqm")
    (d / "boards" / "fan_controller").mkdir(parents=True)
    (d / "boards" / "sensor").mkdir()
    return d


# Repo prefix


def test_simple(tmp_path):
    repo(tmp_path, "aqm")
    assert resolve("aqm-lid", tmp_path) == target(tmp_path, "aqm", "lid.f3d")


def test_longest_prefix_wins(tmp_path):
    repo(tmp_path, "aqm")
    repo(tmp_path, "aqm-sensor")
    assert resolve("aqm-sensor-lid", tmp_path) == target(tmp_path, "aqm-sensor", "lid.f3d")


def test_falls_back_to_shorter_prefix(tmp_path):
    repo(tmp_path, "aqm")
    assert resolve("aqm-sensor-lid", tmp_path) == target(tmp_path, "aqm", "sensor-lid.f3d")


def test_git_file_counts(tmp_path):
    repo(tmp_path, "aqm", gitfile=True)
    assert resolve("aqm-lid", tmp_path) == target(tmp_path, "aqm", "lid.f3d")


def test_dir_without_git_ignored(tmp_path):
    (tmp_path / "aqm-sensor").mkdir()
    repo(tmp_path, "aqm")
    assert resolve("aqm-sensor-lid", tmp_path) == target(tmp_path, "aqm", "sensor-lid.f3d")


def test_no_match(tmp_path):
    repo(tmp_path, "other")
    assert resolve("aqm-lid", tmp_path) is None


def test_prefix_splits_only_at_hyphen(tmp_path):
    repo(tmp_path, "aqm")
    assert resolve("aqmx-lid", tmp_path) is None


def test_case_sensitive(tmp_path):
    repo(tmp_path, "aqm")
    assert resolve("AQM-lid", tmp_path) is None


# Name exhausted: file named after the directory


def test_name_is_repo(tmp_path):
    repo(tmp_path, "aqm")
    assert resolve("aqm", tmp_path) == target(tmp_path, "aqm", "aqm.f3d")


def test_name_is_longer_repo(tmp_path):
    repo(tmp_path, "aqm")
    repo(tmp_path, "aqm-sensor")
    assert resolve("aqm-sensor", tmp_path) == target(tmp_path, "aqm-sensor", "aqm-sensor.f3d")


# Walk into subdirectories


def test_walks_to_deepest_dir(tmp_path, aqm):
    assert resolve("aqm-boards-fan_controller-enclosure", tmp_path) == target(
        tmp_path, "aqm", "boards", "fan_controller", "enclosure.f3d"
    )


def test_walk_exhausting_name_names_file_after_dir(tmp_path, aqm):
    assert resolve("aqm-boards-fan_controller", tmp_path) == target(
        tmp_path, "aqm", "boards", "fan_controller", "fan_controller.f3d"
    )


def test_no_dir_match_stays_in_repo(tmp_path, aqm):
    assert resolve("aqm-lid", tmp_path) == target(tmp_path, "aqm", "lid.f3d")


def test_stops_at_first_unmatched_level(tmp_path, aqm):
    assert resolve("aqm-boards-lid", tmp_path) == target(tmp_path, "aqm", "boards", "lid.f3d")


def test_remaining_segments_joined(tmp_path, aqm):
    assert resolve("aqm-boards-sensor-top-cover", tmp_path) == target(
        tmp_path, "aqm", "boards", "sensor", "top-cover.f3d"
    )


def test_hyphenated_dir_matched_as_run(tmp_path, aqm):
    (aqm / "boards" / "fan-controller").mkdir()
    assert resolve("aqm-boards-fan-controller-lid", tmp_path) == target(
        tmp_path, "aqm", "boards", "fan-controller", "lid.f3d"
    )
    assert resolve("aqm-boards-fan-controller", tmp_path) == target(
        tmp_path, "aqm", "boards", "fan-controller", "fan-controller.f3d"
    )


def test_longest_run_wins(tmp_path, aqm):
    (aqm / "fan").mkdir()
    (aqm / "fan-controller").mkdir()
    assert resolve("aqm-fan-controller-lid", tmp_path) == target(
        tmp_path, "aqm", "fan-controller", "lid.f3d"
    )
    assert resolve("aqm-fan-lid", tmp_path) == target(tmp_path, "aqm", "fan", "lid.f3d")


def test_walk_case_sensitive(tmp_path):
    d = repo(tmp_path, "aqm")
    (d / "Boards").mkdir()
    assert resolve("aqm-boards-lid", tmp_path) == target(tmp_path, "aqm", "boards-lid.f3d")


def test_dot_dirs_not_entered(tmp_path, aqm):
    (aqm / ".cache").mkdir()
    assert resolve("aqm-.git-lid", tmp_path) == target(tmp_path, "aqm", ".git-lid.f3d")
    assert resolve("aqm-.cache-lid", tmp_path) == target(tmp_path, "aqm", ".cache-lid.f3d")


def test_file_not_entered(tmp_path):
    d = repo(tmp_path, "aqm")
    (d / "notes").write_text("")
    assert resolve("aqm-notes-lid", tmp_path) == target(tmp_path, "aqm", "notes-lid.f3d")


def test_symlinked_dir_not_entered(tmp_path):
    d = repo(tmp_path, "aqm")
    outside = tmp_path / "outside"
    outside.mkdir()
    (d / "ext").symlink_to(outside, target_is_directory=True)
    assert resolve("aqm-ext-lid", tmp_path) == target(tmp_path, "aqm", "ext-lid.f3d")


# Rejected names


def test_trailing_hyphen_empty_part(tmp_path, aqm):
    assert resolve("aqm-", tmp_path) is None
    assert resolve("aqm-boards-", tmp_path) is None


def test_empty_part_no_fallback_to_shorter_prefix(tmp_path):
    repo(tmp_path, "aqm")
    repo(tmp_path, "aqm-sensor")
    assert resolve("aqm-sensor-", tmp_path) is None


def test_empty_name(tmp_path):
    assert resolve("", tmp_path) is None


def test_slash_in_part_rejected(tmp_path, aqm):
    assert resolve("aqm-a/b", tmp_path) is None
    assert resolve("aqm-../x", tmp_path) is None
    assert resolve("aqm-boards/sensor-lid", tmp_path) is None


def test_dot_parts_rejected(tmp_path, aqm):
    assert resolve("aqm-.", tmp_path) is None
    assert resolve("aqm-..", tmp_path) is None
    assert resolve("aqm-boards-..", tmp_path) is None


def test_slash_in_name_prefix_rejected(tmp_path):
    repo(tmp_path, "aqm")
    (tmp_path / "x").mkdir()
    assert resolve("../aqm-lid", tmp_path) is None
