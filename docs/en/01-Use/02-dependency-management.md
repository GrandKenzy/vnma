# Dependency Management

`vnma` provides commands to resolve, download, compile, install, and uninstall packages across different distribution sources.

---

## 1. Installing Packages

### A. From PyPI

To install a package and resolve its transitive dependency tree:

```bash
# Latest compatible version:
vnma install requests

# Pinned version:
vnma install colorama==0.4.6

# Hyphenated version shorthand:
vnma install pygame-ce-2.5.8

# Version constraint range:
vnma install "urllib3>=2.0.0,<3.0.0"
```

During installation, `vnma`:
1. Queries the PyPI JSON API and filters incompatible platforms and yanked wheels.
2. Traverses the transitive dependency graph, applying PEP 508 environment markers.
3. Downloads or retrieves the wheel from the local user cache (`~/.vnma/cache/wheels/`).
4. Performs a single-pass extraction computing SHA256 hashes and validating against Zip Slip attacks.
5. Records installed files in `manifest.json`.
6. Appends the dependency definition to `vnma.toml`.
7. Updates `vnma.lock`.

---

### B. From Local Directories (Monorepos / Proprietary Code)

To vendor an in-tree or sibling library:

```bash
vnma install "C:/Users/Kentucky/Desktop/Gram"
# or relative path:
vnma install ./packages/my-internal-tool
```

`vnma` builds the local source tree into an isolated wheel via PEP 517 before installation. If the local directory contains a `vnma_config.toml`, its explicit declarations are honored (see [Configuration Specifications](03-configuration-specs.md#2-package-level-configuration-vnma_configtoml)).

In `vnma.toml`, this is recorded as:

```toml
[dependencies]
gram-framework = { path = "C:/Users/Kentucky/Desktop/Gram" }
```

---

### C. From Remote Git Repositories

To install directly from a remote Git repository:

```bash
vnma install git+https://github.com/psf/requests.git@main
```

`vnma` clones the repository into `~/.vnma/cache/git/`, builds a wheel archive in cache, and vendors it into `vendor/`. If the repository contains a `vnma_config.toml`, its declared native DLL paths and CLI entry points are automatically loaded (see [Package-Level Configuration](03-configuration-specs.md#2-package-level-configuration-vnma_configtoml)).

In `vnma.toml`, this is recorded as:

```toml
[dependencies]
requests = { git = "https://github.com/psf/requests.git", branch = "main" }
```

---

## 2. Restoring Dependencies (Team / CI Workflow)

When cloning a project containing `vnma.toml` and `vnma.lock`, the `vendor/` directory is not included in Git. To restore all dependencies:

```bash
vnma install
# or explicitly:
vnma install .
```

`vnma` reads `vnma.toml`, resolves sources (PyPI, local paths, and Git repos), and populates `vendor/` identically.

---

## 3. Uninstalling Packages

To remove a package:

```bash
vnma uninstall colorama
```

`vnma` removes the files tracked in `manifest.json` for that package. Shared files claimed by other installed packages (e.g., in namespace packages) are preserved. Empty parent directories are pruned, and entries are removed from `vnma.toml` and `vnma.lock`.

---

## 4. Listing Installed Packages

To inspect the current vendor directory:

```bash
vnma list
```

Output format:

```text
[vnma] Packages installed in 'vendor':
Package                   Version         Native    
----------------------------------------------------
colorama                  0.4.6           No        
gram-framework            2.0.0b0         No        
pygame-ce                 2.5.8           Yes       
requests                  2.34.2          No        
```

---

## 5. Pruning Orphaned Packages (`vnma prune`)

When removing or modifying dependencies directly in `vnma.toml`, transitive packages that are no longer required by any root dependency remain in `vendor/`.

To inspect or remove orphaned packages:

```bash
# Preview orphaned packages without making modifications:
vnma prune --dry-run

# Interactively confirm pruning:
vnma prune

# Non-interactive confirmation (CI / automation):
vnma prune --yes
```

`vnma prune`:
1. Constructs the reachability closure from all packages declared in `vnma.toml`.
2. Identifies packages present in `manifest.json` that are disconnected from the reachable graph.
3. Deletes orphan files while preserving shared namespace files.
4. Regenerates `__bootstrap__.py` and synchronizes `vnma.lock`.

---

## 6. Offline Mode & Local Repositories

In air-gapped environments, secure CI pipelines, or when working without an internet connection, dependencies can be restored strictly from pre-downloaded wheels:

```bash
# Resolve and install strictly from user wheel cache (~/.vnma/cache/wheels/):
vnma install --offline

# Specify an additional local directory containing wheel archives:
vnma install --offline --find-links ./wheelhouse
```

If a package cannot be satisfied by the available local wheels, `vnma` raises an error with the missing package and constraint without initiating network requests.
