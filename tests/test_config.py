"""Unit tests for configuration loaders and vnma_config.toml package metadata."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from vnma.core.config import ConfigHandler, VnmaConfig
from vnma.core.package_config import PackageConfig


class TestPackageConfig(unittest.TestCase):
    """Test loading and parsing of package-level vnma_config.toml files."""

    def test_from_dict_defaults(self) -> None:
        """Verify default fallback values when parsing minimal package dictionary."""
        cfg = PackageConfig.from_dict({"package": {"name": "test-pkg"}})
        self.assertEqual(cfg.name, "test-pkg")
        self.assertEqual(cfg.package_type, "pure-python")
        self.assertEqual(cfg.dll_directories, [])
        self.assertTrue(cfg.hermetic)

    def test_from_dict_rich_metadata(self) -> None:
        """Verify full parsing of custom runtime DLLs and export definitions."""
        data = {
            "package": {"name": "my-native-lib", "version": "2.0.0", "type": "native"},
            "runtime": {"dll_directories": ["bin", "extra_dlls"], "hermetic": False},
            "exports": {"entry_points": {"cli": "my_native_lib.cli:main"}},
        }
        cfg = PackageConfig.from_dict(data)
        self.assertEqual(cfg.name, "my-native-lib")
        self.assertEqual(cfg.version, "2.0.0")
        self.assertEqual(cfg.package_type, "native")
        self.assertEqual(cfg.dll_directories, ["bin", "extra_dlls"])
        self.assertFalse(cfg.hermetic)
        self.assertEqual(cfg.entry_points, {"cli": "my_native_lib.cli:main"})

    def test_load_from_dir_success(self) -> None:
        """Verify loading vnma_config.toml directly from directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            cfg_file = tmp_path / "vnma_config.toml"
            cfg_file.write_text(
                '[package]\nname = "gram-framework"\nversion = "2.0.0"\n\n'
                '[runtime]\ndll_directories = ["gram/native"]\n',
                encoding="utf-8",
            )
            loaded = PackageConfig.load_from_dir(tmp_path)
            self.assertIsNotNone(loaded)
            if loaded:
                self.assertEqual(loaded.name, "gram-framework")
                self.assertEqual(loaded.version, "2.0.0")
                self.assertEqual(loaded.dll_directories, ["gram/native"])

    def test_load_from_dir_missing(self) -> None:
        """Verify None is returned when vnma_config.toml does not exist."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            loaded = PackageConfig.load_from_dir(Path(tmp_dir))
            self.assertIsNone(loaded)


class TestConfigHandler(unittest.TestCase):
    """Test project-level vnma.toml configuration parser and serializer."""

    def test_save_and_reload_roundtrip(self) -> None:
        """Verify VnmaConfig saves to disk and reloads identical values."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_file = Path(tmp_dir) / "vnma.toml"
            original = VnmaConfig(
                project_name="sample-project",
                version="1.2.3",
                dependencies={
                    "requests": ">=2.28.0",
                    "my-local": {"path": "./local_dir"},
                    "my-git": {"git": "https://github.com/org/repo.git", "branch": "dev"},
                },
                vendor_dir="custom_vendor",
            )

            ConfigHandler.save(config_file, original)
            self.assertTrue(config_file.is_file())

            reloaded = ConfigHandler.load(config_file)
            self.assertEqual(reloaded.project_name, "sample-project")
            self.assertEqual(reloaded.version, "1.2.3")
            self.assertEqual(reloaded.vendor_dir, "custom_vendor")
            self.assertIn("requests", reloaded.dependencies)
            self.assertIn("my-local", reloaded.dependencies)
            self.assertIn("my-git", reloaded.dependencies)

    def test_get_all_specs_conversion(self) -> None:
        """Verify get_all_specs converts strings, paths, and git dependencies."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            sub = Path(tmp_dir) / "sub"
            sub.mkdir()
            config = VnmaConfig(
                dependencies={
                    "urllib3": ">=1.26.0",
                    "local-pkg": {"path": str(sub)},
                    "git-pkg": {"git": "https://fake.git", "branch": "release"},
                }
            )
            specs = config.get_all_specs()
            self.assertEqual(len(specs), 3)

            spec_map = {s.name: s for s in specs}
            self.assertIn("urllib3", spec_map)
            self.assertEqual(spec_map["urllib3"].specifier, ">=1.26.0")

            self.assertIn("local-pkg", spec_map)
            self.assertEqual(spec_map["local-pkg"].path, sub.resolve())

            self.assertIn("git-pkg", spec_map)
            self.assertEqual(spec_map["git-pkg"].git_url, "https://fake.git")
            self.assertEqual(spec_map["git-pkg"].git_ref, "release")


if __name__ == "__main__":
    unittest.main()
