"""Unit tests for LocalWheelIndex offline discovery and metadata extraction."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

from vnma.core.models import PackageSpec
from vnma.pypi.local_index import LocalWheelIndex
from vnma.pypi.resolver import WheelResolver


class TestLocalWheelIndex(unittest.TestCase):
    """Test offline wheel index discovery and metadata inspection."""

    def test_wheel_discovery_and_metadata_reading(self) -> None:
        """Verify local wheel index finds wheels and parses metadata without extracting to disk."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            wheelhouse = Path(tmp_dir)
            wheel_name = "test_offline-1.2.3-py3-none-any.whl"
            wheel_file = wheelhouse / wheel_name

            metadata_content = (
                "Metadata-Version: 2.1\n"
                "Name: test-offline\n"
                "Version: 1.2.3\n"
                "Requires-Dist: cached-dep>=2.0.0\n"
            )

            with zipfile.ZipFile(wheel_file, "w") as zf:
                zf.writestr("test_offline-1.2.3.dist-info/METADATA", metadata_content)

            index = LocalWheelIndex([wheelhouse])
            releases = index.fetch_wheel_releases("test-offline")

            self.assertEqual(len(releases), 1)
            release = releases[0]
            self.assertEqual(release.filename, wheel_name)
            self.assertEqual(release.version, "1.2.3")
            self.assertEqual(release.requires_dist, ("cached-dep>=2.0.0",))

            expected_sha = hashlib.sha256(wheel_file.read_bytes()).hexdigest()
            self.assertEqual(release.sha256, expected_sha)

            pkg_data = index.fetch_package_data("test-offline", "1.2.3")
            self.assertEqual(pkg_data["info"]["requires_dist"], ["cached-dep>=2.0.0"])

    def test_version_filtering(self) -> None:
        """Verify requesting specific version filters out other releases."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            wheelhouse = Path(tmp_dir)
            wheel_file = wheelhouse / "test_pkg-1.0.0-py3-none-any.whl"

            with zipfile.ZipFile(wheel_file, "w") as zf:
                zf.writestr("test_pkg-1.0.0.dist-info/METADATA", "Name: test-pkg\nVersion: 1.0.0\n")

            index = LocalWheelIndex([wheelhouse])
            match_releases = index.fetch_wheel_releases("test-pkg", "1.0.0")
            self.assertEqual(len(match_releases), 1)

            nomatch_releases = index.fetch_wheel_releases("test-pkg", "2.0.0")
            self.assertEqual(len(nomatch_releases), 0)

    def test_resolver_with_local_index(self) -> None:
        """Verify WheelResolver resolves wheels seamlessly using LocalWheelIndex."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            wheelhouse = Path(tmp_dir)
            wheel_file = wheelhouse / "alpha_tool-0.9.0-py3-none-any.whl"

            with zipfile.ZipFile(wheel_file, "w") as zf:
                zf.writestr("alpha_tool-0.9.0.dist-info/METADATA", "Name: alpha-tool\nVersion: 0.9.0\n")

            index = LocalWheelIndex([wheelhouse])
            resolver = WheelResolver(client=index)

            spec = PackageSpec.parse("alpha-tool>=0.5.0")
            resolved_wheel = resolver.resolve_wheel(spec)
            self.assertEqual(resolved_wheel.version, "0.9.0")
            self.assertEqual(resolved_wheel.filename, wheel_file.name)


if __name__ == "__main__":
    unittest.main()
