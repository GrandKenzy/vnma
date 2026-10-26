# VNMA `0.3.0`

**Release date:** 2026-10-24

> **Beta** — Resolver backtracking, recoverable transactions, and safer file operations

This release strengthens the dependency resolver, adds recoverable
transactions for installs and updates, fixes dangerous file operations, and
formalizes the importable identity of Python packages.

**Publication status:** published on PyPI
([`0.3.0`](https://pypi.org/project/vnma/0.3.0/)) and merged into `main`.
This release remains **Beta**.

## Added

### Resolver backtracking and installation transactions

- Replaced the queue-only dependency resolver with deterministic, bounded
  backtracking that **recomputes its complete constraint graph** from the
  current version choices. Rejected package versions no longer leave transitive
  constraints or dependencies in the final result.
- Regression coverage for conflicting diamonds, shared dependency constraints,
  parent-version rollback, orphan elimination, and cycles.
- `WorkspaceTransaction`: changes are staged in a private vendor tree, multiple
  wheels are committed together, and a failed install or update can restore the
  previous vendor, configuration, lockfile, and generated workspace settings.
- Exclusive transaction lock and recovery journal to handle interrupted commits
  and prevent parallel workspace mutations. Windows uses recoverable directory
  renames, **not a single atomic two-directory swap**.
- Grouped transactions applied to `install`, `update`, `link`, `unlink`,
  `reload`, `prune`, and targeted package removal. Direct
  `WheelInstaller.install` calls are transactional as well.
- Generated command wrappers derive vendor paths from their own executable
  location, so moving staged directories into place does not leave broken paths.
- `[package].package` is now the **Python import name** (for example `my_lib`),
  independent of the distribution identifier `[package].name` (which may contain
  versions, dashes, or other normalized separators). The legacy `packname`
  alias remains accepted; installed records and `vnma list` expose the
  importable name separately.
- Editable package links prefer the import name and keep dependency keys such
  as `my_lib = { path = "...", editable = true }` intact. Relative paths in
  `vnma.toml` now resolve relative to the manifest, not the caller's current
  working directory.
- Documented real-world `vnma_config.toml` and `vnma.toml` manifests as
  compatibility references.

## Fixed

- **Safe workspace cleanup:** `WorkspaceCleaner` no longer removes every
  directory named `vendor/` or `vendor_vnma/`. It preserves directories without
  VNMA's `.vnma_meta/` marker and skips symbolic links and resolved paths
  outside the project root. This prevents a case where VNMA used `vendor_vnma/`
  but its purge also deleted another tool's unrelated `vendor/` directory.
- **`link` and `reload` dependency resolution:** both commands now construct
  `WheelResolver` with a usable default client instead of passing `WheelCache`
  and `LocalWheelIndex` positionally. Regression tests exercise the resolution
  branches.
- **Optional dependencies during pruning:** `OrphanPruner` flattens extras from
  root requirements into a set of strings instead of mixing tuples with strings.
  A new test verifies that dependencies activated by multiple requested extras
  remain reachable.
- **PEP 508 extras evaluation:** `WheelResolver._evaluate_marker` evaluates
  requirements against each selected extra rather than only the first one.
- **Wheel path preflight:** `WheelArchive` validates every extraction path
  before writing files, rejects duplicate destinations, and blocks entries that
  would map into VNMA's internal metadata or overwrite the runtime's root
  `__bootstrap__.py` / `__init__.py`. Tests cover disguised `.data/purelib`
  paths and late malicious entries.
- **Uninstall bootstrap preservation:** removing one wheel regenerates the
  bootstrap through the same aggregation path used by the installer, preserving
  remaining packages' module exports, hermetic settings, and editable-link
  paths.
- **Windows test portability:** `test_vendor_dir_configuration_precedence`
  resolves both paths before comparing them, avoiding short-name vs long-name
  temporary-directory aliases.

## Changed

- Version updated to `0.3.0` in `pyproject.toml`, `vnma.__version__`,
  `vnma.toml`, the PyPI client and cache user agents, and the main beta
  documentation.
- GitHub Actions matrix for Python **3.11** and **3.13** on Windows and Linux,
  plus a separate smoke test for the previously published PyPI distribution.
- Independent wheel-build-and-install smoke test for the `0.3.0` source branch,
  checking that installed distribution metadata matches `vnma.__version__`.

## Verification

- **117 unit tests passed in each of four matrix environments:** Windows and
  Linux, Python 3.11 and 3.13.
- **7/7 jobs successful** in
  [GitHub Actions run 40123819610](https://github.com/GrandKenzy/vnma/actions/runs/40123819610),
  including a live integration job that used real repository manifests and an
  executable import test.
- The branch built `vnma-0.3.0-py3-none-any.whl`, installed it outside the
  checkout directory, and verified its version and CLI.
- The independent `pip install vnma` smoke test checks the **published**
  distribution, not the unpublished `0.3.0` branch.
- These are automated tests and static verification; no claim is made of
  exhaustive end-to-end coverage across platforms and real package graphs.

## Known issues

- The resolver has bounded backtracking; large pathological graphs can exhaust
  its decision limit.
- Transaction staging copies the vendor tree, requiring additional temporary
  disk space. `uninstall --all` remains an explicit destructive purge, not a
  reversible transaction.
- Crash recovery uses a durable journal and directory renames. It does not
  promise uninterrupted visibility of the live vendor during Windows directory
  swaps, nor power-loss durability on every filesystem.
- `LockfileHandler.is_vendor_synchronized()` checks manifest records, not the
  presence and content hash of every installed file.
- Git fallback checkout commands may fail without surfacing the failure,
  potentially installing a different ref from the one requested.
- Transactional mutations reject vendor paths outside the project, but
  non-transactional commands such as `vnma init` still need a uniform
  workspace path-validation policy.
- End-to-end native-binary installation across all OS/Python combinations and
  Python 3.14 are not covered by this CI matrix.

## Earlier releases

`0.2.9` is the last version published before the `0.3.0` development work.
Historical changes prior to `0.3.0` were not reconstructed.
