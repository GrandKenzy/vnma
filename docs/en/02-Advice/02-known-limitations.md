# Known Limitations

This document outlines structural and design limitations inherent to Python's runtime model and the current implementation of `vnma`.

---

## 1. Flat Runtime Namespace (`sys.modules`)

Unlike ecosystems such as Node.js (npm), which allow nested module hierarchies via relative file resolution, CPython uses a single global dictionary (`sys.modules`) for all imported modules in a process.

* **Impact:** Two mutually exclusive versions of the same library (e.g., `urllib3<2.0.0` and `urllib3>=2.0.0`) cannot be imported simultaneously into the same Python process under the same name without source-code shading or namespace mangling.
* **Current Behavior:** `vnma` detects this condition during dependency graph resolution and raises a `DependencyConflictError` rather than writing an ambiguous or corrupted state to `vendor/`.

---

## 2. Shared Library (DLL/SO) Name Collisions

On Windows and Linux, the dynamic linker binds a shared library by its base filename in the process address space.

* **Impact:** If Package A bundles `zlib.dll` (v1.2.8) and Package B bundles `zlib.dll` (v1.3.1), the operating system's loader will bind to whichever DLL is loaded first. If ABI compatibility diverges, memory violations can occur.
* **Current Behavior:** `vnma` computes SHA256 hashes for all DLLs and logs explicit collision warnings when differing binaries share the same filename.

---

## 3. Packages with Non-Standard Runtime Paths

Certain legacy Python packages perform runtime inspection of `site-packages` or assume they reside directly within `sys.prefix`.

* **Impact:** While most modern packages use `__file__`, `importlib.resources`, or `importlib.metadata` (which work seamlessly with `vnma`), packages that hardcode checks against `sys.prefix` or `site.USER_BASE` may require explicit configuration in `vnma.toml`.

---

## 4. PEP 658 Network Optimization

PyPI supports PEP 658 core metadata downloads (fetching small `.metadata` files rather than full `.whl` archives during dependency resolution). `vnma` currently resolves requirements by inspecting release metadata via the PyPI JSON API and downloading wheels into cache. Full PEP 658 Simple API streaming is scheduled for upcoming releases.

---

## 5. Same Package Declared from Different Sources

When the same package is declared by the root manifest and by a dependency, or by two dependencies, with different Git refs or paths:

* **Impact:** only one source can be installed into `vendor/`.
* **Current Behavior:** the root declaration wins. Between two non-root declarations, the first one discovered is used. The difference is not reported. See [Nested Dependencies](../01-Use/06-nested-dependencies.md#4-precedence).
