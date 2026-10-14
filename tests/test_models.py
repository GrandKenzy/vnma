"""Unit tests for VNMA data models and package specification parser."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from vnma.core.models import (
    InstalledFile,
    InstalledPackageRecord,
    PackageSpec,
    VnmaManifest,
    normalize_package_name,
)


class TestPackageNormalization(unittest.TestCase):
    """Test PEP 503 package name normalization logic."""

    def test_pep503_lowercasing(self) -> None:
        """Verify package names are converted to lowercase."""
        self.assertEqual(normalize_package_name("Requests"), "requests")
        self.assertEqual(normalize_package_name("PyQt5"), "pyqt5")

    def test_pep503_symbol_replacement(self) -> None:
        """Verify underscores, periods, and repeated separators normalize to single hyphens."""
        self.assertEqual(normalize_package_name("foo_bar"), "foo-bar")
        self.assertEqual(normalize_package_name("foo.bar"), "foo-bar")
        self.assertEqual(normalize_package_name("foo__._-bar"), "foo-bar")


class TestPackageSpecParser(unittest.TestCase):
    """Test parsing of various package requirement expressions."""

    def test_simple_package_name(self) -> None:
        """Verify parsing a package name with no version constraints."""
        spec = PackageSpec.parse("requests")
        self.assertEqual(spec.name, "requests")
        self.assertEqual(spec.specifier, "")
        self.assertEqual(spec.extras, ())

    def test_version_operators(self) -> None:
        """Verify operators such as ==, >=, <=, ~=, and compound ranges."""
        spec_eq = PackageSpec.parse("requests==2.31.0")
        self.assertEqual(spec_eq.name, "requests")
        self.assertEqual(spec_eq.specifier, "==2.31.0")

        spec_range = PackageSpec.parse("urllib3>=1.26.0,<3.0.0")
        self.assertEqual(spec_range.name, "urllib3")
        self.assertEqual(spec_range.specifier, ">=1.26.0,<3.0.0")

        spec_tilde = PackageSpec.parse("flask~=2.3.0")
        self.assertEqual(spec_tilde.name, "flask")
        self.assertEqual(spec_tilde.specifier, "~=2.3.0")

    def test_extras_parsing(self) -> None:
        """Verify extraction of bracketed optional dependencies."""
        spec = PackageSpec.parse("uvicorn[standard]>=0.20.0")
        self.assertEqual(spec.name, "uvicorn")
        self.assertEqual(spec.specifier, ">=0.20.0")
        self.assertEqual(spec.extras, ("standard",))

    def test_dash_version_syntax(self) -> None:
        """Verify dash-separated version syntax is converted to == specifier."""
        spec = PackageSpec.parse("requests-2.31.0")
        self.assertEqual(spec.name, "requests")
        self.assertEqual(spec.specifier, "==2.31.0")

    def test_git_url_specification(self) -> None:
        """Verify git+https URLs with optional branch or tag references."""
        spec = PackageSpec.parse("git+https://github.com/psf/requests.git@v2.31.0")
        self.assertEqual(spec.name, "requests")
        self.assertEqual(spec.git_url, "https://github.com/psf/requests.git")
        self.assertEqual(spec.git_ref, "v2.31.0")

    def test_local_path_specification(self) -> None:
        """Verify local directory path detection and configuration loading."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            cfg_file = tmp_path / "vnma_config.toml"
            cfg_file.write_text('[package]\nname = "my-custom-pkg"\n', encoding="utf-8")

            spec = PackageSpec.parse(str(tmp_path))
            self.assertEqual(spec.name, "my-custom-pkg")
            self.assertEqual(spec.path, tmp_path.resolve())


class TestManifestSerialization(unittest.TestCase):
    """Test VnmaManifest and InstalledPackageRecord serialization and hydration."""

    def test_manifest_roundtrip(self) -> None:
        """Verify VnmaManifest persists to dictionary and loads identical state."""
        file_record = InstalledFile(
            relative_path="test_pkg/__init__.py",
            sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            size_bytes=100,
        )
        pkg_record = InstalledPackageRecord(
            name="test-pkg",
            version="1.0.0",
            files=[file_record],
            dll_directories=["test_pkg/libs"],
            has_native_binaries=True,
        )
        manifest = VnmaManifest(
            python_version="3.14",
            packages={"test-pkg": pkg_record},
        )

        serialized = manifest.to_dict()
        self.assertIn("packages", serialized)
        self.assertIn("test-pkg", serialized["packages"])

        reloaded = VnmaManifest.from_dict(serialized)
        self.assertEqual(reloaded.python_version, "3.14")
        self.assertIn("test-pkg", reloaded.packages)
        loaded_pkg = reloaded.packages["test-pkg"]
        self.assertEqual(loaded_pkg.version, "1.0.0")
        self.assertEqual(len(loaded_pkg.files), 1)
        self.assertEqual(loaded_pkg.files[0].relative_path, "test_pkg/__init__.py")
        self.assertTrue(loaded_pkg.has_native_binaries)


if __name__ == "__main__":
    unittest.main()
