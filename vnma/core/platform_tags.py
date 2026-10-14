"""Platform, architecture, and wheel tag compatibility detection."""

from __future__ import annotations

import platform
import re
import sys
import sysconfig
from dataclasses import dataclass

try:
    from packaging import tags as packaging_tags
except ImportError:
    packaging_tags = None


@dataclass(slots=True, frozen=True)
class ParsedWheelFilename:
    """Deconstructed components of a standard PEP 427 wheel filename."""

    distribution: str
    version: str
    python_tags: tuple[str, ...]
    abi_tags: tuple[str, ...]
    platform_tags: tuple[str, ...]


class PlatformTagMatcher:
    """Evaluates compatibility between wheel tags and the current runtime."""

    _WHEEL_REGEX = re.compile(
        r"^(?P<dist>[^\-]+)-(?P<ver>[^\-]+)(?:-[^\-]+)?-(?P<py>[^\-]+)-(?P<abi>[^\-]+)-(?P<plat>[^\-]+)\.whl$"
    )

    def __init__(self) -> None:
        """Initialize supported tags for the host environment."""
        self._supported_tags = self._resolve_supported_tags()

    def parse_wheel_filename(self, filename: str) -> ParsedWheelFilename | None:
        """Parse wheel filename into tag tuples according to PEP 427."""
        match = self._WHEEL_REGEX.match(filename)
        if not match:
            return None
        return ParsedWheelFilename(
            distribution=match.group("dist"),
            version=match.group("ver"),
            python_tags=tuple(match.group("py").split(".")),
            abi_tags=tuple(match.group("abi").split(".")),
            platform_tags=tuple(match.group("plat").split(".")),
        )

    def is_wheel_compatible(self, filename: str) -> bool:
        """Check if a wheel filename can run in the current environment."""
        parsed = self.parse_wheel_filename(filename)
        if not parsed:
            return False

        for py in parsed.python_tags:
            for abi in parsed.abi_tags:
                for plat in parsed.platform_tags:
                    if (py, abi, plat) in self._supported_tags:
                        return True
        return False

    def get_tag_priority(self, filename: str) -> int:
        """Calculate ranking index for wheel selection; lower is better, -1 if incompatible."""
        parsed = self.parse_wheel_filename(filename)
        if not parsed:
            return -1

        best_score = -1
        for py in parsed.python_tags:
            for abi in parsed.abi_tags:
                for plat in parsed.platform_tags:
                    key = (py, abi, plat)
                    if key in self._supported_tags:
                        score = self._supported_tags[key]
                        if best_score == -1 or score < best_score:
                            best_score = score
        return best_score

    def _resolve_supported_tags(self) -> dict[tuple[str, str, str], int]:
        """Build prioritized lookup table for matching (python, abi, platform) tags."""
        if packaging_tags is not None:
            tag_list = list(packaging_tags.sys_tags())
            return {(t.interpreter, t.abi, t.platform): idx for idx, t in enumerate(tag_list)}

        tags: dict[tuple[str, str, str], int] = {}
        idx = 0
        py_ver = f"cp{sys.version_info.major}{sys.version_info.minor}"
        py_major = f"py{sys.version_info.major}"
        plat = self._get_default_platform_tag()

        tags[(py_ver, py_ver, plat)] = idx
        idx += 1
        tags[(py_ver, "abi3", plat)] = idx
        idx += 1
        tags[(py_ver, "none", plat)] = idx
        idx += 1
        tags[(py_major, "none", "any")] = idx
        idx += 1
        tags[("py3", "none", "any")] = idx
        idx += 1
        tags[("py2.py3", "none", "any")] = idx
        return tags

    @staticmethod
    def _get_default_platform_tag() -> str:
        """Detect fallback platform tag using standard system configuration."""
        os_name = sys.platform
        arch = platform.machine().lower()

        if os_name == "win32":
            if arch in ("amd64", "x86_64"):
                return "win_amd64"
            if arch in ("x86", "i386", "i686"):
                return "win32"
            if arch in ("arm64", "aarch64"):
                return "win_arm64"
            return f"win_{arch}"

        if os_name.startswith("linux"):
            if arch in ("x86_64", "amd64"):
                return "manylinux_2_17_x86_64"
            if arch in ("aarch64", "arm64"):
                return "manylinux_2_17_aarch64"
            return f"linux_{arch}"

        if os_name == "darwin":
            mac_ver = platform.mac_ver()[0]
            major_ver = mac_ver.split(".")[0] if mac_ver else "11"
            if arch in ("arm64", "aarch64"):
                return f"macosx_{major_ver}_0_arm64"
            return f"macosx_{major_ver}_0_x86_64"

        return sysconfig.get_platform().replace("-", "_")
