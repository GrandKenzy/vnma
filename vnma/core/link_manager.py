"""Management and live zero-copy projection of linked local packages."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Sequence

from vnma.core.config import ConfigHandler
from vnma.core.context import ProjectContext
from vnma.core.models import PackageSpec, normalize_package_name
from vnma.core.path_resolver import PortablePathResolver
from vnma.runtime.bootstrap import BootstrapGenerator
from vnma.visitors.git_visitors import GitignoreVisitor
from vnma.visitors.ide_visitors import PyCharmConfigVisitor, VSCodeConfigVisitor


class LinkManager:
    """Coordinates registration, integrity validation, and path projection of linked packages."""

    def __init__(self, context: ProjectContext) -> None:
        """Initialize link manager with project context."""
        self._context = context

    def get_linked_specs(self) -> list[PackageSpec]:
        """Retrieve all declared dependencies configured with editable=True."""
        config = ConfigHandler.load(self._context.config_path, self._context.pyproject_path)
        return [spec for spec in config.get_all_specs(include_dev=True) if spec.editable and spec.path]

    def verify_links(self) -> list[tuple[str, Path]]:
        """Identify broken links where the target directory no longer exists on disk."""
        broken: list[tuple[str, Path]] = []
        for spec in self.get_linked_specs():
            if not spec.path or not spec.path.is_dir():
                broken.append((spec.name, spec.path or Path("")))
        return broken

    @staticmethod
    def render_broken_links_alert(broken: Sequence[tuple[str, Path]]) -> str:
        """Format an aesthetic alert box detailing missing linked directories."""
        raw_items: list[tuple[str, str, str]] = []
        for name, path in broken:
            raw_items.append((
                f"  * Package: {name}",
                f"    Target Path: {path}",
                f"    Action: Restore directory or run 'vnma unlink {name}'",
            ))

        width = 72
        for n, p, a in raw_items:
            width = max(width, len(n) + 4, len(p) + 4, len(a) + 4)

        border = "+" + "-" * (width - 2) + "+"
        lines: list[str] = [
            border,
            f"| [!] [vnma] Linked dependency broken: directory not found".ljust(width - 1) + "|",
        ]
        for n, p, a in raw_items:
            lines.append(f"| {n}".ljust(width - 1) + "|")
            lines.append(f"| {p}".ljust(width - 1) + "|")
            lines.append(f"| {a}".ljust(width - 1) + "|")
        lines.append(border)
        return "\n".join(lines)

    @staticmethod
    def inspect_target(target_path: Path) -> tuple[str, list[str], list[PackageSpec]]:
        """Inspect target directory for vnma_config.toml or pyproject.toml to extract metadata."""
        resolved = target_path.resolve()
        vnma_cfg = resolved / "vnma_config.toml"
        pyproject_cfg = resolved / "pyproject.toml"

        pkg_name = normalize_package_name(resolved.name)
        module_paths: list[str] = []
        dependencies: list[PackageSpec] = []

        if vnma_cfg.is_file():
            try:
                with vnma_cfg.open("rb") as f:
                    data = tomllib.load(f)
                pkg_data = data.get("package", {})
                # Editable links are addressed by the Python import identity,
                # not by an unrelated distribution label (Gram -> import gram).
                visible_name = (
                    pkg_data.get("package")
                    or pkg_data.get("packname")
                    or pkg_data.get("name")
                )
                if visible_name:
                    pkg_name = normalize_package_name(str(visible_name))
                exports_data = data.get("exports", {})
                declared_modules = exports_data.get("modules", [])
                for mod in declared_modules:
                    cand = resolved / mod
                    if cand.is_dir():
                        if (cand / "__init__.py").is_file():
                            target_cand = cand.parent.resolve()
                        else:
                            target_cand = cand.resolve()
                    elif cand.is_file():
                        target_cand = cand.parent.resolve()
                    else:
                        target_cand = resolved
                    module_paths.append(PortablePathResolver.to_portable_string(target_cand))
                deps_data = data.get("dependencies", {})
                for dep_name, dep_spec in deps_data.items():
                    raw = f"{dep_name}{dep_spec}" if isinstance(dep_spec, str) and dep_spec != "*" else str(dep_name)
                    dependencies.append(PackageSpec.parse(raw))
            except Exception:
                pass
        elif pyproject_cfg.is_file():
            try:
                with pyproject_cfg.open("rb") as f:
                    data = tomllib.load(f)
                proj_data = data.get("project", {})
                if "name" in proj_data:
                    pkg_name = normalize_package_name(str(proj_data["name"]))
                if "dependencies" in proj_data and isinstance(proj_data["dependencies"], list):
                    for req in proj_data["dependencies"]:
                        dependencies.append(PackageSpec.parse(req))
            except Exception:
                pass

        if not module_paths:
            src_dir = resolved / "src"
            if src_dir.is_dir():
                module_paths.append(PortablePathResolver.to_portable_string(src_dir.resolve()))
            else:
                module_paths.append(PortablePathResolver.to_portable_string(resolved))

        return pkg_name, module_paths, dependencies

    def link(self, raw_path: str) -> tuple[PackageSpec, list[PackageSpec]]:
        """Register a local source directory in live zero-copy editable mode."""
        resolved_path = PortablePathResolver.expand(raw_path, base_dir=self._context.project_root)
        if not resolved_path.is_dir():
            raise FileNotFoundError(f"Target directory '{raw_path}' does not exist.")

        pkg_name, module_paths, deps = self.inspect_target(resolved_path)

        from vnma.wheel.uninstaller import WheelUninstaller
        uninstaller = WheelUninstaller(self._context)
        if pkg_name in uninstaller._load_manifest().packages:
            uninstaller.uninstall(pkg_name)

        portable_path = PortablePathResolver.to_portable_string(resolved_path, base_dir=self._context.project_root)
        ConfigHandler.add_dependency(
            self._context.config_path,
            pkg_name,
            {"path": portable_path, "editable": True},
            self._context.pyproject_path,
        )

        self.sync_bootstrap()
        self._sync_environment()

        spec = PackageSpec(name=pkg_name, path=resolved_path, editable=True)
        return spec, deps

    def unlink(self, identifier: str) -> PackageSpec | None:
        """Remove a linked dependency specification and clean up runtime path injection."""
        norm_id = normalize_package_name(identifier)
        resolved_candidate = (
            PortablePathResolver.expand(identifier, base_dir=self._context.project_root)
            if ("/" in identifier or "\\" in identifier or identifier.startswith("~") or "%" in identifier)
            else None
        )

        target_spec: PackageSpec | None = None
        for spec in self.get_linked_specs():
            if spec.name == norm_id:
                target_spec = spec
                break
            if resolved_candidate and spec.path and spec.path.resolve() == resolved_candidate:
                target_spec = spec
                break

        if not target_spec:
            return None

        ConfigHandler.remove_dependency(
            self._context.config_path,
            target_spec.name,
            self._context.pyproject_path,
        )

        self.sync_bootstrap()
        self._sync_environment()
        return target_spec

    def sync_bootstrap(self) -> None:
        """Rebuild __bootstrap__.py aggregating installed packages and all live linked roots."""
        from vnma.wheel.installer import WheelInstaller

        installer = WheelInstaller(self._context)
        manifest = installer._load_manifest()

        all_dll_dirs: set[str] = set()
        all_modules: set[str] = set()
        all_hermetic = True

        for pkg in manifest.packages.values():
            all_dll_dirs.update(pkg.dll_directories)
            all_modules.update(pkg.modules)
            if not pkg.hermetic:
                all_hermetic = False

        for linked in self.get_linked_specs():
            if linked.path and linked.path.is_dir():
                _, module_paths, _ = self.inspect_target(linked.path)
                all_modules.update(module_paths)

        generator = BootstrapGenerator(self._context.vendor_path)
        generator.generate(
            dll_subdirectories=sorted(all_dll_dirs),
            hermetic=all_hermetic,
            extra_paths=sorted(all_modules),
        )

    def _sync_environment(self) -> None:
        """Run IDE visitors only after a staged workspace is committed."""
        if getattr(self._context, "_transaction_active", False):
            return
        self._context.accept(GitignoreVisitor())
        self._context.accept(VSCodeConfigVisitor())
        self._context.accept(PyCharmConfigVisitor())
