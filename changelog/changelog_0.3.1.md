# VNMA `0.3.1`

**Release date:** 2026-10-24

> **Beta** — Test runner, configuration safety, and visual identity

This release fixes the accidental removal of the project configuration file
during uninstall, adds the `vnma test` command for automatic test discovery
inside the vendored environment, and introduces the project's visual identity.

**Publication status:** published on PyPI
([`0.3.1`](https://pypi.org/project/vnma/0.3.1/)) and merged into `main`.

## Added

- **`vnma test` command:** discovers test directories (`tests/`, `test/`,
  `testing/`) and runs `pytest` inside the vendored environment. It falls back
  to the standard library's `unittest discover` when `pytest` is not installed.
- **`--purge-config` flag:** explicitly removes `vnma.toml` during a full
  `vnma uninstall`, only when the user requests it.
- **Visual identity:** official banner and logo in SVG and HD raster formats
  (`assets/banner.*`, `assets/logo.*`) and a refreshed `README.md`.

## Fixed

- **`vnma.toml` preservation:** `vnma uninstall` (and `vnma uninstall -y`) now
  keeps `vnma.toml` by default (`keep_config=True`). The `vendor/` directory and
  the lockfile are cleaned without destroying the project's dependency
  definition.
