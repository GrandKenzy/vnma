# Nested Dependencies

A package you install can itself depend on other packages, and several packages can depend on the same one. This document explains how `vnma install` handles those cases.

---

## 1. The Scenario

```text
app
├── shared-lib          (Git)
└── tool-lib            (local path)
    └── shared-lib      (Git, same repository)
```

`app` depends on `shared-lib` and `tool-lib`, and `tool-lib` also depends on `shared-lib`. Both paths lead to the same package, so it must be installed once and before `tool-lib`.

---

## 2. Declaring Dependencies

A package declares what it needs in its own manifest. `vnma` reads the first of these that declares any dependencies:

| Order | File | Where dependencies are declared |
| :--- | :--- | :--- |
| 1 | `vnma.toml` | `[dependencies]` |
| 2 | `vnma_config.toml` | `[dependencies]` |
| 3 | `pyproject.toml` | `[project].dependencies`, or `[tool.vnma.dependencies]` |

Entries use the same forms as the root manifest:

```toml
# tool-lib/vnma_config.toml
[package]
name = "tool-lib"
version = "1.0.0"

[exports]
modules = ["tool_lib"]

[dependencies]
shared-lib = { git = "https://github.com/org/shared-lib.git", branch = "main" }
helper = ">=1.0.0"
local-utils = { path = "../local-utils" }
```

Relative `path` values are resolved from the directory of the manifest that declares them.

The root project declares its own packages as usual:

```toml
# app/vnma.toml
[project]
name = "app"
version = "1.0.0"

[dependencies]
shared-lib = { git = "https://github.com/org/shared-lib.git", branch = "main" }
tool-lib = { path = "../tool-lib" }
```

---

## 3. What `vnma install` Does

```bash
cd app
vnma install
```

1. **Collects** the root dependencies.
2. **Inspects** each Git repository (cloned into `~/.vnma/cache/git/`) and each local path for the dependencies it declares, and queues them.
3. **Deduplicates** by normalized package name. A package reached through several paths is processed once.
4. **Resolves** all PyPI requirements gathered from every level together, so version constraints from different packages are checked against each other.
5. **Orders** the result so a dependency is installed before the packages that need it.
6. **Installs** each package from its source and writes `vnma.lock`.

Each Git repository or local path is visited once, so circular declarations terminate.

---

## 4. Precedence

When the root manifest and a dependency declare the same package, **the root declaration is used**. In the scenario above, the Git branch declared in `app/vnma.toml` applies even if `tool-lib` names a different one.

If the root does not declare a package that only dependencies need, it is installed as a transitive dependency.

> [!WARNING]
> Differences between declarations of the same package (different Git refs or paths) are not reported. Two dependencies that declare the same package from different sources are also not reconciled: the first one discovered is used. Declare the package in the root manifest when the source matters.

---

## 5. Sources That Only Have a Manifest

A Git repository or local directory does not need `pyproject.toml` or `setup.py`. If it only has `vnma_config.toml` or `vnma.toml`, `vnma` builds a standard wheel by generating the build metadata temporarily and removing it afterwards. The source tree is not modified.

The modules to package come from `[exports].modules` in `vnma_config.toml`. When that list is absent, `vnma` packages the top-level directories that contain `__init__.py` and the top-level `.py` files.

The build uses `pip wheel`, so `setuptools` must be obtainable in the build environment.

---

## 6. Lockfile

`vnma.lock` records the real source of every installed package, including those that were not declared in the root manifest:

```json
{
  "packages": {
    "shared-lib": { "source": "git", "git_url": "https://github.com/org/shared-lib.git", "git_ref": "main" },
    "tool-lib": { "source": "local", "path": "/home/user/projects/tool-lib" }
  }
}
```

Restoring with `vnma install` uses these records.

---

## 7. Limits

* Only one version of a package can exist in `vendor/`. Conflicting PyPI constraints raise a `DependencyConflictError` (see [Known Limitations](../02-Advice/02-known-limitations.md)).
* Linked (`editable`) packages are not copied; their own dependencies are installed into `vendor/`, as described in [Dependency Management](02-dependency-management.md#8-live-development-links-vnma-link-vnma-unlink-vnma-reload).
