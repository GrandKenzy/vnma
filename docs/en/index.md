# VNMA Documentation

> **Version:** `0.3.2` (Beta)
> **Runtime:** CPython 3.11+ · Windows and Linux

Welcome to the official English documentation for **VNMA**, a dependency and
vendoring manager that installs packages into a local project directory
(`vendor/`) instead of creating virtual environments.

---

## Documentation Index

### [01. Use](./01-Use/index.md)
Installing VNMA, managing dependencies, configuring projects and packages, and running code.
- **[01. Getting Started](./01-Use/01-getting-started.md)** — Installing VNMA, initializing a project, and the first install.
- **[02. Dependency Management](./01-Use/02-dependency-management.md)** — Installing from PyPI, local paths, and Git; updating, pruning, offline mode, and live links.
- **[03. Configuration Specifications](./01-Use/03-configuration-specs.md)** — Schema of `vnma.toml` and `vnma_config.toml`, and configuration precedence.
- **[04. Runtime Execution](./01-Use/04-runtime-execution.md)** — `vnma run`, hermetic loading, DLL registration, and `vnma exec`.
- **[05. IDE Integration](./01-Use/05-ide-integration.md)** — VS Code and PyCharm configuration.
- **[06. Nested Dependencies](./01-Use/06-nested-dependencies.md)** — Packages that depend on other packages, shared dependencies, and install order.
- **[07. Entry Points Without `vnma run`](./01-Use/07-entry-point-bootstrap.md)** — Running a script or CLI with plain `python` using `vnma insert-import`.

### [02. Advice](./02-Advice/index.md)
Stability, limitations, and direction of the project.
- **[01. Beta Status](./02-Advice/01-beta-status.md)** — What has been validated and how to use VNMA during beta.
- **[02. Known Limitations](./02-Advice/02-known-limitations.md)** — Constraints that come from Python's runtime model and the current implementation.
- **[03. Future Roadmap](./02-Advice/03-future-roadmap.md)** — Recently implemented work and planned enhancements.
- **[04. Community Vision](./02-Advice/04-community-vision.md)** — Where VNMA fits and where it does not.

### [Changelog](../../changelog/README.md)
Versioned release notes, one file per version.
