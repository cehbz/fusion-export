# TODO

- Verify in Fusion: `./install.sh`, restart Fusion, save a design named `aqm-fan-enclosure`. Expect `~/projects/aqm/cad/fan-enclosure.f3d`, the `cad/*.f3d` LFS rule in aqm's `.gitattributes`, an executable `.git/hooks/pre-push`, and log lines in `~/Library/Logs/fusion-export/fusion-export.log`. The log also answers:
  - whether `document.name` carries a version suffix (the add-in uses `dataFile.name`);
  - whether `ExportManager.execute` works inside the `documentSaved` handler, and whether Fusion keeps the `.f3d` filename as given;
  - whether the archive of a design with an inserted linked component (the PCB STEP) is self-contained, and its size against the GitHub Free LFS quota (10 GiB storage, 10 GiB bandwidth a month; every pushed version counts in full).
- Commit `cad/fan-enclosure.f3d` into aqm once aqm's own pending work (C6 section of its TODO.md, unpushed commits) is committed.
