"""Local filesystem wheel index for offline dependency resolution."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from typing import Any, Sequence

from vnma.core.models import WheelRelease, normalize_package_name
from vnma.core.platform_tags import PlatformTagMatcher


class OfflineMissingDependencyError(RuntimeError):
    """Raised when a dependency cannot be satisfied from local offline caches."""


class LocalWheelIndex:
    """Discovers and inspects wheels across local cache directories with zero network calls."""

    def __init__(
        self,
        search_directories: Sequence[Path] | None = None,
        tag_matcher: PlatformTagMatcher | None = None,
    ) -> None:
        """Initialize index with directories to search for pre-built wheel distributions."""
        self._directories: list[Path] = []
        if search_directories:
            for d in search_directories:
                p = Path(d).resolve()
                if p.is_dir() and p not in self._directories:
                    self._directories.append(p)

        self._matcher = tag_matcher or PlatformTagMatcher()
        self._wheel_metadata_cache: dict[Path, tuple[str, list[str]]] = {}

    @property
    def directories(self) -> list[Path]:
        """Configured local search directories."""
        return list(self._directories)

    def add_directory(self, directory: Path) -> None:
        """Add a filesystem directory to the offline search path."""
        resolved = directory.resolve()
        if resolved.is_dir() and resolved not in self._directories:
            self._directories.append(resolved)

    def fetch_wheel_releases(
        self, package_name: str, requested_version: str | None = None
    ) -> list[WheelRelease]:
        """Scan search directories for platform-compatible wheels matching package name and version."""
        norm_target = normalize_package_name(package_name)
        releases: list[WheelRelease] = []

        for directory in self._directories:
            if not directory.is_dir():
                continue
            for file_path in directory.glob("*.whl"):
                parsed = self._matcher.parse_wheel_filename(file_path.name)
                if not parsed:
                    continue
                if normalize_package_name(parsed.distribution) != norm_target:
                    continue
                if requested_version and parsed.version != requested_version:
                    continue

                sha256_digest, reqs = self._inspect_wheel(file_path)
                release = WheelRelease(
                    filename=file_path.name,
                    url=file_path.as_uri(),
                    sha256=sha256_digest,
                    version=parsed.version,
                    python_tag=".".join(parsed.python_tags),
                    abi_tag=".".join(parsed.abi_tags),
                    platform_tag=".".join(parsed.platform_tags),
                    requires_dist=tuple(reqs),
                )
                releases.append(release)

        return releases

    def fetch_package_data(
        self, package_name: str, version: str | None = None
    ) -> dict[str, Any]:
        """Extract metadata for package version from indexed local wheels."""
        releases = self.fetch_wheel_releases(package_name, version)
        if not releases:
            return {"info": {"requires_dist": []}}
        return {"info": {"requires_dist": list(releases[0].requires_dist)}}

    def _inspect_wheel(self, wheel_path: Path) -> tuple[str, list[str]]:
        """Extract SHA256 and Requires-Dist lines from wheel without disk unpacking."""
        if wheel_path in self._wheel_metadata_cache:
            return self._wheel_metadata_cache[wheel_path]

        hasher = hashlib.sha256()
        with wheel_path.open("rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        digest = hasher.hexdigest()

        requires_dist: list[str] = []
        try:
            with zipfile.ZipFile(wheel_path, "r") as zf:
                for name in zf.namelist():
                    norm_name = name.replace("\\", "/")
                    parts = norm_name.split("/")
                    if len(parts) == 2 and parts[0].endswith(".dist-info") and parts[1] == "METADATA":
                        with zf.open(name, "r") as meta_f:
                            text = meta_f.read().decode("utf-8", errors="replace")
                            for line in text.splitlines():
                                if line.startswith("Requires-Dist:"):
                                    requires_dist.append(line[len("Requires-Dist:") :].strip())
                        break
        except Exception:
            pass

        result = (digest, requires_dist)
        self._wheel_metadata_cache[wheel_path] = result
        return result
