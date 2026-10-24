# VNMA (Vendor Manager)

> **Status:** Beta (v0.3.0)  
> **Platform Support:** CPython 3.11+ (Tested on Windows and Linux)

`vnma` is a dependency and vendoring manager for Python projects. It manages project dependencies inside a local, isolated vendor directory (`vendor/` or `vendor_vnma/`) instead of creating or replicating full Python virtual environments (`venv`).

---

## Overview

Traditional Python development relies on virtual environments, which duplicate the interpreter executable and standard library layout. While effective for system isolation, virtual environments introduce overhead in container builds, portable deployments, and shared team workflows where only runtime libraries are required.

`vnma` addresses this by downloading, building, and extracting platform-compatible wheels directly into the project directory while maintaining runtime path isolation and native binary compatibility.

### Key Capabilities

* **Hermetic Path Isolation:** Sanitizes `sys.path` during execution to prevent accidental leakage from system or user `site-packages`.
* **Static O(1) Binary Resolution:** Avoids filesystem tree traversal at startup by recording precomputed dynamic link library (DLL/SO) paths during installation.
* **Transitive DAG Resolution:** Evaluates version constraints across dependency trees, evaluating PEP 508 environment markers and detecting version conflicts.
* **Explicit Configuration (`vnma_config.toml`):** Allows local packages and complex dependencies to specify exact DLL directories, entry points, and export boundaries without heuristic guesswork.
* **Multi-Source Support:** Installs packages from PyPI, local filesystem paths (monorepos), and remote Git repositories.
* **Reproducible Builds:** Emits a deterministic `vnma.lock` tracking versions, sources, and binary metadata.
* **Automatic IDE Configuration:** Generates configuration for Visual Studio Code (`extraPaths`) and JetBrains PyCharm (`.idea` and `.env`).

---

## Current Status: Beta Notice

`vnma` is currently in **Beta**. While core workflows—such as installing native packages (`pygame-ce`), complex transitive graphs (`requests`), and local source trees—have been validated, edge cases exist across different platforms, compilers, and non-standard packaging layouts.

Users are encouraged to verify builds in testing environments before deploying to critical production pipelines. See [docs/en/02-Advice/01-beta-status.md](docs/en/02-Advice/01-beta-status.md) for detailed considerations.

---

## Quickstart

### Installation

Install `vnma` directly from PyPI using `pip`:

```bash
pip install vnma
```

Or for development:

```bash
pip install -e .
```

### Basic Commands

Initialize a project:
```bash
vnma init
```

Install a package from PyPI:
```bash
vnma install requests
```

Install a package from a local directory:
```bash
vnma install "C:/path/to/my-library"
```

Execute a script using the vendored runtime:
```bash
vnma run main.py
```

List installed packages:
```bash
vnma list
```

Prune orphaned packages not declared in `vnma.toml`:
```bash
vnma prune --dry-run
vnma prune --yes
```

Restore dependencies in offline mode:
```bash
vnma install --offline
```

Update dependencies (ignoring pinned packages):
```bash
# Update both PyPI and Git dependencies
vnma update

# Update only PyPI dependencies
vnma update --pip

# Update only Git repositories (pulls latest branch commit)
vnma update --git
```

---

## Documentation

Full documentation is available in the `docs/` directory:

* **Usage Guide:** [docs/en/01-Use/](docs/en/01-Use/)
  * [01. Getting Started](docs/en/01-Use/01-getting-started.md)
  * [02. Dependency Management](docs/en/01-Use/02-dependency-management.md)
  * [03. Configuration Specifications](docs/en/01-Use/03-configuration-specs.md)
  * [04. Runtime Execution Model](docs/en/01-Use/04-runtime-execution.md)
  * [05. IDE Integration](docs/en/01-Use/05-ide-integration.md)
* **Design & Guidance:** [docs/en/02-Advice/](docs/en/02-Advice/)
  * [01. Beta Status & Stability](docs/en/02-Advice/01-beta-status.md)
  * [02. Known Limitations](docs/en/02-Advice/02-known-limitations.md)
  * [03. Future Roadmap](docs/en/02-Advice/03-future-roadmap.md)
  * [04. Community Vision](docs/en/02-Advice/04-community-vision.md)

---

## License

This software is released under a modified permissive license. Commercial resale of the tool itself is prohibited, and bundled distributions must retain reciprocal licensing. See [LICENSE](LICENSE) for terms.
