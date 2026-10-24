"""Artifact visitors handling native binaries, file manifests, and script wrappers."""

from __future__ import annotations

import configparser
import sys
from pathlib import Path

from vnma.core.models import InstalledFile
from vnma.visitors.base import ArtifactElement, ArtifactVisitor


class BinaryDetectorVisitor(ArtifactVisitor):
    """Detects native binaries (.pyd/.so/.dll) and tracks DLL SHA256 hashes for collision checks."""

    BINARY_EXTENSIONS = {".pyd", ".so", ".dylib", ".dll"}

    def __init__(self, existing_dll_hashes: dict[str, tuple[str, str]] | None = None) -> None:
        """Initialize detector optionally with existing DLL hashes for collision detection."""
        self._existing_dlls = existing_dll_hashes or {}
        self._dll_directories: set[str] = set()
        self._has_binaries = False
        self._collisions: list[str] = []

    @property
    def has_binaries(self) -> bool:
        """Indicate whether any native binary was identified."""
        return self._has_binaries

    @property
    def dll_directories(self) -> list[str]:
        """Directories containing dynamic libraries relative to vendor root."""
        return sorted(self._dll_directories)

    @property
    def collisions(self) -> list[str]:
        """Recorded collision warnings when another package provides a mismatched DLL."""
        return self._collisions

    def visit_artifact(self, artifact: ArtifactElement) -> None:
        """Inspect file extension to detect compiled binary or dynamic link library."""
        ext = artifact.relative_path.suffix.lower()
        if ext not in self.BINARY_EXTENSIONS:
            return

        self._has_binaries = True
        parent_rel = str(artifact.relative_path.parent).replace("\\", "/")
        self._dll_directories.add(parent_rel if parent_rel != "." else "")

        if ext in (".dll", ".so", ".dylib"):
            dll_name = artifact.relative_path.name.lower()
            if dll_name in self._existing_dlls:
                prev_sha, prev_pkg = self._existing_dlls[dll_name]
                if prev_sha != artifact.sha256:
                    self._collisions.append(
                        f"DLL collision detected for '{dll_name}': "
                        f"conflicts with package '{prev_pkg}' (SHA256 mismatch)"
                    )


class RecordCollectorVisitor(ArtifactVisitor):
    """Collects pre-computed single-pass hashes and sizes for the installation manifest."""

    def __init__(self) -> None:
        """Initialize storage for collected installed files."""
        self._installed_files: list[InstalledFile] = []

    @property
    def installed_files(self) -> list[InstalledFile]:
        """Ordered collection of recorded installed files."""
        return self._installed_files

    def visit_artifact(self, artifact: ArtifactElement) -> None:
        """Record pre-computed hash and size without secondary disk I/O."""
        rel_str = str(artifact.relative_path).replace("\\", "/")
        self._installed_files.append(
            InstalledFile(
                relative_path=rel_str,
                sha256=artifact.sha256,
                size_bytes=artifact.size_bytes,
            )
        )


class ScriptWrapperVisitor(ArtifactVisitor):
    """Generates cross-platform command-line launcher wrappers for package scripts."""

    def __init__(self, bin_dir: Path, vendor_dir: Path) -> None:
        """Initialize launcher generator with destination bin directory and vendor root."""
        self._bin_dir = bin_dir
        self._vendor_dir = vendor_dir
        self._discovered_entry_points: dict[str, str] = {}

    @property
    def entry_points(self) -> dict[str, str]:
        """Command names mapped to their target script or module paths."""
        return self._discovered_entry_points

    def visit_artifact(self, artifact: ArtifactElement) -> None:
        """Detect entry_points.txt or scripts to generate executable launchers."""
        if artifact.relative_path.name == "entry_points.txt":
            self._process_entry_points_file(artifact.absolute_path)
        elif artifact.is_data_script:
            self._create_direct_script_wrapper(artifact)

    def _process_entry_points_file(self, file_path: Path) -> None:
        """Parse standard entry_points.txt using configparser."""
        parser = configparser.ConfigParser()
        try:
            parser.read(file_path, encoding="utf-8")
        except Exception:
            return

        if parser.has_section("console_scripts"):
            for cmd_name, target in parser.items("console_scripts"):
                cmd_clean = cmd_name.strip()
                target_clean = target.strip()
                self._discovered_entry_points[cmd_clean] = target_clean
                self._generate_executable_wrapper(cmd_clean, target_clean)

    def _generate_executable_wrapper(self, command_name: str, target: str) -> None:
        """Create shell and Windows batch launchers independent of vendor directory name."""
        self._bin_dir.mkdir(parents=True, exist_ok=True)
        py_exe = sys.executable
        module_part, _, attr_part = target.partition(":")
        attr_expr = f"getattr(mod, {attr_part!r})()" if attr_part else ""

        py_snippet = (
            f"import importlib, sys; "
            f"mod = importlib.import_module({module_part!r}); "
            f"sys.exit({attr_expr})"
        )

        bat_file = self._bin_dir / f"{command_name}.cmd"
        # Resolve vendor relative to launcher location, not to the staging
        # path where VNMA initially created this script.
        bat_content = (
            "@echo off\r\n"
            'set "VNMA_VENDOR=%~dp0..\\.."\r\n'
            'set "PYTHONPATH=%VNMA_VENDOR%\\.vnma_meta\\site;%VNMA_VENDOR%;%PYTHONPATH%"\r\n'
            f'"{py_exe}" -c "{py_snippet}" %*\r\n'
        )
        bat_file.write_text(bat_content, encoding="utf-8")

        sh_file = self._bin_dir / command_name
        sh_content = (
            "#!/usr/bin/env sh\n"
            'VNMA_VENDOR="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"\n'
            'export PYTHONPATH="$VNMA_VENDOR/.vnma_meta/site:$VNMA_VENDOR:$PYTHONPATH"\n'
            f'exec "{py_exe}" -c "{py_snippet}" "$@"\n'
        )
        sh_file.write_text(sh_content, encoding="utf-8")
        try:
            sh_file.chmod(0o755)
        except OSError:
            pass

    def _create_direct_script_wrapper(self, artifact: ArtifactElement) -> None:
        """Generate launcher for scripts packaged directly in .data/scripts."""
        cmd_name = artifact.relative_path.name
        self._discovered_entry_points[cmd_name] = str(artifact.relative_path)
        self._generate_executable_wrapper(cmd_name, f"{artifact.relative_path.stem}:main")
