"""PEP 517 isolated builder compiling local source directories into wheels."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


class BuildError(RuntimeError):
    """Raised when building a wheel from source code fails."""


class SourceBuilder:
    """Builds wheel archives from source trees or repositories."""

    def __init__(self, output_dir: Path) -> None:
        """Initialize builder with target destination directory for wheels."""
        self._output_dir = output_dir
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def build_wheel(self, source_dir: Path) -> Path:
        """Execute pip wheel in a subprocess to produce a standard .whl distribution."""
        resolved_src = source_dir.resolve()
        if not resolved_src.is_dir():
            raise FileNotFoundError(f"Source directory does not exist: {source_dir}")

        has_pyproject = (resolved_src / "pyproject.toml").is_file()
        has_setup = (resolved_src / "setup.py").is_file()

        if not has_pyproject and not has_setup:
            raise BuildError(
                f"Directory '{source_dir.name}' lacks pyproject.toml or setup.py build definitions."
            )

        before_mtimes = {f: f.stat().st_mtime for f in self._output_dir.glob("*.whl")}

        cmd = [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-cache-dir",
            "-w",
            str(self._output_dir),
            str(resolved_src),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise BuildError(
                f"Failed to build wheel from '{source_dir.name}':\n{result.stderr or result.stdout}"
            )

        after_files = list(self._output_dir.glob("*.whl"))
        modified_or_new = [
            f for f in after_files
            if f not in before_mtimes or f.stat().st_mtime > before_mtimes[f]
        ]

        if modified_or_new:
            return sorted(modified_or_new, key=lambda f: f.stat().st_mtime, reverse=True)[0]

        candidates = sorted(
            after_files,
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            return candidates[0]

        raise BuildError(f"Wheel build succeeded but no .whl found in {self._output_dir}")
