"""Unit tests for package uninstaller and shared namespace reference counting."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from vnma.core.context import ProjectContext
from vnma.core.models import InstalledFile, InstalledPackageRecord, VnmaManifest
from vnma.wheel.uninstaller import WheelUninstaller


class TestWheelUninstaller(unittest.TestCase):
    """Test safe uninstallation preserving shared namespace files."""

    def test_shared_file_preservation(self) -> None:
        """Verify uninstaller deletes package specific files but preserves shared files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir)
            vendor_dir = project_dir / "vendor"
            vendor_dir.mkdir(parents=True, exist_ok=True)
            meta_dir = vendor_dir / ".vnma_meta"
            meta_dir.mkdir(parents=True, exist_ok=True)

            ns_dir = vendor_dir / "ns_pkg"
            ns_dir.mkdir(parents=True, exist_ok=True)
            shared_init = ns_dir / "__init__.py"
            shared_init.write_text('__import__("pkg_resources").declare_namespace(__name__)\n', encoding="utf-8")

            mod_a = ns_dir / "mod_a.py"
            mod_a.write_text("MODULE_A = True\n", encoding="utf-8")

            mod_b = ns_dir / "mod_b.py"
            mod_b.write_text("MODULE_B = True\n", encoding="utf-8")

            rec_a = InstalledPackageRecord(
                name="package-a",
                version="1.0.0",
                files=[
                    InstalledFile("ns_pkg/__init__.py", "sha_init", 50),
                    InstalledFile("ns_pkg/mod_a.py", "sha_a", 20),
                ],
            )
            rec_b = InstalledPackageRecord(
                name="package-b",
                version="1.0.0",
                files=[
                    InstalledFile("ns_pkg/__init__.py", "sha_init", 50),
                    InstalledFile("ns_pkg/mod_b.py", "sha_b", 20),
                ],
            )
            manifest = VnmaManifest(
                python_version="3.14",
                packages={"package-a": rec_a, "package-b": rec_b},
            )

            manifest_path = meta_dir / "manifest.json"
            manifest_path.write_text(json.dumps(manifest.to_dict()), encoding="utf-8")

            (project_dir / "vnma.toml").write_text('[project]\nname="test"\n', encoding="utf-8")
            context = ProjectContext(start_path=project_dir)
            uninstaller = WheelUninstaller(context)

            success = uninstaller.uninstall("package-a")
            self.assertTrue(success)

            self.assertFalse(mod_a.exists())
            self.assertTrue(shared_init.exists())
            self.assertTrue(mod_b.exists())

            updated_manifest = VnmaManifest.from_dict(
                json.loads(manifest_path.read_text(encoding="utf-8"))
            )
            self.assertNotIn("package-a", updated_manifest.packages)
            self.assertIn("package-b", updated_manifest.packages)


if __name__ == "__main__":
    unittest.main()
