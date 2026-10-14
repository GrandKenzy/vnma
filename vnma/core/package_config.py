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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PackageConfig:
        """Hydrate package configuration from parsed dictionary."""
        pkg_data = data.get("package", {})
        runtime_data = data.get("runtime", {})
        exports_data = data.get("exports", {})

        raw_name = pkg_data.get("name", "")
        return cls(
            name=normalize_package_name(raw_name) if raw_name else "",
            version=str(pkg_data.get("version", "")),
            package_type=pkg_data.get("type", "pure-python"),
            dll_directories=list(runtime_data.get("dll_directories", [])),
            entry_points=dict(exports_data.get("entry_points", {})),
            modules=list(exports_data.get("modules", [])),
            hermetic=bool(runtime_data.get("hermetic", True)),
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
