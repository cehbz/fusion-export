# fusion-export

A Fusion (macOS) add-in. Fusion's cloud is not the source of truth for a design, so on every document save this add-in exports the design's .f3d into the project's git repo, in the directory its name points to. It never commits or pushes.

## Install

```
./install.sh
```

This symlinks `FusionExport/` into Fusion's add-ins folder, so the repo is what Fusion runs. Restart Fusion; the add-in runs on startup.

## Naming

A design is named `<repo>-<path>` in Fusion. The repo is the longest hyphen-prefix of the name that is a git repo directly under `~/projects`; `aqm-sensor-lid` goes to the `aqm-sensor` repo if it exists, else to `aqm`.

The rest of the name walks down the repo's tree. At each level the longest run of leading segments that names an existing subdirectory is entered, so a directory called `fan-controller` takes two segments. The file goes in the deepest directory reached and is named after the segments left over, or after that directory when none are left. Matching is exact, even on a case-insensitive filesystem. Dot-directories and symlinks are not entered, and no directory is created.

With `aqm` holding `boards/fan_controller/`:

| Design | File |
|---|---|
| `aqm-boards-fan_controller-enclosure` | `aqm/boards/fan_controller/enclosure.f3d` |
| `aqm-boards-fan_controller` | `aqm/boards/fan_controller/fan_controller.f3d` |
| `aqm-boards-lid` | `aqm/boards/lid.f3d` |
| `aqm-lid` | `aqm/lid.f3d` |
| `aqm` | `aqm/aqm.f3d` |

A name that matches no repo, contains `/`, or leaves a file name of empty, `.` or `..` is skipped and logged with the reason.

## What a save produces

The `.f3d` at the resolved path, written atomically. If git does not already store that path in LFS (by `git check-attr filter`), the rule `*.f3d filter=lfs diff=lfs merge=lfs -text` is appended to the `.gitattributes` in the file's own directory, creating it. The pattern has no slash, so the rule also covers that directory's subdirectories. The native Git LFS `pre-push` hook is written to `.git/hooks` if missing. Without git-lfs installed the LFS wiring is skipped and the export still happens. STEP and STL are derived and not committed.

## Committing

The add-in never commits or pushes. Commit the `.f3d`, and the `.gitattributes` beside it when one was written, in the project repo yourself.

## Logs

`~/Library/Logs/fusion-export/fusion-export.log`

## Development

```
uv sync
uv run pytest
```
