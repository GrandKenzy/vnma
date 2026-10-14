"""Lockfile generation, synchronization, and atomic persistence for reproducible builds."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vnma.core.config import ConfigHandler
from vnma.core.context import ProjectContext
from vnma.core.models import VnmaManifest, normalize_package_name


class LockfileHandler:
    """Manages the creation and atomic updating of vnma.lock."""

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
    def update(cls, context: ProjectContext) -> Path:
        """Atomically synchronize vnma.lock from manifest.json and vnma.toml definitions."""
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
                "has_native_binaries": record.has_native_binaries,
                "dll_directories": record.dll_directories,
                "files_count": len(record.files),
            }

        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        lock_payload = {
            "lockfile_version": cls.LOCKFILE_VERSION,
            "python_version": py_ver,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "packages": locked_packages,
        }

        tmp_path = context.lock_path.with_suffix(".lock.tmp")
        tmp_path.write_text(
            json.dumps(lock_payload, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(context.lock_path)
        return context.lock_path
