"""Clean removal of installed packages, metadata, and associated launchers."""

from __future__ import annotations

import json
from pathlib import Path

from vnma.core.context import ProjectContext
from vnma.core.models import VnmaManifest, normalize_package_name
from vnma.runtime.bootstrap import BootstrapGenerator


class WheelUninstaller:
    """Removes installed package files, restores clean directories, and updates metadata."""

    def __init__(self, context: ProjectContext) -> None:
        """Initialize uninstaller with project context."""
        self._context = context

    def uninstall(self, package_name: str) -> bool:
        """Purge all files tracked by manifest for the specified package preserving shared files."""
        norm_name = normalize_package_name(package_name)
        manifest = self._load_manifest()

        if norm_name not in manifest.packages:
            return False

        record = manifest.packages[norm_name]
        vendor_root = self._context.vendor_path

        shared_files: set[str] = {
            f.relative_path
            for other_name, other_pkg in manifest.packages.items()
            if other_name != norm_name
            for f in other_pkg.files
        }

        for file_entry in record.files:
            if file_entry.relative_path in shared_files:
                continue
            target_path = vendor_root / file_entry.relative_path
            if target_path.is_file():
                target_path.unlink()
                self._prune_empty_directories(target_path.parent, vendor_root)

        bin_dir = self._context.bin_path
        for cmd_name in record.entry_points:
            for ext in (".cmd", ".bat", ""):
                launcher = bin_dir / f"{cmd_name}{ext}"
                if launcher.is_file():
                    launcher.unlink()

        del manifest.packages[norm_name]
        tmp_path = self._context.manifest_path.with_suffix(".json.tmp")
        tmp_path.write_text(
            json.dumps(manifest.to_dict(), indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(self._context.manifest_path)

        all_dll_dirs: set[str] = set()
        for pkg in manifest.packages.values():
            all_dll_dirs.update(pkg.dll_directories)

        generator = BootstrapGenerator(self._context.vendor_path)
        generator.generate(sorted(all_dll_dirs))

        return True

    def _load_manifest(self) -> VnmaManifest:
        """Load project manifest or return empty manifest instance."""
        if self._context.manifest_path.is_file():
            try:
                data = json.loads(self._context.manifest_path.read_text(encoding="utf-8"))
                return VnmaManifest.from_dict(data)
            except (json.JSONDecodeError, KeyError):
                pass
        return VnmaManifest()

    @staticmethod
    def _prune_empty_directories(current_dir: Path, boundary_root: Path) -> None:
        """Traverse upwards deleting directories that have become completely empty."""
        try:
            curr = current_dir.resolve()
            boundary = boundary_root.resolve()
            while curr != boundary and boundary in curr.parents:
                if not any(curr.iterdir()):
                    curr.rmdir()
                    curr = curr.parent
                else:
                    break
        except OSError:
            pass
