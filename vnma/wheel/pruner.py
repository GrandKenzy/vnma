"""Deterministic detection and removal of orphaned vendored packages."""

from __future__ import annotations

import json
import re
from collections import deque
from pathlib import Path
from typing import Sequence

from vnma.core.config import ConfigHandler
from vnma.core.context import ProjectContext
from vnma.core.lockfile import LockfileHandler
from vnma.core.models import PackageSpec, VnmaManifest, normalize_package_name
from vnma.pypi.resolver import WheelResolver
from vnma.wheel.uninstaller import WheelUninstaller

_METADATA_REGEX = re.compile(r"^([^/]+)\.dist-info/METADATA$", re.IGNORECASE)


class OrphanPruner:
    """Calculates transitive reachability from declared dependencies and purges orphaned packages."""

    def __init__(
        self,
        context: ProjectContext,
        uninstaller: WheelUninstaller | None = None,
    ) -> None:
        """Initialize pruner with project context and uninstaller."""
        self._context = context
        self._uninstaller = uninstaller or WheelUninstaller(context)

    def compute_reachable_packages(
        self,
        root_specs: Sequence[PackageSpec],
        manifest: VnmaManifest,
    ) -> set[str]:
        """Traverse dependency graph from root specifications using installed package metadata."""
        adjacency: dict[str, set[str]] = {pkg: set() for pkg in manifest.packages}
        vendor_path = self._context.vendor_path

        for pkg_name, record in manifest.packages.items():
            metadata_file: Path | None = None
            for file_entry in record.files:
                norm_rel = file_entry.relative_path.replace("\\", "/")
                if _METADATA_REGEX.match(norm_rel):
                    candidate = vendor_path / file_entry.relative_path
                    if candidate.is_file():
                        metadata_file = candidate
                        break

            if not metadata_file:
                continue

            try:
                content = metadata_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            for line in content.splitlines():
                if not line.startswith("Requires-Dist:"):
                    continue
                raw_req = line[len("Requires-Dist:") :].strip()
                if not WheelResolver._evaluate_marker(raw_req, ()):
                    continue
                dep_spec = PackageSpec.parse(raw_req)
                norm_dep = normalize_package_name(dep_spec.name)
                if norm_dep in manifest.packages:
                    adjacency[pkg_name].add(norm_dep)

        reachable: set[str] = set()
        queue: deque[str] = deque()

        for spec in root_specs:
            norm_root = normalize_package_name(spec.name)
            if norm_root in manifest.packages and norm_root not in reachable:
                reachable.add(norm_root)
                queue.append(norm_root)

        while queue:
            current = queue.popleft()
            for neighbor in adjacency.get(current, ()):
                if neighbor not in reachable:
                    reachable.add(neighbor)
                    queue.append(neighbor)

        return reachable

    def find_orphans(self) -> list[str]:
        """Identify installed packages that are not reachable from project configuration."""
        if not self._context.manifest_path.is_file():
            return []

        try:
            raw_manifest = json.loads(self._context.manifest_path.read_text(encoding="utf-8"))
            manifest = VnmaManifest.from_dict(raw_manifest)
        except Exception:
            return []

        config = ConfigHandler.load(self._context.config_path, self._context.pyproject_path)
        root_specs = config.get_all_specs()

        reachable = self.compute_reachable_packages(root_specs, manifest)
        installed = set(manifest.packages.keys())
        orphans = sorted(installed - reachable)
        return orphans

    def prune(self, dry_run: bool = False) -> list[str]:
        """Purge orphaned packages and synchronize lockfile."""
        orphans = self.find_orphans()
        if dry_run or not orphans:
            return orphans

        for pkg in orphans:
            self._uninstaller.uninstall(pkg)

        LockfileHandler.update(self._context)
        return orphans
