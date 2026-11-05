"""Typed errors shared by VNMA subsystems and the command-line interface."""

from __future__ import annotations


class VnmaError(RuntimeError):
    """Expected user-facing VNMA failure with a stable process exit code."""

    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class ConfigError(VnmaError):
    """Configuration exists but cannot be parsed or validated."""


class ManifestError(VnmaError):
    """Installed manifest is missing, malformed, or internally inconsistent."""


class ArtifactError(VnmaError):
    """Wheel metadata cannot safely be converted into installed artifacts."""
