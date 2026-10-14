# Beta Status & Stability Considerations

`vnma` is currently in **Beta (v0.2.0)**. This document provides an objective summary of tested environments, stability expectations, and recommended deployment practices.

---

## 1. What Has Been Validated

The following capabilities have been tested across representative scenarios:

* **CPython Compatibility:** Validated on CPython 3.11, 3.12, and 3.14 on Windows (amd64) and Linux.
* **Native C/C++ Extensions:** Verified with packages distributing compiled `.pyd` files and shared libraries (e.g., `pygame-ce` bundling SDL2 runtime DLLs).
* **Transitive Dependency Graphs:** Validated with deep dependency trees (e.g., `requests` resolving `urllib3`, `certifi`, `idna`, `charset-normalizer`).
* **PEP 517 Local Builds:** Verified using local source trees containing `pyproject.toml` (e.g., `Gram Framework`).
* **Security Controls:** Validated single-pass extraction, canonical path checking against Zip Slip, and symlink prohibition.
* **Hermetic Execution:** Validated exclusion of global `site-packages` while retaining CPython standard library extensions.

---

## 2. Recommended Usage During Beta

1. **Development & Tooling:** Ideal for developer workflows, scripts, desktop tools, and self-contained projects where avoiding virtual environment overhead is desired.
2. **Container Deployments:** Suitable for containerized environments where building wheels into a single project layer reduces container image size.
3. **Critical Production Services:** For mission-critical server deployments, ensure full test suite coverage passes under `vnma run` before replacing traditional virtual environment pipelines.

---

## 3. Reporting Issues

If you encounter unexpected resolution behavior, DLL load failures, or packaging discrepancies, please report them with:
* The exact Python version and platform architecture (`python -V`, OS details).
* The contents of `vnma.toml` and `vnma.lock`.
* The terminal output with error tracebacks.
