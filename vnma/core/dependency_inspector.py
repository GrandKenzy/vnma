"""Extracts package metadata, module paths, and declared dependencies from source directories."""

from __future__ import annotations

import tomllib
from pathlib import Path

from vnma.core.models import PackageSpec, normalize_package_name
from vnma.core.path_resolver import PortablePathResolver


class DependencyInspector:
    """Discovers project manifests and extracts dependencies from local source directories."""

    @classmethod
    def inspect(cls, target_path: Path) -> tuple[str, list[str], list[PackageSpec]]:
        """Inspect target directory for vnma.toml, vnma_config.toml, or pyproject.toml.

        Returns:
            tuple of (pkg_name, module_paths, dependencies)
        """
        resolved = target_path.resolve()
        vnma_toml = resolved / "vnma.toml"
        vnma_cfg = resolved / "vnma_config.toml"
        pyproject_cfg = resolved / "pyproject.toml"

        pkg_name = normalize_package_name(resolved.name)
        module_paths: list[str] = []
        dependencies: list[PackageSpec] = []

        if vnma_toml.is_file():
            try:
                from vnma.core.config import ConfigHandler
                config = ConfigHandler.load(vnma_toml)
                if config.project_name:
                    pkg_name = normalize_package_name(config.project_name)
                dependencies.extend(config.get_all_specs(include_dev=False))
            except Exception:
                pass

        if vnma_cfg.is_file():
            try:
                from vnma.core.package_config import PackageConfig
                pkg_cfg = PackageConfig.load_from_dir(resolved)
                if pkg_cfg:
                    # Visible import identity takes precedence (e.g. distribution "my-lib-framework" -> import "my_lib")
                    import_or_name = pkg_cfg.import_name or pkg_cfg.name
                    if import_or_name:
                        pkg_name = normalize_package_name(import_or_name)
                    # Add declared dependencies if not already extracted from vnma.toml
                    if not dependencies:
                        dependencies.extend(pkg_cfg.get_specs(base_dir=resolved))
                    for mod in pkg_cfg.modules:
                        cand = resolved / mod
                        if cand.is_dir():
                            target_cand = cand.parent.resolve() if (cand / "__init__.py").is_file() else cand.resolve()
                        elif cand.is_file():
                            target_cand = cand.parent.resolve()
                        else:
                            target_cand = resolved
                        module_paths.append(PortablePathResolver.to_portable_string(target_cand))
            except Exception:
                pass

        if not dependencies and pyproject_cfg.is_file():
            try:
                with pyproject_cfg.open("rb") as f:
                    data = tomllib.load(f)
                proj_data = data.get("project", {})
                if "name" in proj_data:
                    pkg_name = normalize_package_name(str(proj_data["name"]))
                if "dependencies" in proj_data and isinstance(proj_data["dependencies"], list):
                    for req in proj_data["dependencies"]:
                        dependencies.append(PackageSpec.parse(req))
                tool_deps = data.get("tool", {}).get("vnma", {}).get("dependencies", {})
                if tool_deps:
                    from vnma.core.config import VnmaConfig
                    temp_cfg = VnmaConfig(dependencies=tool_deps, base_dir=resolved)
                    dependencies.extend(temp_cfg.get_all_specs(include_dev=False))
            except Exception:
                pass

        if not module_paths:
            src_dir = resolved / "src"
            if src_dir.is_dir():
                module_paths.append(PortablePathResolver.to_portable_string(src_dir.resolve()))
            else:
                module_paths.append(PortablePathResolver.to_portable_string(resolved))

        return pkg_name, module_paths, dependencies
