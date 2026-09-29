# TODO

- Verify in Fusion: `./install.sh`, restart Fusion, save a design named `aqm-boards-fan_controller`. Expect `~/projects/aqm/boards/fan_controller/fan_controller.f3d`, the `*.f3d` LFS rule in `aqm/boards/fan_controller/.gitattributes`, an executable `.git/hooks/pre-push`, and log lines in `~/Library/Logs/fusion-export/fusion-export.log`. The log also answers:
  - whether `document.name` carries a version suffix (the add-in uses `dataFile.name`);
  - whether `ExportManager.execute` works inside the `documentSaved` handler, and whether Fusion keeps the `.f3d` filename as given;
  - whether the archive of a design with an inserted linked component (the PCB STEP) is self-contained, and its size against the GitHub Free LFS quota (10 GiB storage, 10 GiB bandwidth a month; every pushed version counts in full).
- Commit `boards/fan_controller/fan_controller.f3d` and its `.gitattributes` into aqm after the check.
