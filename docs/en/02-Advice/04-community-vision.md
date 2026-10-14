# Community Vision & Adoption Aspirations

This document reflects on the current state of dependency management in Python and the philosophy guiding `vnma`.

---

## 1. The Context: The Virtualenv Paradigm

For over two decades, Python's community standard for application isolation has been the virtual environment (`venv` / `virtualenv`). By creating a directory containing a copy or symlink of the Python executable alongside an isolated `site-packages` directory, developers can install libraries without administrative rights or conflicts with system-level packages.

This model solved package isolation for its time, but introduces specific trade-offs:
* **Footprint & Redundancy:** Replicating Python interpreter binaries, scripts, and base tooling for every single project consumes storage and increases initialization latency.
* **Non-Portability:** Virtual environments hardcode absolute paths into script headers (`#!...`) and configuration files (`pyvenv.cfg`), making them non-relocatable and non-exportable across filesystem locations.
* **Tooling Fragmentation:** Activating and deactivating environments introduces cognitive friction across terminal multiplexers, shell scripts, CI runners, and IDE configurations.

---

## 2. The Vendoring Alternative

Languages such as Go, Rust, and JavaScript (with tools like pnpm, yarn zero-installs, and Go vendoring) have demonstrated the ergonomic advantages of project-local dependency storage:
* Dependencies reside cleanly within the workspace.
* The system or container Python executable is reused directly without mutation.
* Sharing a project requires only sharing source definitions; dependencies are restored deterministically in seconds.

`vnma` seeks to offer this workflow natively to Python developers. By combining:
1. Standards-compliant wheel distribution extraction,
2. Hermetic path sanitization at runtime,
3. Deterministic DLL registration on modern operating systems, and
4. Explicit, zero-magic configuration files (`vnma_config.toml`),

`vnma` aims to demonstrate that application-level vendoring in Python is not only feasible, but can be robust, predictable, and clean.

---

## 3. Aspirations for Python Ecosystem Adoption

While virtual environments will remain the default for many workflows, our hope is that `vnma` contributes a viable, lightweight alternative for:
* **CLI Tools & Desktop Applications:** Where self-contained, relocatable distributions simplify packaging.
* **Game Development & Embedded Engines:** (e.g., Pygame, Godot-Python, Blender scripting) where binary dependencies need direct, deterministic loading.
* **Microservices & Serverless:** Where cold-start latency and minimal container layers provide tangible performance benefits.

Feedback, community experimentation, and real-world testing from Python developers are welcome as `vnma` progresses through Beta.
