# Changelog

All notable changes to VNMA are documented here. This project follows the
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format.

## [0.3.0] — 2026-10-24

### Resumen de la versión

Esta versión fortalece el resolvedor de dependencias, añade transacciones
recuperables para instalaciones y actualizaciones, corrige operaciones peligrosas
sobre archivos y formaliza la identidad importable de los paquetes Python.

**Estado de publicación:** código integrado en `main` mediante el
[PR #1](https://github.com/GrandKenzy/vnma/pull/1). La versión **0.3.0**
aún no se ha publicado en PyPI: el
[workflow de publicación](https://github.com/GrandKenzy/vnma/actions/runs/40124410800)
compiló correctamente la distribución y superó las pruebas, pero PyPI
respondió `invalid-publisher` al no encontrar un Trusted Publisher que
corresponda al repositorio, workflow `publish.yml` y entorno `pypi`.
La publicación debe verificarse en PyPI después de configurar la confianza
y reejecutar el job fallido.

Esta versión mantiene el estado **Beta**.

### Added — Resolver backtracking and installation transactions

- Replaced the previous queue-only dependency resolver with deterministic,
  bounded backtracking that **recomputes its complete constraint graph** from
  the current version choices. Rejected package versions no longer leave
  transitive constraints or dependencies in the final result.
- Added regression coverage for conflicting diamonds, shared dependency
  constraints, parent-version rollback, orphan elimination, and cycles.
- Introduced `WorkspaceTransaction`: changes are staged in a private
  vendor tree, multiple wheels are committed together, and a failed
  installation/update can restore the previous vendor, configuration,
  lockfile, and generated workspace settings.
- Added an exclusive transaction lock and recovery journal to handle
  interrupted commits and prevent parallel workspace mutations.
  Windows uses recoverable directory renames, **not a single atomic
  two-directory swap**.
- Applied grouped transactions to CLI `install`, `update`, `link`,
  `unlink`, `reload`, `prune` and targeted package removal.
  Direct `WheelInstaller.install` calls are transactional as well.
- Generated command wrappers now derive vendor paths from their own
  executable location, so moving staged directories into place does not
  leave broken paths.
- Formalized `[package].package` as the **Python import name** (for
  example `gram`) independently of the distribution identifier
  `[package].name` (which may contain versions, dashes or other
  normalized separators). The legacy `packname` alias used by
  Gram remains accepted; installed records and `vnma list` expose
  the importable name separately.
- Editable package links prefer the import name and keep EasyC-style
  `gram = { path = "...", editable = true }` dependency keys intact.
  Relative paths in `vnma.toml` now resolve relative to the manifest,
  not the caller's current working directory.
- Documented Gram's current `vnma_config.toml` and EasyC's
  `vnma.toml.example` as real compatibility references.

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

- **117 unit tests passed in each of four matrix environments**:
  Windows/Python 3.11, Windows/Python 3.13, Linux/Python 3.11,
  Linux/Python 3.13.
- **7/7 jobs successful** in
  [GitHub Actions run 40123819610](https://github.com/GrandKenzy/vnma/actions/runs/40123819610),
  including a live Gram/EasyC integration job using their actual repository
  manifests and an executable import test.
- The branch built `vnma-0.3.0-py3-none-any.whl`, installed that built
  wheel outside the checkout directory, and verified its version and CLI.
- The independent `pip install vnma` smoke test checks the **published**
  distribution, not the unpublished 0.3.0 branch.
- These are automated tests and static verification; no claim is made of
  exhaustive end-to-end coverage across platforms and real package graphs.

### Known issues / not yet resolved

- The resolver has bounded backtracking; large pathological graphs can
  exhaust its decision limit. Performance tuning for unusually complex
  dependency graphs is future work.
- Transaction staging copies the vendor tree, requiring additional temporary
  disk space. Whole-workspace `uninstall --all` is still an explicit
  destructive purge, not a reversible vendor transaction.
- Crash recovery uses a durable journal and directory renames. It does not
  promise uninterrupted visibility of the live vendor during Windows
  directory swaps or arbitrary power-loss durability on every filesystem.
- `LockfileHandler.is_vendor_synchronized()` checks manifest records, not
  the presence and content hash of every installed file.
- Git fallback checkout commands may fail without surfacing the failure,
  potentially installing a different ref from the one requested.
- Transactional mutations reject vendor paths outside the project, but
  nontransactional commands such as `vnma init` still need a uniform
  workspace path-validation policy.
- End-to-end native-binary installation across all OS/Python combinations
  and Python 3.14 are not covered by this CI matrix.

## [0.2.9] — Versión anterior publicada

This is the version that was published before the 0.3.0 development work.
Historical changes prior to this branch were not reconstructed for this file.
