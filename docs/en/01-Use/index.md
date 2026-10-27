# 01. Use

> **Current Version:** `0.3.3` (Beta)

This section explains how to install VNMA, manage project dependencies, configure projects and packages, and run code with the vendored runtime.

---

## Section Overview

| Guide | Summary |
| :--- | :--- |
| **[01. Getting Started](./01-getting-started.md)** | Installing VNMA, `vnma init`, and the first install. |
| **[02. Dependency Management](./02-dependency-management.md)** | PyPI, local, and Git sources; restore, update, prune, offline mode, and live links. |
| **[03. Configuration Specifications](./03-configuration-specs.md)** | `vnma.toml`, `vnma_config.toml`, and precedence rules. |
| **[04. Runtime Execution](./04-runtime-execution.md)** | `vnma run`, hermetic loading, DLL registration, and `vnma exec`. |
| **[05. IDE Integration](./05-ide-integration.md)** | VS Code and PyCharm settings. |
| **[06. Nested Dependencies](./06-nested-dependencies.md)** | Packages that depend on other packages and shared dependencies. |
| **[07. Entry Points Without `vnma run`](./07-entry-point-bootstrap.md)** | Starting a script or CLI with plain `python`. |

---

## Quick Summary

1. **Install:** `vnma init`, then `vnma install <package>` from PyPI, a local path, or a Git URL.
2. **Run:** `vnma run main.py`, or run `vnma insert-import` once and use `python main.py`.
3. **Share:** commit `vnma.toml` and `vnma.lock`; teammates restore with `vnma install`.
