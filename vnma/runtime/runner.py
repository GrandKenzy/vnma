"""Subprocess runner configured with vendored environment variables."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from vnma.core.context import ProjectContext


class EntryPointResolver:
    """Resolves execution entrypoints from scripts, directories, or default conventions."""

    def __init__(self, root: Path) -> None:
        """Initialize resolver with base project path."""
        self._root = root

    def resolve(self, target: str | None = None) -> Path:
        """Resolve python entrypoint script path from user argument or project defaults."""
        if target:
            target_path = Path(target)
            if not target_path.is_absolute():
                target_path = self._root / target_path

            if target_path.is_file():
                return target_path.resolve()

            if target_path.is_dir():
                candidates = [
                    target_path / "main.py",
                    target_path / "__main__.py",
                    target_path / "app.py",
                ]
                for cand in candidates:
                    if cand.is_file():
                        return cand.resolve()
                raise FileNotFoundError(
                    f"No entry point found in directory '{target}' "
                    f"(searched for main.py, __main__.py, app.py)."
                )

            raise FileNotFoundError(f"Script or directory '{target}' not found.")

        default_candidates = [
            self._root / "main.py",
            self._root / "src" / "main.py",
            self._root / "source" / "main.py",
            self._root / "app.py",
        ]
        for cand in default_candidates:
            if cand.is_file():
                return cand.resolve()

        raise FileNotFoundError(
            "No default entry point found in project "
            "(searched for main.py, src/main.py, source/main.py, app.py). "
            "Please specify a script: vnma run <script.py>"
        )


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

        injected_parts = [site_hook_dir, vendor_str]
        try:
            from vnma.core.link_manager import LinkManager
            from vnma.core.path_resolver import PortablePathResolver
            for linked in LinkManager(self._context).get_linked_specs():
                if linked.path and linked.path.is_dir():
                    _, module_paths, _ = LinkManager.inspect_target(linked.path)
                    for mp in module_paths:
                        resolved_mp = str(PortablePathResolver.expand(mp, base_dir=self._context.project_root))
                        if resolved_mp not in injected_parts:
                            injected_parts.append(resolved_mp)
        except Exception:
            pass

        injected = os.pathsep.join(injected_parts)
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

    def run_module(
        self,
        module: str,
        args: Sequence[str] = (),
        env_overrides: dict[str, str] | None = None,
    ) -> int:
        """Execute a Python module (-m <module>) in the context of vendored dependencies."""
        env = self._build_vendor_env()
        if env_overrides:
            env.update(env_overrides)
        cmd = [sys.executable, "-m", module, *args]
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
