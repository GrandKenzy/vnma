# VNMA `1.0.0`

**Release date:** 2026-10-31

> **General Availability (GA)** — Granular test runner suites, developer maintenance tools, hardened execution security, and production stabilization.

This milestone release marks the first stable, production-ready version of VNMA, introducing flexible test suite execution, workspace maintenance utilities (`vnma tools`), resilient flag parsing, and cross-cutting security hardening.

## Added

- **Developer maintenance utilities (`vnma tools`):**
  - Modular tool suite located under `vnma/tools/`.
  - `vnma tools bigfiles [--l <threshold>] [paths...]`: Audit code files exceeding useful lines of code (SLOC), strictly filtering empty lines, comments (`#`), and multi-line docstrings in Python, rendered in an aesthetic table.
  - `vnma tools cacheclean [paths...]`: Recursively purge `__pycache__` directories and standalone `.pyc`/`.pyo` compiled bytecode files, reporting space freed.
  - `vnma tools search "<pattern>" [--outputs <files...>]`: Fast string and regex search across workspace files or specified outputs.
  - Dual syntax support: supports both subcommand (`vnma tools bigfiles`) and flag (`vnma tools --bigfiles`) invocations.
- **Granular test suite execution (`vnma test`):**
  - Run specific test suites or folders inside `tests/` directly: `vnma test <folder>` (e.g. `vnma test unit`, `vnma test e2e`).
  - Target individual test files with or without extensions/prefixes: `vnma test sample` or `vnma test test_sample.py`.
  - Multi-suite orchestration: run multiple folders or files in a single invocation (`vnma test unit e2e`).
  - Automatic fallback: `vnma test` without arguments continues running all discovered suites across `tests/`, `test/`, or `testing/`.
- **Intelligent test argument and flag separation:**
  - Preserves flags with values (e.g. `-k <expr>`, `-m <mark>`, `--tb <style>`, `--maxfail <n>`) preventing flag arguments from being mistakenly treated as test suite targets.
  - Early detection and friendly reporting when a requested test suite or target file is not found.

## Security

- **Path traversal and containment verification:**
  - `vnma test`: Strict containment checks prevent directory traversal (`..`) or absolute paths escaping the project root.
  - `vnma exec`: Validates executable binaries, sanitizing binary names and ensuring resolution is strictly confined to `vendor/.bin`.
  - `vnma/pypi/cache.py`: Sanitizes wheel cache filenames to prevent directory traversal during remote package downloads.
- **Git option and argument injection prevention:**
  - `GitCloner`: Rejects URLs and branch/tag references beginning with a dash (`-`) and enforces the `--` argument delimiter on `git clone` invocations.

## Verification

- Extended test suite with dedicated regression tests in `tests/test_cli.py`, `tests/test_runtime.py`, and `tests/test_tools.py`.
- 100% passing automated test suite across all modules.
