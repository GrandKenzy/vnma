"""Package-level configuration parser for vnma_config.toml and local overrides."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vnma.core.models import normalize_package_name


@dataclass(slots=True)
class PackageConfig:
    """Explicit package metadata to override or bypass runtime heuristic discovery."""

    name: str
    version: str = ""
    package_type: str = "pure-python"
    dll_directories: list[str] = field(default_factory=list)
    entry_points: dict[str, str] = field(default_factory=dict)
    modules: list[str] = field(default_factory=list)
    hermetic: bool = True
    import_name: str = ""
    dependencies: dict[str, Any] = field(default_factory=dict)

    def get_specs(self, base_dir: Path | None = None) -> list[Any]:
        """Convert declared dependencies into PackageSpec instances."""
        from vnma.core.models import PackageSpec
        from vnma.core.path_resolver import PortablePathResolver

        specs: list[PackageSpec] = []
        for name, value in self.dependencies.items():
            norm_name = normalize_package_name(name)
            if isinstance(value, dict):
                if "path" in value:
                    specs.append(
                        PackageSpec(
                            name=norm_name,
                            path=PortablePathResolver.expand(value["path"], base_dir=base_dir),
                            editable=bool(value.get("editable", False)),
                        )
                    )
                elif "git" in value:
                    ref = value.get("branch") or value.get("tag") or value.get("commit") or "main"
                    specs.append(
                        PackageSpec(
                            name=norm_name,
                            git_url=value["git"],
                            git_ref=ref,
                        )
                    )
            elif isinstance(value, str):
                raw = f"{norm_name}{value}" if value and value != "*" else norm_name
                specs.append(PackageSpec.parse(raw))
        return specs

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PackageConfig:
        """Hydrate package configuration from parsed dictionary."""
        pkg_data = data.get("package", {})
        runtime_data = data.get("runtime", {})
        exports_data = data.get("exports", {})
        deps_data = data.get("dependencies", {})

        raw_name = pkg_data.get("name", "")
        # `package` is the official import name; `packname` is the legacy
        # field used by existing Gram manifests and remains supported.
        import_name = str(pkg_data.get("package") or pkg_data.get("packname") or "")
        if import_name and not all(part.isidentifier() for part in import_name.split(".")):
            raise ValueError(f"Invalid importable Python package name: {import_name!r}")
        return cls(
            name=normalize_package_name(raw_name) if raw_name else "",
            import_name=import_name,
            version=str(pkg_data.get("version", "")),
            package_type=pkg_data.get("type", "pure-python"),
            dll_directories=list(runtime_data.get("dll_directories", [])),
            entry_points=dict(exports_data.get("entry_points", {})),
            modules=list(exports_data.get("modules", [])),
            hermetic=bool(runtime_data.get("hermetic", True)),
            dependencies=dict(deps_data),
        )

    @classmethod
    def load_from_dir(cls, directory: Path) -> PackageConfig | None:
        """Inspect directory for vnma_config.toml and return configuration if present."""
        config_path = directory / "vnma_config.toml"
        if not config_path.is_file():
            return None

        try:
            with config_path.open("rb") as f:
                data = tomllib.load(f)
            return cls.from_dict(data)
        except Exception:
            return None
