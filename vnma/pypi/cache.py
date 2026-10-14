"""Local filesystem wheel cache manager with integrity validation."""

from __future__ import annotations

import hashlib
import os
import shutil
import urllib.parse
import urllib.request
from pathlib import Path


class WheelCache:
    """Manages cached wheel distributions in the user profile directory."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        """Initialize wheel cache path."""
        if cache_dir is None:
            home = Path.home()
            self._cache_dir = home / ".vnma" / "cache" / "wheels"
        else:
            self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def cache_dir(self) -> Path:
        """Directory housing cached wheel archives."""
        return self._cache_dir

    def get_wheel_path(self, filename: str) -> Path | None:
        """Retrieve path to cached wheel if present."""
        target = self._cache_dir / filename
        return target if target.is_file() else None

    def store_wheel(self, filename: str, source_path: Path) -> Path:
        """Copy local wheel into cache directory."""
        target = self._cache_dir / filename
        shutil.copy2(source_path, target)
        return target

    def download_wheel(self, url: str, filename: str, expected_sha256: str | None = None) -> Path:
        """Download remote wheel directly to cache with streaming sha256 calculation."""
        cached = self.get_wheel_path(filename)
        if cached:
            if not expected_sha256 or self._verify_sha256(cached, expected_sha256):
                return cached

        temp_target = self._cache_dir / f"{filename}.part"
        hasher = hashlib.sha256()

        if url.startswith("file://"):
            parsed_url = urllib.parse.urlparse(url)
            src_path = Path(urllib.request.url2pathname(parsed_url.path))
            with src_path.open("rb") as src, temp_target.open("wb") as out:
                while chunk := src.read(65536):
                    hasher.update(chunk)
                    out.write(chunk)
        elif Path(url).is_file():
            src_path = Path(url)
            with src_path.open("rb") as src, temp_target.open("wb") as out:
                while chunk := src.read(65536):
                    hasher.update(chunk)
                    out.write(chunk)
        else:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "vnma/0.2.7"},
            )
            with urllib.request.urlopen(req) as response, temp_target.open("wb") as out:
                while chunk := response.read(65536):
                    hasher.update(chunk)
                    out.write(chunk)

        digest = hasher.hexdigest()
        if expected_sha256 and digest.lower() != expected_sha256.lower():
            temp_target.unlink(missing_ok=True)
            raise ValueError(
                f"Checksum mismatch for {filename}: expected {expected_sha256}, got {digest}"
            )

        final_path = self._cache_dir / filename
        if final_path.exists():
            final_path.unlink()
        temp_target.rename(final_path)
        return final_path

    @staticmethod
    def _verify_sha256(path: Path, expected: str) -> bool:
        """Verify file integrity matches expected sha256 hexadecimal hash."""
        hasher = hashlib.sha256()
        with path.open("rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest().lower() == expected.lower()
