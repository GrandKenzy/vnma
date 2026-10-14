# Getting Started with VNMA

This document covers installation, project initialization, and the basic directory layout managed by `vnma`.

---

## 1. System Requirements

* Python 3.11, 3.12, 3.13, or 3.14.
* Operating System: Windows 10/11, Linux (x86_64, aarch64), or macOS.
* Standard `pip` and `git` binaries available on `PATH`.

---

## 2. Installation

Install `vnma` into your system or active user environment:

```bash
# Clone the repository and install in editable mode:
git clone https://github.com/GrandKenzy/vnma.git
cd vnma
pip install -e .
```

Verify that the CLI executable is available:

```bash
vnma --help
```

---

## 3. Project Initialization

To prepare an existing or new project directory for vendoring:

```bash
cd my_project
vnma init
```

The `vnma init` command performs the following automated setup steps:

1. **Manifest File:** Generates `vnma.toml` if neither `vnma.toml` nor `pyproject.toml` exists.
2. **Vendor Directory:** Creates `vendor/` (or `vendor_vnma/` if `vendor/` is already occupied by non-vnma files).
3. **Runtime Loader:** Generates `vendor/__bootstrap__.py` and `vendor/__init__.py`.
4. **Subprocess Hook:** Creates `vendor/.vnma_meta/site/sitecustomize.py`.
5. **Git Rules:** Appends ignore patterns to `.gitignore` to prevent vendored packages from entering version control.
6. **IDE Config:** Injects search paths into `.vscode/settings.json`, `.idea/*.iml`, and `.env`.
7. **Lockfile:** Initializes `vnma.lock`.

### 3.1 Generating a Clean Configuration (`vnma generate`)

If you only want to generate an empty configuration file without running the full environment initialization:

```bash
# Generate empty vnma.toml for the current project (version 1.0.0):
vnma generate

# Or generate a package manifest (vnma_config.toml) for libraries/repositories:
vnma generate --package
```

* Flags:
  * `-f`, `--force`: Overwrite existing configuration if already present.
  * `-p`, `--package`, `--lib`: Generate library manifest (`vnma_config.toml`) instead of project file (`vnma.toml`).

---

## 4. Managed Project Structure

After running `vnma init` and installing packages, your workspace will reflect the following organization:

```text
my_project/
├── .env                       # PYTHONPATH definition for IDE execution
├── .gitignore                 # Automatically ignores vendor artifacts
├── .vscode/
│   └── settings.json          # extraPaths configured for Pylance/Jedi
├── vendor/                    # Local vendored packages
│   ├── .vnma_meta/
│   │   ├── .bin/              # Generated script wrappers (CLI launchers)
│   │   ├── site/              # sitecustomize.py for subprocess injection
│   │   ├── manifest.json      # Cryptographic file manifest per package
│   │   └── python_version     # Recorded build-time Python version
│   ├── __bootstrap__.py       # O(1) runtime path and DLL directory loader
│   ├── __init__.py            # Module entry point importing bootstrap
│   └── <packages>/            # Extracted Python packages and compiled modules
├── vnma.toml                  # Declarative dependency specifications
├── vnma.lock                  # Deterministic lockfile tracking versions and sources
└── main.py                    # Your application entry point
```
