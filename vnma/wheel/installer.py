"""Coordinator for installing wheels, managing metadata, and invoking visitors."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from vnma.core.context import ProjectContext
from vnma.core.models import InstalledPackageRecord, VnmaManifest, normalize_package_name
from vnma.core.package_config import PackageConfig
from vnma.runtime.bootstrap import BootstrapGenerator
from vnma.visitors.artifact_visitors import (
    BinaryDetectorVisitor,
    RecordCollectorVisitor,
    ScriptWrapperVisitor,
)
from vnma.visitors.git_visitors import GitignoreVisitor
from vnma.visitors.ide_visitors import PyCharmConfigVisitor, VSCodeConfigVisitor
from vnma.wheel.archive import WheelArchive


class WheelInstaller:
    """Installs wheel archives into project vendor tree and synchronizes environments."""

    def __init__(self, context: ProjectContext) -> None:
        """Initialize installer with workspace context."""
        self._context = context

    def install(
        self,
        wheel_path: Path,
        package_name: str,
        version: str,
        package_config: PackageConfig | None = None,
    ) -> InstalledPackageRecord:
        """Extract wheel, run artifact analysis visitors, and update manifests."""
        self._context.ensure_directories()
        norm_name = normalize_package_name(package_name)

        manifest = self._load_manifest()
        existing_dlls: dict[str, tuple[str, str]] = {}
        for pkg_name, pkg in manifest.packages.items():
            if pkg_name == norm_name:
                continue
            for f in pkg.files:
                if f.relative_path.lower().endswith((".dll", ".so", ".dylib")):
                    dll_fname = Path(f.relative_path).name.lower()
                    existing_dlls[dll_fname] = (f.sha256, pkg_name)

        record_visitor = RecordCollectorVisitor()
        binary_visitor = BinaryDetectorVisitor(existing_dlls)
        script_visitor = ScriptWrapperVisitor(self._context.bin_path, self._context.vendor_path)

        archive = WheelArchive(wheel_path)
        archive.extract_and_visit(
            self._context.vendor_path,
            visitors=[record_visitor, binary_visitor, script_visitor],
        )

        for warning in binary_visitor.collisions:
            print(f"[vnma] WARNING: {warning}")

        dll_dirs = (
            package_config.dll_directories
            if package_config and package_config.dll_directories
            else binary_visitor.dll_directories
        )

        merged_entry_points = dict(script_visitor.entry_points)
        if package_config and package_config.entry_points:
            for cmd_name, target in package_config.entry_points.items():
                merged_entry_points[cmd_name] = target
                script_visitor._generate_executable_wrapper(cmd_name, target)

        package_record = InstalledPackageRecord(
            name=norm_name,
            version=version,
            files=record_visitor.installed_files,
            dll_directories=dll_dirs,
            entry_points=merged_entry_points,
            has_native_binaries=binary_visitor.has_binaries if not package_config else (package_config.package_type == "native"),
        )

        self._update_manifest(package_record)
        self._record_python_version()
        self._sync_bootstrap()
        self._sync_environment()

        return package_record

    def _update_manifest(self, record: InstalledPackageRecord) -> None:
        """Atomically persist installed package record into project manifest."""
        manifest = self._load_manifest()
        manifest.packages[record.name] = record
        manifest.python_version = (
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        )
        tmp_path = self._context.manifest_path.with_suffix(".json.tmp")
        tmp_path.write_text(
            json.dumps(manifest.to_dict(), indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(self._context.manifest_path)

    def _load_manifest(self) -> VnmaManifest:
        """Load manifest from disk or return a clean default manifest."""
        if self._context.manifest_path.is_file():
            try:
                data = json.loads(self._context.manifest_path.read_text(encoding="utf-8"))
                return VnmaManifest.from_dict(data)
            except (json.JSONDecodeError, KeyError):
                pass
        return VnmaManifest()

    def _record_python_version(self) -> None:
        """Persist host Python version to detect future runtime version mismatches."""
        ver_file = self._context.meta_path / "python_version"
        ver_str = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        ver_file.write_text(ver_str, encoding="utf-8")

    def _sync_bootstrap(self) -> None:
        """Regenerate __bootstrap__.py with all aggregated DLL search paths."""
        manifest = self._load_manifest()
        all_dll_dirs: set[str] = set()
        for pkg in manifest.packages.values():
            all_dll_dirs.update(pkg.dll_directories)

        generator = BootstrapGenerator(self._context.vendor_path)
        generator.generate(sorted(all_dll_dirs))

    def _sync_environment(self) -> None:
        """Run project visitors for Git and IDE configuration."""
        self._context.accept(GitignoreVisitor())
        self._context.accept(VSCodeConfigVisitor())
        self._context.accept(PyCharmConfigVisitor())
