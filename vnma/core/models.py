"""Data transfer objects and domain models for VNMA."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from vnma.core.path_resolver import PortablePathResolver

_NORM_REGEX = re.compile(r"[-_.]+")
_DASH_VER_REGEX = re.compile(
    r"^(?P<name>[a-zA-Z0-9][a-zA-Z0-9._\-]*?)-(?P<ver>\d+(?:\.[a-zA-Z0-9._]+)*)$"
)
_SPEC_SPLIT_REGEX = re.compile(r"(===|==|~=|!=|<=|>=|<|>)")


def normalize_package_name(name: str) -> str:
    """Normalize package name according to PEP 503."""
    return _NORM_REGEX.sub("-", name.strip()).lower()


@dataclass(slots=True, frozen=True)
class PackageSpec:
    """Represents a requested package name and optional version specifier."""

    name: str
    specifier: str = ""
    extras: tuple[str, ...] = field(default_factory=tuple)
    path: Path | None = None
    git_url: str | None = None
    git_ref: str | None = None
    editable: bool = False

    @classmethod
    def parse(cls, raw: str) -> PackageSpec:
        """Parse package requirement string supporting PEP 508, paths, git URLs and dash syntax."""
        cleaned = raw.strip()

        if cleaned.startswith("git+") or cleaned.startswith("git://"):
            clean_git = cleaned[4:] if cleaned.startswith("git+") else cleaned
            git_url, _, git_ref = clean_git.partition("@")
            repo_name = git_url.rstrip("/").split("/")[-1]
            if repo_name.endswith(".git"):
                repo_name = repo_name[:-4]
            return cls(
                name=normalize_package_name(repo_name),
                git_url=git_url,
                git_ref=git_ref or "main",
            )

        candidate_path = PortablePathResolver.expand(cleaned)
        if candidate_path.is_dir() or cleaned.startswith(("./", "../", ".\\", "..\\", "~", "%user%", "%USER%")) or (len(cleaned) >= 3 and cleaned[1:3] == ":\\"):
            res_path = candidate_path.resolve()
            pkg_name = normalize_package_name(res_path.name)
            vnma_cfg = res_path / "vnma_config.toml"
            if vnma_cfg.is_file():
                try:
                    import tomllib
                    with vnma_cfg.open("rb") as f:
                        data = tomllib.load(f)
                    if "package" in data and "name" in data["package"]:
                        pkg_name = normalize_package_name(data["package"]["name"])
                except Exception:
                    pass
            elif (res_path / "pyproject.toml").is_file():
                try:
                    import tomllib
                    with (res_path / "pyproject.toml").open("rb") as f:
                        data = tomllib.load(f)
                    if "project" in data and "name" in data["project"]:
                        pkg_name = normalize_package_name(data["project"]["name"])
                except Exception:
                    pass
            return cls(name=pkg_name, path=res_path)

        cleaned = cleaned.split(";", 1)[0].strip()

        extras: tuple[str, ...] = ()
        if "[" in cleaned and "]" in cleaned:
            b_start = cleaned.index("[")
            b_end = cleaned.index("]")
            raw_extras = cleaned[b_start + 1 : b_end]
            extras = tuple(e.strip().lower() for e in raw_extras.split(",") if e.strip())
            cleaned = cleaned[:b_start] + cleaned[b_end + 1 :]

        op_match = _SPEC_SPLIT_REGEX.search(cleaned)
        if op_match:
            idx = op_match.start()
            pkg_name = normalize_package_name(cleaned[:idx])
            spec = cleaned[idx:].strip()
            return cls(name=pkg_name, specifier=spec, extras=extras)

        dash_match = _DASH_VER_REGEX.match(cleaned)
        if dash_match:
            pkg_name = normalize_package_name(dash_match.group("name"))
            ver = dash_match.group("ver").strip()
            return cls(name=pkg_name, specifier=f"=={ver}", extras=extras)

        return cls(name=normalize_package_name(cleaned), specifier="", extras=extras)

    def matches(self, version_str: str) -> bool:
        """Check whether a candidate version string satisfies the package specifier."""
        if not self.specifier or self.specifier == "*":
            return True
        try:
            from packaging.specifiers import SpecifierSet
            from packaging.version import Version
            spec_set = SpecifierSet(self.specifier)
            return Version(version_str) in spec_set
        except Exception:
            return True


@dataclass(slots=True, frozen=True)
class WheelRelease:
    """Describes a distributable wheel asset available on an index."""

    filename: str
    url: str
    sha256: str
    version: str
    python_tag: str
    abi_tag: str
    platform_tag: str
    requires_dist: tuple[str, ...] = field(default_factory=tuple)


@dataclass(slots=True, frozen=True)
class InstalledFile:
    """Represents a single file written to the vendor directory."""

    relative_path: str
    sha256: str
    size_bytes: int


@dataclass(slots=True)
class InstalledPackageRecord:
    """Tracks a fully installed package inside the vendor directory."""

    name: str
    version: str
    import_name: str = ""
    files: list[InstalledFile] = field(default_factory=list)
    dll_directories: list[str] = field(default_factory=list)
    entry_points: dict[str, str] = field(default_factory=dict)
    has_native_binaries: bool = False
    active_extras: list[str] = field(default_factory=list)
    wheel_filename: str = ""
    wheel_sha256: str = ""
    hermetic: bool = True
    modules: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert record to dictionary for JSON persistence."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InstalledPackageRecord:
        """Hydrate record from serialized dictionary."""
        files = [
            InstalledFile(
                relative_path=f["relative_path"],
                sha256=f["sha256"],
                size_bytes=f["size_bytes"],
            )
            for f in data.get("files", [])
        ]
        return cls(
            name=normalize_package_name(data["name"]),
            version=data["version"],
            import_name=data.get("import_name", ""),
            files=files,
            dll_directories=data.get("dll_directories", []),
            entry_points=data.get("entry_points", {}),
            has_native_binaries=data.get("has_native_binaries", False),
            active_extras=data.get("active_extras", []),
            wheel_filename=data.get("wheel_filename", ""),
            wheel_sha256=data.get("wheel_sha256", ""),
            hermetic=data.get("hermetic", True),
            modules=data.get("modules", []),
        )


@dataclass(slots=True)
class VnmaManifest:
    """Root vendor manifest tracking all installed packages and host environment."""

    manifest_version: str = "1.0"
    python_version: str = ""
    packages: dict[str, InstalledPackageRecord] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize manifest structure to primitive dictionary."""
        return {
            "manifest_version": self.manifest_version,
            "python_version": self.python_version,
            "packages": {name: pkg.to_dict() for name, pkg in self.packages.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VnmaManifest:
        """Deserialize manifest from primitive dictionary."""
        packages = {
            normalize_package_name(name): InstalledPackageRecord.from_dict(pkg_data)
            for name, pkg_data in data.get("packages", {}).items()
        }
        return cls(
            manifest_version=data.get("manifest_version", "1.0"),
            python_version=data.get("python_version", ""),
            packages=packages,
        )
