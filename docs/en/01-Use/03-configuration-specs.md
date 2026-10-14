# Configuration Specifications

This document defines the schema and behavior of `vnma.toml` (project level) and `vnma_config.toml` (package level).

---

## 1. Project Configuration (`vnma.toml`)

The root `vnma.toml` declares project dependencies, vendor settings, and package-specific overrides.

### Complete Example

```toml
[project]
name = "my-application"
version = "0.1.0"

[dependencies]
# Standard PyPI constraints:
colorama = "==0.4.6"
pygame-ce = ">=2.5.0, <2.6.0"

# Local source directory dependency:
gram-framework = { path = "C:/Users/Kentucky/Desktop/Gram" }

# Git repository dependency:
custom-fork = { git = "https://github.com/user/fork.git", branch = "main" }

[dev-dependencies]
pytest = ">=8.0.0"

[tool.vnma]
vendor_dir = "vendor"
ide_integration = ["vscode", "pycharm"]

# Explicit overrides for third-party packages:
[package.unusual-package]
dll_directories = ["unusual_package/libs"]
entry_points = { run-tool = "unusual_package.cli:run" }
```

### Fields

* **`[project]`**: Basic project metadata (`name`, `version`).
* **`[dependencies]`**: Mapping of package names to version constraints, local filesystem paths, or Git repositories.
* **`[tool.vnma]`**:
  * `vendor_dir`: Directory name for vendoring (`vendor` by default; automatically adjusted to `vendor_vnma` if `vendor/` is pre-occupied).
  * `ide_integration`: List of IDEs to synchronize (`["vscode", "pycharm"]`).
* **`[package.<name>]`**: Overrides applied to specific packages during installation.

---

## 2. Package Configuration (`vnma_config.toml`)

Placed inside the root directory of a proprietary or local package, `vnma_config.toml` eliminates runtime heuristics by explicitly declaring the package's requirements.

### Schema

```toml
[package]
name = "gram-framework"
version = "2.0.0b0"
type = "pure-python" # "pure-python" | "native" | "mixed"

[runtime]
# Relative paths containing dynamic link libraries (.dll, .so, .dylib)
dll_directories = []

# Enforce hermetic isolation when loading this package
hermetic = true

[exports]
# Top-level module directories to expose
modules = ["gram", "sjson"]

# Command-line entry points
entry_points = { gram = "gram.__main__:main" }
```

### Precedence Hierarchy

1. **User Overrides:** `[package.<name>]` defined in the project's root `vnma.toml`.
2. **Package Manifest:** `vnma_config.toml` present in the package source tree.
3. **PEP Standards:** Information from `.dist-info/` (`entry_points.txt`, `RECORD`).
4. **Automated Detection:** Analyzers such as `BinaryDetectorVisitor`.
