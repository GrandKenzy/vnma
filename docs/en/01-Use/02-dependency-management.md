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
vnma install ./packages/my-internal-tool
# or relative path:
vnma install ../shared-library
```

`vnma` builds the local source tree into an isolated wheel via PEP 517 before installation. If the local directory contains a `vnma_config.toml`, its explicit declarations are honored (see [Configuration Specifications](03-configuration-specs.md#2-package-level-configuration-vnma_configtoml)).

In `vnma.toml`, this is recorded as:

```toml
[dependencies]
my-internal-tool = { path = "./packages/my-internal-tool" }
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

## 3. Uninstalling Packages & Purging Workspace

### Uninstalling an Individual Package
To remove a package:

```bash
# Remove package files from vendor/ (retains declaration in vnma.toml for future installs):
vnma uninstall colorama

# Completely remove package from vendor/ AND purge from vnma.toml:
vnma uninstall colorama --del
# or shorthand:
vnma uninstall colorama -d
```

`vnma` removes the files tracked in `manifest.json` for that package. Shared files claimed by other installed packages (e.g., in namespace packages) are preserved, and empty parent directories are pruned. When `--del` (`-d`) is supplied, the dependency definition is also deleted from `vnma.toml`. In both cases, `vnma.lock` is synchronized.

### Purging Entire VNMA Support from a Project
When `vnma uninstall` is invoked without specifying a package, it completely purges all VNMA vendor directories and support files from the folder, leaving the directory completely clean as if VNMA had never been initialized:

```bash
# Interactively purge all VNMA support from the current directory:
vnma uninstall

# Non-interactive confirmation (CI / automation):
vnma uninstall -y

# Purge vendor directories and lockfiles but keep vnma.toml:
vnma uninstall --keep-config -y
```

What `vnma uninstall` cleans:
* Deletes `vendor/` (or `vendor_vnma/`) with all vendored packages and metadata.
* Deletes `vnma.lock`.
* Deletes `vnma.toml` (unless `--keep-config` is provided).
* Cleans VNMA paths from `.vscode/settings.json` (removes `.vscode/` if empty).
* Cleans VNMA `PYTHONPATH` from `.env` (removes `.env` if empty).
* Cleans VNMA ignore blocks from `.gitignore` (removes `.gitignore` if empty).
* Never uninstalls the global `vnma` CLI tool, and never touches user source files (e.g. `main.py`).

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

---

## 7. Updating Dependencies (`vnma update`)

To upgrade dependencies to their latest compatible versions without modifying fixed user constraints:

```bash
# Update all dependencies (PyPI and Git):
vnma update

# Update only PyPI packages:
vnma update --pip

# Update only Git packages (fetches latest commits from remote repositories):
vnma update --git

# Update an individual package and its transitives:
vnma update requests
```

### Pinned Package Protection
Following standard lockfile semantics, `vnma update` respects explicit user pins:
* **PyPI packages** pinned with `==` (e.g., `colorama = "==0.4.6"`) are preserved and skipped silently without errors.
* **Git packages** locked to an immutable `commit` hash or `tag` are preserved and skipped silently without errors.
* Packages with floating constraints (e.g., `*`, `>=2.0.0`, `~=1.5.0`) or floating Git branches (`main`) are upgraded to their latest release.

Upgrades are performed transactionally: obsolete files from previous package versions are safely deleted from `vendor/` without touching shared namespace packages, and `vnma.lock` is updated deterministically.

---

## 8. Live Development Links (`vnma link`, `vnma unlink`, `vnma reload`)

When developing a library (such as an internal SDK or framework like `Gram`) alongside an application that consumes it, rebuilding and installing wheels on every edit slows down iteration.

`vnma` provides zero-copy live development links:

### A. Linking a Local Source Tree (`vnma link`)

```bash
vnma link ../my-library
# or relative path:
vnma link ./packages/my-internal-tool
# or user-relative path:
vnma link ~/projects/my-library
```

1. **Zero-Copy & Session Portable**: Does not copy files into `vendor/`. Automatically serializes paths using user-independent tokens (`~/...`), ensuring the configuration works across different developers and user sessions without hardcoded usernames.
2. **Instant Reflection**: Source changes in the linked library take effect immediately on the next execution (`vnma run` or `import vendor`).
3. **Dependency Resolution**: Inspects `vnma_config.toml` or `pyproject.toml` in the target directory and automatically resolves and installs any declared dependencies into `vendor/`.
4. **IDE Autocompletion**: Injects the target directory into `.vscode/settings.json` (`${userHome}/...` in `python.analysis.extraPaths`) and `.env`.

In `vnma.toml`, it is stored portably as:
```toml
[dependencies]
my-library = { path = "../my-library", editable = true }
```

---

### B. Unlinking a Package (`vnma unlink`)

To remove a linked package:

```bash
# By package name:
vnma unlink my-library

# Or by directory path or portable token:
vnma unlink ../my-library
```

This removes the dependency from `vnma.toml`, clears its search path from `__bootstrap__.py`, and updates IDE configurations.

---

### C. Reconciling & Auto-Pruning (`vnma reload`)

To verify the integrity of all linked dependencies, resolve newly added requirements, and automatically prune packages that are no longer referenced:

```bash
vnma reload
```

* **Integrity Audit**: Checks that all linked directories exist. If a folder was moved or deleted, it aborts with an aesthetic warning box.
* **Auto-Pruning**: If a linked library removed a dependency (or if the library was unlinked), `vnma reload` automatically detects that the package is no longer needed by any part of the project and removes it from `vendor/`.
* **Execution Protection in `vnma run`**: Before running any script, `vnma run` verifies that all linked directories exist, halting with a helpful message instead of raising confusing import tracebacks if a directory is missing.

