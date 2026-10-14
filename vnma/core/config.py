"""Configuration loader and serializer for vnma.toml and pyproject.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vnma.core.models import PackageSpec, normalize_package_name


@dataclass(slots=True)
class VnmaConfig:
    """In-memory representation of project vendor configuration."""

    project_name: str = "project"
    version: str = "0.1.0"
    dependencies: dict[str, Any] = field(default_factory=dict)
    dev_dependencies: dict[str, Any] = field(default_factory=dict)
    vendor_dir: str = "vendor"
    ide_integration: list[str] = field(
        default_factory=lambda: ["vscode", "pycharm"]
    )
    package_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)

    def get_all_specs(self) -> list[PackageSpec]:
        """Convert declared dependency definitions into PackageSpec instances."""
        specs: list[PackageSpec] = []
        for name, value in self.dependencies.items():
            norm_name = normalize_package_name(name)
            if isinstance(value, dict):
                if "path" in value:
                    specs.append(
                        PackageSpec(
                            name=norm_name,
                            path=Path(value["path"]).resolve(),
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


class ConfigHandler:
    """Reads and writes TOML project configuration files."""

    @staticmethod
    def load(config_path: Path, pyproject_path: Path | None = None) -> VnmaConfig:
        """Parse configuration from vnma.toml or fallback to pyproject.toml."""
        if config_path.exists():
            with config_path.open("rb") as f:
                data = tomllib.load(f)
            return ConfigHandler._parse_vnma_data(data)

        if pyproject_path and pyproject_path.exists():
            with pyproject_path.open("rb") as f:
                data = tomllib.load(f)
            tool_data = data.get("tool", {}).get("vnma", {})
            project_data = data.get("project", {})
            deps = dict(tool_data.get("dependencies", {}))
            if not deps and "dependencies" in project_data and isinstance(project_data["dependencies"], list):
                for req in project_data["dependencies"]:
                    parsed = PackageSpec.parse(req)
                    deps[parsed.name] = parsed.specifier or "*"
            return VnmaConfig(
                project_name=project_data.get("name", "project"),
                version=project_data.get("version", "0.1.0"),
                dependencies=deps,
                dev_dependencies=tool_data.get("dev-dependencies", {}),
                vendor_dir=tool_data.get("vendor_dir", "vendor"),
                ide_integration=tool_data.get("ide_integration", ["vscode", "pycharm"]),
            )

        return VnmaConfig()

    @staticmethod
    def save(config_path: Path, config: VnmaConfig) -> None:
        """Serialize configuration directly to TOML file format."""
        lines: list[str] = [
            "[project]",
            f'name = "{config.project_name}"',
            f'version = "{config.version}"',
            "",
            "[dependencies]",
        ]
        for name, req in sorted(config.dependencies.items()):
            if isinstance(req, dict):
                formatted_inner = ", ".join(f'{k} = "{v}"' for k, v in req.items())
                lines.append(f"{name} = {{ {formatted_inner} }}")
            else:
                lines.append(f'{name} = "{req}"')

        lines.extend([
            "",
            "[dev-dependencies]",
        ])
        for name, req in sorted(config.dev_dependencies.items()):
            if isinstance(req, dict):
                formatted_inner = ", ".join(f'{k} = "{v}"' for k, v in req.items())
                lines.append(f"{name} = {{ {formatted_inner} }}")
            else:
                lines.append(f'{name} = "{req}"')

        lines.extend([
            "",
            "[tool.vnma]",
            f'vendor_dir = "{config.vendor_dir}"',
            f'ide_integration = {config.ide_integration!r}'.replace("'", '"'),
        ])

        if config.package_overrides:
            lines.append("")
            for pkg_name, overrides in sorted(config.package_overrides.items()):
                lines.append(f"[package.{pkg_name}]")
                for k, v in overrides.items():
                    if isinstance(v, list):
                        lines.append(f'{k} = {v!r}'.replace("'", '"'))
                    elif isinstance(v, dict):
                        lines.append(f'{k} = {v!r}'.replace("'", '"'))
                    else:
                        lines.append(f'{k} = "{v}"')

        lines.append("")
        config_path.write_text("\n".join(lines), encoding="utf-8")

    @staticmethod
    def _format_entry_line(name: str, value: Any) -> str:
        """Format dependency key and value for TOML persistence."""
        if isinstance(value, dict):
            formatted_inner = ", ".join(f'{k} = "{v}"' for k, v in value.items())
            return f"{name} = {{ {formatted_inner} }}"
        return f'{name} = "{value}"'

    @staticmethod
    def _add_dependency_pyproject(pyproject_path: Path, name: str, value: Any) -> None:
        """Add or update a dependency inside [tool.vnma.dependencies] in pyproject.toml."""
        norm_name = normalize_package_name(name)
        entry_line = ConfigHandler._format_entry_line(norm_name, value)
        content = pyproject_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        section_header = "[tool.vnma.dependencies]"
        if section_header in content:
            new_lines: list[str] = []
            in_section = False
            replaced = False
            for line in lines:
                stripped = line.strip()
                if stripped == section_header:
                    in_section = True
                    new_lines.append(line)
                    continue
                if in_section:
                    if stripped.startswith("[") and stripped.endswith("]"):
                        if not replaced:
                            new_lines.append(entry_line)
                            replaced = True
                        in_section = False
                        new_lines.append(line)
                        continue
                    key_part = stripped.split("=")[0].strip().strip('"').strip("'")
                    if normalize_package_name(key_part) == norm_name:
                        new_lines.append(entry_line)
                        replaced = True
                        continue
                new_lines.append(line)
            if in_section and not replaced:
                new_lines.append(entry_line)
            pyproject_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        else:
            block = f"\n{section_header}\n{entry_line}\n"
            pyproject_path.write_text(content.rstrip() + block, encoding="utf-8")

    @staticmethod
    def _remove_dependency_pyproject(pyproject_path: Path, name: str) -> None:
        """Remove a dependency from [tool.vnma.dependencies] in pyproject.toml."""
        norm_name = normalize_package_name(name)
        content = pyproject_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        new_lines: list[str] = []
        in_section = False
        for line in lines:
            stripped = line.strip()
            if stripped == "[tool.vnma.dependencies]":
                in_section = True
                new_lines.append(line)
                continue
            if in_section:
                if stripped.startswith("[") and stripped.endswith("]"):
                    in_section = False
                    new_lines.append(line)
                    continue
                key_part = stripped.split("=")[0].strip().strip('"').strip("'")
                if normalize_package_name(key_part) == norm_name:
                    continue
            new_lines.append(line)
        pyproject_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    @staticmethod
    def add_dependency(
        config_path: Path,
        name: str,
        value: Any = "*",
        pyproject_path: Path | None = None,
    ) -> None:
        """Add or update a dependency entry inside vnma.toml or pyproject.toml."""
        if not config_path.exists() and pyproject_path and pyproject_path.exists():
            ConfigHandler._add_dependency_pyproject(pyproject_path, name, value)
            return

        config = ConfigHandler.load(config_path, pyproject_path)
        norm_name = normalize_package_name(name)
        config.dependencies[norm_name] = value
        ConfigHandler.save(config_path, config)

    @staticmethod
    def remove_dependency(
        config_path: Path,
        name: str,
        pyproject_path: Path | None = None,
    ) -> None:
        """Remove a dependency entry from vnma.toml or pyproject.toml."""
        if not config_path.exists() and pyproject_path and pyproject_path.exists():
            ConfigHandler._remove_dependency_pyproject(pyproject_path, name)
            return

        config = ConfigHandler.load(config_path, pyproject_path)
        norm_name = normalize_package_name(name)
        config.dependencies.pop(norm_name, None)
        config.dev_dependencies.pop(norm_name, None)
        ConfigHandler.save(config_path, config)


    @staticmethod
    def _parse_vnma_data(data: dict[str, Any]) -> VnmaConfig:
        """Extract configuration properties from raw parsed dictionary."""
        project_data = data.get("project", {})
        tool_data = data.get("tool", {}).get("vnma", {})
        package_overrides = data.get("package", {})

        return VnmaConfig(
            project_name=project_data.get("name", "project"),
            version=project_data.get("version", "0.1.0"),
            dependencies=data.get("dependencies", {}),
            dev_dependencies=data.get("dev-dependencies", {}),
            vendor_dir=tool_data.get("vendor_dir", "vendor"),
            ide_integration=tool_data.get("ide_integration", ["vscode", "pycharm"]),
            package_overrides=package_overrides,
        )
