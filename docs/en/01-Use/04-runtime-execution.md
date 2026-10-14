# Runtime Execution Model

This document explains how `vnma` runs scripts, loads packages hermetically, and resolves dynamic libraries without virtual environments.

---

## 1. Running Applications with `vnma run`

To execute an application script with the vendored runtime active:

```bash
vnma run main.py -- --option value
```

### Process Lifecycle

When invoking `vnma run`:
1. `vnma` locates the project root and its vendor directory.
2. It sets up environment variables:
   * `PYTHONPATH` includes `vendor/.vnma_meta/site` (housing `sitecustomize.py`) and `vendor/`.
   * `PATH` prepends `vendor/.vnma_meta/.bin/` to expose installed CLI tools.
   * `PYTHONNOUSERSITE=1` blocks user-site directories from loading.
3. It launches the Python interpreter directly:
   ```bash
   python main.py --option value
   ```
   Because execution does not use `python -c "exec(...)"`, `sys.argv[0]` correctly points to `main.py`, preserving compatibility with `argparse`, `sys.argv` inspection, and the `multiprocessing` module.

---

## 2. Direct Python Execution (`import vendor.__bootstrap__`)

If you prefer to launch your application directly via `python main.py` without using the `vnma` CLI:

Add the bootstrap import at the top of your entry file:

```python
import vendor.__bootstrap__
import requests
import pygame

# Application code follows...
```

---

## 3. Hermetic Path Sanitization ($\mathbf{P}_{\text{hermetic}}$)

When `__bootstrap__.py` runs, it executes the hermetic projection operator:

1. It identifies standard library paths (`stdlib`, `platstdlib`, interpreter zip files).
2. It identifies global package directories:
   * `purelib` and `platlib` (system `site-packages`).
   * User site-packages (`site.getusersitepackages()`).
   * Distribution package paths (`dist-packages`).
3. It filters `sys.path` in place, removing global and user third-party packages while retaining Python's standard library and the local `vendor/` directory.

This prevents the common issue where code succeeds locally because a dependency exists in the developer's system Python, but fails when deployed to a clean container.

---

## 4. O(1) Dynamic Library Resolution (Windows DLLs)

On Windows with Python 3.8+, Python no longer searches the system `PATH` for DLLs required by compiled extensions (`.pyd`).

Instead of performing recursive filesystem scans (`os.walk`) during startup, `vnma` records the exact relative directories containing `.dll` files in a static tuple during installation:

```python
_DLL_SUBDIRS = ['pygame', 'pygame/_sdl2']
```

At startup:
1. `__bootstrap__.py` iterates over `_DLL_SUBDIRS`.
2. It verifies that each path is strictly confined within `VENDOR_ROOT` (preventing DLL hijacking via external symlinks).
3. It invokes `os.add_dll_directory()` and retains the resulting handle in a global collection `_DLL_HANDLES` to prevent premature garbage collection.

---

## 5. CLI Executables (`vnma exec`)

When packages declare console scripts (e.g., `pytest`, `black`, `gram`):
* `vnma` generates executable wrapper scripts in `vendor/.vnma_meta/.bin/`.
* Wrappers configure `PYTHONPATH` and launch the tool using the host Python interpreter.

To invoke an installed tool:

```bash
vnma exec gram --help
# or directly on Windows:
.\vendor\.vnma_meta\.bin\gram.cmd --help
```
