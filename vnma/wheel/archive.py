"""Secure single-pass Wheel ZIP archive extraction and visitor dispatching."""

from __future__ import annotations

import hashlib
import stat
import zipfile
from pathlib import Path
from typing import Sequence

from vnma.visitors.base import ArtifactElement, ArtifactVisitor


class SecurityError(RuntimeError):
    """Raised when a wheel archive attempts path traversal or unsafe extraction."""


class WheelArchive:
    """Manages safe reading, PEP 427 path mapping, and single-pass extraction of a wheel."""

    CHUNK_SIZE = 65536

    def __init__(self, wheel_path: Path) -> None:
        """Initialize wheel archive with path to .whl file."""
        self._wheel_path = wheel_path

    @property
    def path(self) -> Path:
        """Filesystem path to the underlying wheel archive."""
        return self._wheel_path

    @staticmethod
    def _normalize_wheel_member_path(raw_filename: str) -> tuple[Path, bool]:
        """Map PEP 427 .data directories and detect scripts safely."""
        norm = raw_filename.replace("\\", "/").lstrip("/")
        parts = norm.split("/")

        if any(p in ("..", "") for p in parts if p == ".."):
            raise SecurityError(f"Unsafe relative path segment in wheel entry: {raw_filename}")

        is_script = False
        if len(parts) >= 3 and parts[0].endswith(".data"):
            category = parts[1].lower()
            remainder = Path(*parts[2:])
            if category in ("purelib", "platlib"):
                return remainder, False
            if category == "scripts":
                return Path(".vnma_meta", ".scripts_raw") / remainder, True

        return Path(*parts), is_script

    def extract_and_visit(
        self,
        destination_dir: Path,
        visitors: Sequence[ArtifactVisitor],
    ) -> list[ArtifactElement]:
        """Extract wheel contents safely while computing SHA256 in a single I/O pass."""
        extracted_artifacts: list[ArtifactElement] = []
        dest_root = destination_dir.resolve()
        dest_root.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(self._wheel_path, "r") as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue

                unix_mode = info.external_attr >> 16
                if stat.S_ISLNK(unix_mode):
                    raise SecurityError(f"Symlinks are prohibited inside wheels: {info.filename}")

                rel_path, is_script = self._normalize_wheel_member_path(info.filename)
                target_path = (dest_root / rel_path).resolve()

                if not target_path.is_relative_to(dest_root):
                    raise SecurityError(
                        f"Zip Slip path traversal blocked: {info.filename} -> {target_path}"
                    )

                target_path.parent.mkdir(parents=True, exist_ok=True)

                hasher = hashlib.sha256()
                size_bytes = 0

                with archive.open(info, "r") as src, target_path.open("wb") as dst:
                    while chunk := src.read(self.CHUNK_SIZE):
                        hasher.update(chunk)
                        dst.write(chunk)
                        size_bytes += len(chunk)

                artifact = ArtifactElement(
                    relative_path=rel_path,
                    absolute_path=target_path,
                    sha256=hasher.hexdigest(),
                    size_bytes=size_bytes,
                    is_data_script=is_script,
                )
                extracted_artifacts.append(artifact)

                for visitor in visitors:
                    visitor.visit_artifact(artifact)

        return extracted_artifacts
