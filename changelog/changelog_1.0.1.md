# VNMA `1.0.1`

**Release date:** 2026-11-01

> **Patch** — Internal test folder resolution priority and non-package discovery fix

This patch release fixes test suite discovery when targeting internal folders inside `tests/` or `test/`.

## Fixed

- **Internal test folder resolution priority:** `vnma test <folder>` now strictly prioritizes subfolders and suites inside `tests/` (e.g. `tests/unit`) over same-named directories in the project root. Users no longer need to relocate test suites outside of `tests/`.
- **Non-package test directory discovery:** Fixed `unittest discover` failing with `ImportError: Start directory is not importable` when test subdirectories do not contain an `__init__.py` file.

## Verification

- Added regression tests in `tests/test_cli.py` covering priority over root directories and non-package subdirectory execution.
- 100% passing automated test suite across all modules.
