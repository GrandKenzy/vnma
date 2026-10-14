"""Project workspace detection, directory routing, and visitor acceptance."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vnma.visitors.base import ProjectVisitor, VisitableProject

if TYPE_CHECKING:
    pass


class ProjectContext(VisitableProject):
    """Encapsulates project paths, layout resolution, and visitor execution."""

    def __init__(self, start_path: Path | None = None) -> None:
        """Initialize project context from a specified or current directory."""
        self.project_root = self._discover_project_root(start_path or Path.cwd())
        self.vendor_name = self._determine_vendor_dir_name()

    def accept(self, visitor: ProjectVisitor) -> Any:
        """Accept a project-level visitor for configuration or validation."""
        return visitor.visit_project(self)

    @property
    def vendor_path(self) -> Path:
        """Target directory where third-party packages are vendored."""
        return self.project_root / self.vendor_name

    @property
    def meta_path(self) -> Path:
        """Internal metadata directory within the vendor root."""
        return self.vendor_path / ".vnma_meta"

    @property
    def manifest_path(self) -> Path:
        """Persistent JSON file tracking installed packages and hashes."""
        return self.meta_path / "manifest.json"

    @property
    def bin_path(self) -> Path:
        """Directory housing generated executable script wrappers."""
        return self.meta_path / ".bin"

    @property
    def bootstrap_path(self) -> Path:
        """Generated runtime script injecting sys.path and DLL directories."""
        return self.vendor_path / "__bootstrap__.py"

    @property
    def config_path(self) -> Path:
        """Primary project configuration file path."""
        return self.project_root / "vnma.toml"

    @property
    def pyproject_path(self) -> Path:
        """Alternative PEP 518 configuration file path."""
        return self.project_root / "pyproject.toml"

    @property
    def lock_path(self) -> Path:
        """Locked dependency resolution manifest."""
        return self.project_root / "vnma.lock"

    @property
    def gitignore_path(self) -> Path:
        """Project root git ignore file."""
        return self.project_root / ".gitignore"

    def ensure_directories(self) -> None:
        """Ensure necessary vendor and metadata directories exist."""
        self.vendor_path.mkdir(parents=True, exist_ok=True)
        self.meta_path.mkdir(parents=True, exist_ok=True)
        self.bin_path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _discover_project_root(start: Path) -> Path:
        """Traverse upwards to identify the root of the project workspace."""
        current = start.resolve()
        for parent in (current, *current.parents):
            if (parent / "vnma.toml").exists() or (parent / "pyproject.toml").exists():
                return parent
            if (parent / ".git").exists():
                return parent
        return current

    def _determine_vendor_dir_name(self) -> str:
        """Select vendor directory name avoiding collisions with external vendor folders."""
        default_vendor = self.project_root / "vendor"
        meta_marker = default_vendor / ".vnma_meta"

        if not default_vendor.exists():
            return "vendor"

        if meta_marker.exists():
            return "vendor"

        try:
            if not any(default_vendor.iterdir()):
                return "vendor"
        except OSError:
            pass

        return "vendor_vnma"
