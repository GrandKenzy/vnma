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
gram-framework = { path = "./packages/my-internal-tool" }

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

## 2. Package-Level Configuration (`vnma_config.toml`)

`vnma_config.toml` is an optional, explicit manifest placed in the **root directory** of your library (or repository). Its purpose is to **eliminate heuristic guesswork ("zero magic")** when `vnma` builds and installs packages from GitHub repositories, local source directories, or monorepo subprojects.

When `vnma_config.toml` is present, `vnma` prioritizes its declarations over automated filesystem inspections.

---

### Complete Schema

```toml
[package]
name = "my-library"      # Distribution identifier; may contain hyphens
package = "my_library"  # Python import name: import my_library
version = "0.1.0"
type = "pure-python"  # "pure-python" | "native" | "mixed"

[runtime]
# Relative paths inside the package containing dynamic link libraries (.dll, .so, .dylib)
# vnma automatically registers these with os.add_dll_directory() in Windows at runtime:
dll_directories = [
    "my_library/libs",
    "my_library/vendor_bin",
]

# Enforce hermetic isolation when loading this package (filters external site-packages):
hermetic = true

[exports]
# Top-level module directories to expose to sys.path:
modules = ["my_library"]

# Command-line entry points exposed as executable wrappers in vendor/.bin/:
entry_points = {
    my-tool = "my_library.cli:main",
    runner = "my_library.__main__:main"
}
```

---

### Field Reference

| Section | Field | Type | Description |
| :--- | :--- | :--- | :--- |
| `[package]` | `name` | string | Distribution identifier (PEP 503 normalized). It does not need to equal the imported module name. |
| `[package]` | `package` | string | **Official Python import name**, e.g. `gram` when the distribution is called `gram-framework`. Must use valid dotted Python identifiers. |
| `[package]` | `packname` | string | Legacy alias for `package` (supported for existing Gram manifests). `package` wins when both are set. |
| `[package]` | `version` | string | Package release version (e.g. `"1.0.0"`). Overrides fallback versioning. |
| `[package]` | `type` | string | Package classification: `"pure-python"` (default), `"native"`, or `"mixed"`. |
| `[runtime]` | `dll_directories` | list of strings | Subdirectories containing native shared objects (`.dll`, `.so`, `.dylib`). Injected into `_DLL_SUBDIRS` in `__bootstrap__.py`. |
| `[runtime]` | `hermetic` | boolean | Defaults to `true`. When enabled, prevents runtime fallback to global Python `site-packages`. |
| `[exports]` | `modules` | list of strings | Root Python packages or modules exported by this distribution. |
| `[exports]` | `entry_points` | table / map | Map of binary name to Python callable `module.submodule:function`. Wrappers are written to `.bin/`. |

---

### Gram and EasyC compatibility

Gram's actual manifest uses a distribution name such as
`gram-framework2.0.0Beta`, the legacy field `packname = "gram"`,
`[exports] modules = ["gram"]` and an entry point for `gram.__main__`.
VNMA still accepts that unchanged. New manifests should express the same
contract explicitly:

```toml
[package]
name = "gram-framework2.0.0Beta"
package = "gram"
version = "2.0.0b1"
type = "pure-python"

[runtime]
dll_directories = []
hermetic = true

[exports]
modules = ["gram"]

[exports.entry_points]
gram = "gram.__main__:main"
```

`name` remains the dependency/distribution identity used in VNMA's
manifest and resolution; `package` is the Python import identity,
validated against the installed wheel's modules. It is not a rename
of `gram` to the distribution name.

EasyC's `vnma.toml.example` remains supported without changes, including
editable local dependencies (`{ path = "...", editable = true }`)
and Git branch dependencies (`{ git = "...", branch = "main" }`).

### Atomic installation in 0.3.0

`vnma install`, `update`, `link`, and `reload` stage their
vendor operations in a temporary sibling folder and publish the whole
vendor tree only on success. Package removal and prune from the CLI
also stage modifications. Failed commands restore the previous vendor,
project config and lockfile. A journal supports recovery after a process
crash, with an exclusive lock against concurrent mutations. The
generated CLI wrappers use relocation-safe paths.

Limitations: whole-tree copy staging may require extra disk space
(up to roughly another vendor tree), and on Windows the two renames
are **recoverable but not one atomic directory-swap primitive**.
The generic full-workspace `uninstall --all` purge remains an
explicit destructive operation, not a rollback transaction.

---

### Real-World Use Cases

#### Case A: Pure Python Library with CLI Tools
If your GitHub library provides a command-line tool:

```toml
[package]
name = "devkit"
version = "1.2.0"
type = "pure-python"

[exports]
entry_points = { devkit = "devkit.cli:main" }
```

When installed via `vnma install git+https://github.com/org/devkit.git@main`, `vnma`:
1. Compiles the package into `vendor/devkit/`.
2. Automatically generates `vendor/.vnma_meta/.bin/devkit.cmd` (and `.bat`).
3. Allows running `vnma exec devkit --help` immediately.

---

#### Case B: Library Shipping Native Compiled Binaries (C / C++ / Rust / SDL2)
If your library bundles compiled C extensions or third-party DLLs:

```toml
[package]
name = "fast-engine"
version = "2.0.0"
type = "native"

[runtime]
dll_directories = ["fast_engine/native_libs"]
```

When installed, `vnma`:
1. Bypasses heuristic scanning of binary extensions.
2. Injects `"fast_engine/native_libs"` into the static `$O(1)$` DLL registry in `vendor/__bootstrap__.py`.
3. Ensures Windows Win32 API calls (`os.add_dll_directory`) retain DLL handles persistently in memory.

---

### Precedence Hierarchy

When determining how a package behaves, `vnma` resolves configurations in this strict order:

```text
1. User Project Overrides    ([package.<name>] in the root vnma.toml)
             ↓
2. Package Manifest          (vnma_config.toml in the library source repository)
             ↓
3. PEP 517 / Wheel Standards (.dist-info/entry_points.txt, METADATA, RECORD)
             ↓
4. Automated Heuristics      (Static file extension scanners: .pyd, .so, .dll)
```
