"""Coordinator for installing wheels, managing metadata, and invoking visitors."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from vnma.core.config import ConfigHandler
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
        active_extras: Sequence[str] = (),
    ) -> InstalledPackageRecord:
        """Extract wheel, run artifact analysis visitors, and update manifests."""
        self._context.ensure_directories()
        norm_name = normalize_package_name(package_name)

        manifest = self._load_manifest()
        previous_record = manifest.packages.get(norm_name)
        previous_files: set[str] = (
            {f.relative_path for f in previous_record.files} if previous_record else set()
        )

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

        new_files: set[str] = {f.relative_path for f in record_visitor.installed_files}
        obsolete_files = previous_files - new_files

        if obsolete_files:
            claimed_by_others: set[str] = {
                f.relative_path
                for other_name, other_pkg in manifest.packages.items()
                if other_name != norm_name
                for f in other_pkg.files
            }
            vendor_root = self._context.vendor_path
            for rel in obsolete_files:
                if rel in claimed_by_others:
                    continue
                target = vendor_root / rel
                if target.is_file():
                    target.unlink()
                    self._prune_empty_parents(target.parent, vendor_root)

        for warning in binary_visitor.collisions:
            print(f"[vnma] WARNING: {warning}")

        if package_config is None:
            config = ConfigHandler.load(self._context.config_path, self._context.pyproject_path)
            override_data = config.package_overrides.get(norm_name)
            if override_data:
                package_config = PackageConfig.from_dict({
                    "package": {
                        "name": norm_name,
                        "version": version,
                        "type": override_data.get("package_type", "native" if "dll_directories" in override_data else "pure-python"),
                    },
                    "runtime": {
                        "dll_directories": override_data.get("dll_directories", []),
                        "hermetic": override_data.get("hermetic", True),
                    },
                    "exports": {
                        "entry_points": override_data.get("entry_points", {}),
                        "modules": override_data.get("modules", []),
                    },
                })

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

        hasher = hashlib.sha256()
        with wheel_path.open("rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        wheel_sha = hasher.hexdigest()

        package_record = InstalledPackageRecord(
            name=norm_name,
            version=version,
            files=record_visitor.installed_files,
            dll_directories=dll_dirs,
            entry_points=merged_entry_points,
            has_native_binaries=binary_visitor.has_binaries if not package_config else (package_config.package_type == "native"),
            active_extras=list(active_extras),
            wheel_filename=wheel_path.name,
            wheel_sha256=wheel_sha,
            hermetic=package_config.hermetic if package_config else True,
            modules=package_config.modules if package_config else [],
        )

        self._update_manifest(package_record)
        self._record_python_version()
        self._sync_bootstrap()
        self._sync_environment()


        return package_record

    def _prune_empty_parents(self, directory: Path, stop_at: Path) -> None:
        """Recursively delete empty directories up to the vendor root."""
        current = directory
        while current != stop_at and current.is_relative_to(stop_at):
            try:
                current.rmdir()
                current = current.parent
            except OSError:
                break

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
        """Regenerate __bootstrap__.py with all aggregated DLL search paths and extra module exports."""
        manifest = self._load_manifest()
        all_dll_dirs: set[str] = set()
        all_modules: set[str] = set()
        all_hermetic = True

        for pkg in manifest.packages.values():
            all_dll_dirs.update(pkg.dll_directories)
            all_modules.update(pkg.modules)
            if not pkg.hermetic:
                all_hermetic = False

        from vnma.core.link_manager import LinkManager
        for linked in LinkManager(self._context).get_linked_specs():
            if linked.path and linked.path.is_dir():
                _, module_paths, _ = LinkManager.inspect_target(linked.path)
                all_modules.update(module_paths)

        generator = BootstrapGenerator(self._context.vendor_path)
        generator.generate(
            dll_subdirectories=sorted(all_dll_dirs),
            hermetic=all_hermetic,
            extra_paths=sorted(all_modules),
        )


    def _sync_environment(self) -> None:
        """Run project visitors for Git and IDE configuration."""
        self._context.accept(GitignoreVisitor())
        self._context.accept(VSCodeConfigVisitor())
        self._context.accept(PyCharmConfigVisitor())
