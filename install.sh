#!/usr/bin/env bash
# Install the add-in loader, which runs fusion_export.addin from this repo, into Fusion's add-ins folder.
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
src="$repo_dir/addin"
addins="$HOME/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns"
dest="$addins/FusionExport"
placeholder="@REPO_DIR@"

for f in FusionExport.manifest FusionExport.py; do
  if [[ ! -f "$src/$f" ]]; then
    echo "error: $src/$f not found" >&2
    exit 1
  fi
done

# The loader holds the path in a Python string literal.
case "$repo_dir" in
  *'"'* | *'\'* | *$'\n'*)
    echo "error: repo path contains a quote, backslash or newline: $repo_dir" >&2
    exit 1
    ;;
esac

if [[ -L "$dest" ]]; then
  old_target="$(readlink "$dest")"
  rm "$dest"
  echo "removed old symlink: $dest -> $old_target"
fi

if [[ -d "$dest" ]]; then
  echo "updating: $dest"
else
  mkdir -p "$dest"
  echo "created: $dest"
fi

cp "$src/FusionExport.manifest" "$dest/FusionExport.manifest"
echo "wrote: FusionExport.manifest"

template="$(<"$src/FusionExport.py")"
printf '%s%s%s\n' "${template%%"$placeholder"*}" "$repo_dir" "${template#*"$placeholder"}" \
  >"$dest/FusionExport.py"
echo "wrote: FusionExport.py, loading fusion_export from $repo_dir"

echo "Restart Fusion to load the add-in, or start it from Utilities > Add-Ins > Scripts and Add-Ins."
