"""Core modules and data representations for VNMA."""

from vnma.core.config import ConfigHandler, VnmaConfig
from vnma.core.context import ProjectContext
from vnma.core.models import (
    InstalledFile,
    InstalledPackageRecord,
    PackageSpec,
    VnmaManifest,
    WheelRelease,
)
from vnma.core.platform_tags import PlatformTagMatcher

__all__ = [
    "ConfigHandler",
    "InstalledFile",
    "InstalledPackageRecord",
    "PackageSpec",
    "PlatformTagMatcher",
    "ProjectContext",
    "VnmaConfig",
    "VnmaManifest",
    "WheelRelease",
]
