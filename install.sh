#!/usr/bin/env bash
# Symlink this repo's FusionExport/ into Fusion's add-ins folder.
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
src="$repo_dir/FusionExport"
addins="$HOME/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns"
dest="$addins/FusionExport"

if [[ ! -d "$src" ]]; then
  echo "error: $src not found" >&2
  exit 1
fi

mkdir -p "$addins"

if [[ -L "$dest" ]]; then
  current="$(readlink "$dest")"
  if [[ "$current" == "$src" ]]; then
    echo "already linked: $dest -> $src"
  else
    ln -sfn "$src" "$dest"
    echo "replaced link (was -> $current): $dest -> $src"
  fi
elif [[ -e "$dest" ]]; then
  echo "error: $dest exists and is not a symlink; remove or move it and rerun" >&2
  exit 1
else
  ln -s "$src" "$dest"
  echo "linked: $dest -> $src"
fi

echo "Restart Fusion to load the add-in, or start it from Utilities > Add-Ins > Scripts and Add-Ins."
