"""Fusion add-in loader: runs fusion_export.addin from the repo install.sh rendered in."""

import sys

REPO = "@REPO_DIR@"

if REPO not in sys.path:
    sys.path.insert(0, REPO)

from fusion_export import addin  # noqa: E402


def run(context):
    addin.run(context)


def stop(context):
    addin.stop(context)
