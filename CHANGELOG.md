# Changelog

All notable changes to VNMA are documented here. This project follows the
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format.

## [0.3.0] — In development (2026-10-24)

**Status:** Changes are committed on the `actualizar-vnma` branch. This entry
does **not** indicate a PyPI release or a merge into `main`.
The last PyPI version verified by the smoke test was `0.2.9`.

### Fixed

- **Safe workspace cleanup:** `WorkspaceCleaner` no longer blindly removes
  all directories named `vendor/` and `vendor_vnma/`. It preserves directories
  without VNMA's `.vnma_meta/` marker, and skips symbolic links and resolved
  paths outside the project root. This prevents the previously identified case
  where VNMA used `vendor_vnma/` but its purge also deleted another tool's
  unrelated `vendor/` directory.
- **`link` and `reload` dependency resolution:** Both commands now
  construct `WheelResolver` with a usable default client rather than
  incorrectly passing `WheelCache` and `LocalWheelIndex` as positional
  arguments. Regression tests exercise the dependency resolution branches.
- **Optional dependencies during pruning:** `OrphanPruner` flattens
  extras from root requirements into a set of strings instead of mixing tuples
  with strings. A new test verifies that dependencies activated by multiple
  requested extras remain reachable.
- **PEP 508 extras evaluation:** `WheelResolver._evaluate_marker`
  evaluates requirements against each selected extra rather than only
  the first one. Added a regression test for dependencies activated by the
  second extra.
- **Wheel path preflight:** `WheelArchive` validates all extracted
  destination paths before writing files, rejects duplicate destinations,
  and blocks entries that would map into VNMA's internal metadata or
  overwrite the runtime's root `__bootstrap__.py`/`__init__.py`.
  Tests cover disguised `.data/purelib` paths and late malicious entries.
- **Uninstall bootstrap preservation:** Removing one wheel now regenerates
  the bootstrap through the same aggregation path used by the installer,
  preserving remaining packages' module exports, hermetic settings, and
  editable-link paths.
- **Windows test portability:** `test_vendor_dir_configuration_precedence`
  resolves both paths before comparing them, avoiding short-name vs
  long-name Windows temporary-directory aliases.

### Changed

- Version updated to **0.3.0** in `pyproject.toml`, `vnma.__version__`,
  `vnma.toml`, the PyPI client/cache user agents, and the main beta
  documentation.
- Added a GitHub Actions matrix for Python **3.11** and **3.13** on both
  Windows and Linux, plus a separate smoke test for the previously published
  PyPI distribution.
- Added an independent wheel-build-and-install smoke test for the **0.3.0
  source branch** and checks that installed distribution metadata matches
  `vnma.__version__`.

### Verification evidence

- **103 unit tests passed in each of four matrix environments**:
  Windows/Python 3.11, Windows/Python 3.13, Linux/Python 3.11,
  Linux/Python 3.13.
- **6/6 jobs successful** in
  [GitHub Actions run 40121475119](https://github.com/GrandKenzy/vnma/actions/runs/40121475119).
- The branch built `vnma-0.3.0-py3-none-any.whl`, installed that built
  wheel outside the checkout directory, and verified its version and CLI.
- The independent `pip install vnma` smoke test checks the **published**
  distribution, not the unpublished 0.3.0 branch.
- These are automated tests and static verification; no claim is made of
  exhaustive end-to-end coverage across platforms and real package graphs.

### Known issues / not yet resolved

- The graph resolver still accumulates constraints from replaced dependency
  versions. More complex version backtracking can produce false conflicts.
- ZIP path **preflight** prevents partial extraction for rejected archive
  members, but extraction and manifest updates are **not yet transactional**.
  An I/O failure mid-extraction may still leave files behind.
- `LockfileHandler.is_vendor_synchronized()` checks manifest records, not
  the presence and content hash of every installed file.
- Git fallback checkout commands may fail without surfacing the failure,
  potentially installing a different ref from the one requested.
- The cleanup guard protects *deletion*, but configured `vendor_dir` paths
  should also be validated when initializing/installing to prevent writes
  outside the workspace.
- End-to-end native-binary installation across all OS/Python combinations
  and Python 3.14 are not covered by this CI matrix.

## 0.2.9 — Previous published baseline

This is the version that was published before the 0.3.0 development work.
Historical changes prior to this branch were not reconstructed for this file.
