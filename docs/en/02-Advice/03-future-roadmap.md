# Future Roadmap

This document outlines completed capabilities in recent releases and future architectural enhancements under consideration for `vnma`.

---

## 1. Recently Implemented

### v0.3.2

* **Nested Dependencies:** Dependencies declared by Git and local packages are resolved with the root manifest, with diamond deduplication and topological install order.
* **`vnma insert-import`:** Adds the bootstrap import to an entry script so it runs with plain `python`.

### v0.3.0

* **Orphan Pruning (`vnma prune`):** Identifies and removes packages in `vendor/` that are no longer referenced by `vnma.toml` or active dependencies.
* **Offline Mode (`--offline`):** Allows restoring dependencies strictly from local wheel caches without contacting external networks.
* **Transactional Staging & Rollback:** Staging in isolated vendor folders with recovery journals to ensure failed installations never corrupt the project.
* **Bounded Backtracking Resolver:** Evaluates transitive dependency graphs and breaks version conflicts cleanly.

---

## 2. Planned & Under Consideration

### A. PEP 658 Metadata Streaming
Download core wheel `.metadata` files directly from PyPI instead of downloading full `.whl` archives during dependency inspection, significantly accelerating initial dependency resolution on slow connections.

### B. Isolated Type Stub Generation (`vnma stubs generate`)
Generate `.pyi` type stub files for compiled C/C++ extensions (`.pyd` / `.so`) by introspecting them in an isolated subprocess, improving autocompletion and type checking in VS Code (Pylance) and PyCharm.

### C. Automated AST Shading (`--shaded`)
For pure-Python libraries with unavoidable version conflicts in complex dependency trees, explore rewriting `ast.Import` and `ast.ImportFrom` nodes to relocate conflicting packages under isolated namespace prefixes.
