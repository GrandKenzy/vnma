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
from vnma.core.cleaner import WorkspaceCleaner
from vnma.core.path_resolver import PortablePathResolver
from vnma.core.platform_tags import PlatformTagMatcher

__all__ = [
    "ConfigHandler",
    "InstalledFile",
    "InstalledPackageRecord",
    "PackageSpec",
    "PlatformTagMatcher",
    "PortablePathResolver",
    "ProjectContext",
    "VnmaConfig",
    "VnmaManifest",
    "WheelRelease",
    "WorkspaceCleaner",
]
