"""Subprocess runner configured with vendored environment variables."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from vnma.core.context import ProjectContext


class ScriptRunner:
    """Executes Python scripts or binaries in the context of vendored dependencies."""

    def __init__(self, context: ProjectContext) -> None:
        """Initialize runner with target project context."""
        self._context = context

    def _build_vendor_env(self) -> dict[str, str]:
        """Construct environment dictionary with sitecustomize and vendor paths."""
        env = os.environ.copy()
        site_hook_dir = str(self._context.meta_path / "site")
        vendor_str = str(self._context.vendor_path)

        injected = f"{site_hook_dir}{os.pathsep}{vendor_str}"
        is_hermetic = env.get("VNMA_HERMETIC", "1") == "1"

        if is_hermetic:
            env["PYTHONPATH"] = injected
        else:
            current_pythonpath = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = (
                f"{injected}{os.pathsep}{current_pythonpath}"
                if current_pythonpath
                else injected
            )


        bin_str = str(self._context.bin_path)
        current_path = env.get("PATH", "")
        env["PATH"] = f"{bin_str}{os.pathsep}{current_path}" if current_path else bin_str
        env["PYTHONNOUSERSITE"] = "1"
        return env

    def run_script(self, script_path: Path, args: Sequence[str] = ()) -> int:
        """Execute a Python file natively preserving sys.argv[0] and multiprocessing."""
        resolved_script = script_path.resolve()
        env = self._build_vendor_env()
        cmd = [sys.executable, str(resolved_script), *args]
        completed = subprocess.run(cmd, env=env, cwd=str(self._context.project_root))
        return completed.returncode

    def exec_binary(self, binary_name: str, args: Sequence[str] = ()) -> int:
        """Execute a CLI tool installed in the vendor .bin directory."""
        bin_dir = self._context.bin_path
        candidates = (
            [bin_dir / f"{binary_name}.cmd", bin_dir / f"{binary_name}.bat", bin_dir / binary_name]
            if sys.platform == "win32"
            else [bin_dir / binary_name, bin_dir / f"{binary_name}.cmd"]
        )

        target_bin = next((c for c in candidates if c.is_file()), None)
        if not target_bin:
            raise FileNotFoundError(
                f"Binary '{binary_name}' not found in {bin_dir}. Ensure package is installed."
            )

        env = self._build_vendor_env()
        cmd = [str(target_bin), *args]
        completed = subprocess.run(cmd, env=env, cwd=str(self._context.project_root))
        return completed.returncode
