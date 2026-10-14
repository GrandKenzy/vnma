# Future Roadmap

This document outlines planned capabilities and architectural enhancements under consideration for subsequent releases of `vnma`.

---

## 1. Automated AST Shading (`--shaded`)

To address diamond dependency conflicts in pure-Python packages, a future release will introduce an AST-based shading transformation:
* Re-writes `ast.Import` and `ast.ImportFrom` nodes to relocate conflicting packages under `_vnma_shaded/v1/<pkg>/`.
* Updates internal `importlib.import_module` calls.
* Excludes native binary modules where compiled entry points (`PyInit_*`) cannot be rewritten without recompilation.

---

## 2. Orphan Pruning (`vnma prune`)

A dedicated command to audit `vendor/` against `vnma.toml` and `vnma.lock`:
* Identifies unmanaged packages or packages removed from project configuration.
* Safely removes orphaned files while protecting shared files.
* Prunes empty directory branches.

---

## 3. Strict Offline Mode (`--offline`)

A flag forcing `vnma` to operate strictly from local caches (`~/.vnma/cache/wheels/` and `~/.vnma/cache/git/`):
* Fails fast if any required wheel is absent from disk.
* Ideal for air-gapped environments, secure enterprise builds, and rapid CI execution.

---

## 4. Isolated Type Stub Generation (`vnma stubs generate`)

To ensure type checkers and IDEs (Pylance, Pyright, Mypy) have full visibility into compiled C/C++ extensions:
* Runs an isolated sub-process with `__bootstrap__` active.
* Introspects native binary members (`.pyd` / `.so`).
* Generates `.pyi` stub files alongside compiled artifacts without risking interpreter crashes in the main process.
