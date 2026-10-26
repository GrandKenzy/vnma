# VNMA `0.3.2`

**Release date:** pending

> **Beta** — Transitive dependencies across sources and entry-point bootstrap

This release closes two gaps: dependencies declared by Git or local packages
were ignored during install, and projects had no way to start without
`vnma run`.

## Added

- **`vnma insert-import [target]` command:** inserts
  `import vendor.__bootstrap__  # From VNMA.` into a script so it can run with
  plain `python` instead of `vnma run`.
  - The import uses the project's active vendor directory name (for example
    `vendor_vnma`).
  - Without `target`, it uses the same entry-point discovery as `vnma run`
    (`main.py`, `src/main.py`, `source/main.py`, `app.py`) and falls back to
    `main.py`.
  - If the file does not exist, a minimal runnable template is created.
  - A leading shebang and an encoding declaration are preserved; the import is
    placed right after them.
  - It is idempotent: a file that already references `__bootstrap__` is left
    untouched.
- **Transitive dependencies across sources:** `vnma install` now inspects the
  dependencies declared by Git and local packages and resolves them together
  with the root manifest (see
  [Nested Dependencies](../docs/en/01-Use/06-nested-dependencies.md)).
  - **Diamond deduplication:** a package required through several paths is
    resolved, built, and installed once.
  - **Root precedence:** when the root manifest and a dependency declare the
    same package, the root declaration is used.
  - **Topological install order:** shared dependencies are installed before the
    packages that need them.
  - **Cycle safety:** each Git repository or local path is visited once.
- **`[dependencies]` in `vnma_config.toml`:** package manifests can declare
  PyPI constraints, `{ git = ... }`, and `{ path = ... }` dependencies.
- **`DependencyInspector`:** a single place that reads `vnma.toml`,
  `vnma_config.toml`, and `pyproject.toml` (`[project].dependencies` and
  `[tool.vnma.dependencies]`) from a source directory.
- **Pure VNMA packages can be built:** a source tree that only has
  `vnma_config.toml` or `vnma.toml` (no `pyproject.toml` or `setup.py`) is
  built into a standard wheel. The build metadata is generated temporarily and
  removed afterwards; the source tree is not modified.
- **Lockfile sources for transitive packages:** `vnma.lock` records the real
  source (`git`, `local`, or `pypi`) of packages that were not declared in the
  root manifest.

## Changed

- `LinkManager.inspect_target` delegates to `DependencyInspector`, so
  `vnma link` and `vnma install` read dependencies consistently.
- `LockfileHandler.update` accepts the resolved specifications of an install.

## Fixed

- **Dependencies of Git and local packages were ignored.** Wheels were built
  with `--no-deps` and the source's own declarations were never read, leaving
  such packages installed without what they import.
- **Sources with only `vnma_config.toml` failed to build** with a missing build
  definition error.

## Documentation

- Added a documentation index and section indexes.
- Added [Nested Dependencies](../docs/en/01-Use/06-nested-dependencies.md) and
  [Entry Points Without `vnma run`](../docs/en/01-Use/07-entry-point-bootstrap.md).
- Moved release notes to this `changelog/` folder with one file per version.
- Replaced project-specific names in documentation with generic examples.

## Verification

- Full unit test suite: 130 tests passed (`python -m unittest discover tests`),
  including new tests for `insert-import`, dependency inspection, diamond
  resolution order, and pure-manifest wheel builds.
- An isolated example in `examples/` installs a Git dependency that is also
  required by a local sub-project two levels deep. It runs with `python`,
  with `vnma run`, and through `vnma exec`.

## Known issues

- When the root manifest and a dependency declare the same package with
  different Git refs or paths, the root declaration silently wins and the
  difference is not reported.
- Two non-root dependencies that declare the same package from different
  sources are not reconciled; the first one discovered is used.
- `vnma insert-import` treats any occurrence of `__bootstrap__` in the file as
  an existing import.
