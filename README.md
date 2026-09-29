# fusion-export

A Fusion (macOS) add-in. Fusion's cloud is not the source of truth for a design, so on every document save this add-in exports the design's .f3d into the project's git repo at `cad/<part>.f3d`. It never commits or pushes.

## Install

```
./install.sh
```

This symlinks `FusionExport/` into Fusion's add-ins folder, so the repo is what Fusion runs. Restart Fusion; the add-in runs on startup.

## Naming

Designs are named `<repo>-<part>` in Fusion. The repo is the longest hyphen-prefix of the name that is a git repo directly under `~/projects`. `aqm-sensor-lid` goes to `~/projects/aqm-sensor/cad/lid.f3d` if that repo exists, else `~/projects/aqm/cad/sensor-lid.f3d`. A name with no matching repo, or with nothing after the repo prefix, is skipped and logged.

## What a save produces

`<repo>/cad/<part>.f3d`, written atomically. On the first export into a repo, `.gitattributes` gets an LFS rule for `cad/*.f3d` and, if missing, the native Git LFS `pre-push` hook is written to `.git/hooks`. Without git-lfs installed that wiring is skipped and the export still happens. STEP and STL are derived and not committed.

## Committing

The add-in never commits or pushes. Commit `cad/<part>.f3d` (and `.gitattributes` the first time) in the project repo yourself.

## Logs

`~/Library/Logs/fusion-export/fusion-export.log`

## Development

```
uv sync
uv run pytest
```
