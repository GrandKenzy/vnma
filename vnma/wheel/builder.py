"""PEP 517 isolated builder compiling local source directories into wheels."""

from __future__ import annotations

import json
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

        temp_pyproject_created = False
        if not has_pyproject and not has_setup:
            vnma_cfg = resolved_src / "vnma_config.toml"
            vnma_toml = resolved_src / "vnma.toml"
            if vnma_cfg.is_file() or vnma_toml.is_file():
                pkg_name = resolved_src.name
                pkg_version = "1.0.0"
                loaded_cfg = None
                if vnma_cfg.is_file():
                    from vnma.core.package_config import PackageConfig
                    loaded_cfg = PackageConfig.load_from_dir(resolved_src)
                    if loaded_cfg:
                        pkg_name = loaded_cfg.name or pkg_name
                        pkg_version = loaded_cfg.version or pkg_version
                elif vnma_toml.is_file():
                    from vnma.core.config import ConfigHandler
                    loaded_toml = ConfigHandler.load(vnma_toml)
                    pkg_name = loaded_toml.project_name or pkg_name
                    pkg_version = loaded_toml.version or pkg_version

                where_dir = "src" if (resolved_src / "src").is_dir() else "."
                declared_modules = loaded_cfg.modules if (loaded_cfg and loaded_cfg.modules) else []

                file_modules: list[str] = []
                dir_modules: list[str] = []

                if declared_modules:
                    for m in declared_modules:
                        if (resolved_src / m).is_dir():
                            dir_modules.append(m)
                        elif (resolved_src / f"{m}.py").is_file():
                            file_modules.append(m)
                else:
                    file_modules = [
                        f.stem for f in resolved_src.glob("*.py")
                        if not f.name.startswith((".", "_")) and f.name not in ("setup.py", "conftest.py")
                    ]
                    dir_modules = [
                        d.name for d in resolved_src.iterdir()
                        if d.is_dir() and (d / "__init__.py").is_file() and not d.name.startswith(".")
                    ]

                setuptools_blocks: list[str] = []
                if file_modules:
                    setuptools_blocks.append("[tool.setuptools]")
                    setuptools_blocks.append(f"py-modules = {json.dumps(sorted(file_modules))}")

                setuptools_blocks.append("[tool.setuptools.packages.find]")
                setuptools_blocks.append(f'where = ["{where_dir}"]')
                if dir_modules:
                    include_patterns = [f"{m}*" for m in dir_modules]
                    setuptools_blocks.append(f"include = {json.dumps(include_patterns)}")

                setuptools_section = "\n".join(setuptools_blocks)

                synth_content = (
                    "[build-system]\n"
                    'requires = ["setuptools>=61.0"]\n'
                    'build-backend = "setuptools.build_meta"\n\n'
                    "[project]\n"
                    f'name = "{pkg_name}"\n'
                    f'version = "{pkg_version}"\n\n'
                    f"{setuptools_section}\n"
                )
                (resolved_src / "pyproject.toml").write_text(synth_content, encoding="utf-8")
                temp_pyproject_created = True
            else:
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

        try:
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
        finally:
            if temp_pyproject_created:
                try:
                    (resolved_src / "pyproject.toml").unlink(missing_ok=True)
                except Exception:
                    pass
