"""Lockfile generation, synchronization, and atomic persistence for reproducible builds."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from vnma.core.config import ConfigHandler
from vnma.core.context import ProjectContext
from vnma.core.models import VnmaManifest, normalize_package_name
from vnma.core.path_resolver import PortablePathResolver


class LockfileHandler:
    """Manages the creation, verification, and atomic updating of vnma.lock."""

    LOCKFILE_VERSION = "1.0"

    @classmethod
    def load(cls, lock_path: Path) -> dict[str, Any] | None:
        """Load lockfile dictionary if file exists."""
        if not lock_path.is_file():
            return None
        try:
            return json.loads(lock_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    @classmethod
    def is_synchronized(cls, context: ProjectContext, config: VnmaConfig) -> bool:
        """Verify that vnma.lock satisfies all root dependencies declared in configuration."""
        lock_data = cls.load(context.lock_path)
        if not lock_data:
            return False

        packages = lock_data.get("packages", {})
        all_specs = config.get_all_specs()
        if not packages and all_specs:
            return False

        for spec in all_specs:
            if spec.name not in packages:
                return False
            pkg_data = packages[spec.name]
            if spec.editable:
                if not pkg_data.get("editable") or pkg_data.get("source") != "editable":
                    return False
            elif spec.path:
                if pkg_data.get("source") != "local":
                    return False
            elif spec.git_url:
                if pkg_data.get("source") != "git" or pkg_data.get("git_url") != spec.git_url:
                    return False
            else:
                if pkg_data.get("source") != "pypi":
                    return False
                if not spec.matches(pkg_data.get("version", "")):
                    return False

        return True

    @classmethod
    def is_vendor_synchronized(cls, context: ProjectContext, lock_data: dict[str, Any]) -> bool:
        """Check whether current vendor tree matches exact locked package versions and hashes."""
        if not context.manifest_path.is_file():
            return False

        try:
            raw = json.loads(context.manifest_path.read_text(encoding="utf-8"))
            manifest = VnmaManifest.from_dict(raw)
        except Exception:
            return False

        locked_pkgs = lock_data.get("packages", {})
        non_editable_locked = {
            name: info for name, info in locked_pkgs.items()
            if not info.get("editable") and info.get("source") != "editable"
        }
        if set(manifest.packages.keys()) != set(non_editable_locked.keys()):
            return False

        for name, locked_info in non_editable_locked.items():
            record = manifest.packages[name]
            if record.version != locked_info.get("version"):
                return False
            expected_sha = locked_info.get("sha256")
            if expected_sha and record.wheel_sha256 and record.wheel_sha256 != expected_sha:
                return False

        return True

    @classmethod
    def update(cls, context: ProjectContext) -> Path:
        """Atomically synchronize vnma.lock from manifest.json and declared specifications."""
        manifest_data = VnmaManifest()
        if context.manifest_path.is_file():
            try:
                raw_manifest = json.loads(context.manifest_path.read_text(encoding="utf-8"))
                manifest_data = VnmaManifest.from_dict(raw_manifest)
            except Exception:
                pass

        config = ConfigHandler.load(context.config_path, context.pyproject_path)
        specs_by_name = {spec.name: spec for spec in config.get_all_specs()}

        locked_packages: dict[str, dict[str, Any]] = {}
        for pkg_name, record in sorted(manifest_data.packages.items()):
            norm_name = normalize_package_name(pkg_name)
            spec = specs_by_name.get(norm_name)

            source = "pypi"
            source_meta: dict[str, Any] = {}

            if spec and spec.path:
                source = "local"
                source_meta["path"] = str(spec.path.as_posix())
            elif spec and spec.git_url:
                source = "git"
                source_meta["git_url"] = spec.git_url
                source_meta["git_ref"] = spec.git_ref or "main"

            locked_packages[norm_name] = {
                "version": record.version,
                "source": source,
                **source_meta,
                "wheel_filename": record.wheel_filename,
                "sha256": record.wheel_sha256,
                "active_extras": sorted(record.active_extras),
                "has_native_binaries": record.has_native_binaries,
                "dll_directories": record.dll_directories,
                "files_count": len(record.files),
            }

        for spec in config.get_all_specs():
            if spec.editable and spec.path:
                portable = PortablePathResolver.to_portable_string(spec.path, context.project_root)
                locked_packages[spec.name] = {
                    "source": "editable",
                    "path": portable,
                    "editable": True,
                }

        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        lock_payload = {
            "lockfile_version": cls.LOCKFILE_VERSION,
            "python_version": py_ver,
            "packages": locked_packages,
        }

        tmp_path = context.lock_path.with_suffix(".lock.tmp")
        tmp_path.write_text(
            json.dumps(lock_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        tmp_path.replace(context.lock_path)
        return context.lock_path

