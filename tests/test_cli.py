"""Unit tests for VNMA CLI commands including prune and offline installation."""

from __future__ import annotations

import argparse
import io
import json
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

from vnma.cli import cmd_install, cmd_prune, cmd_uninstall
from vnma.core.context import ProjectContext
from vnma.core.models import InstalledFile, InstalledPackageRecord, VnmaManifest


class TestCliPrune(unittest.TestCase):
    """Test prune subcommand execution and flag handling."""

    def test_prune_clean_vendor(self) -> None:
        """Verify prune command exits cleanly when no orphans are present."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir)
            (project_dir / "vnma.toml").write_text('[project]\nname="test"\n', encoding="utf-8")
            context = ProjectContext(start_path=project_dir)

            args = argparse.Namespace(dry_run=False, yes=True)
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cmd_prune(args, context)

            self.assertEqual(code, 0)
            self.assertIn("No orphaned packages found", buf.getvalue())

    def test_prune_dry_run_with_orphans(self) -> None:
        """Verify dry-run reports orphans without removing files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir)
            vendor_dir = project_dir / "vendor"
            meta_dir = vendor_dir / ".vnma_meta"
            meta_dir.mkdir(parents=True, exist_ok=True)

            (project_dir / "vnma.toml").write_text('[project]\nname="test"\n', encoding="utf-8")

            orphan_file = vendor_dir / "orphan_mod.py"
            orphan_file.write_text("ORPHAN = True\n", encoding="utf-8")

            manifest = VnmaManifest(
                python_version="3.14",
                packages={
                    "orphan-lib": InstalledPackageRecord(
                        name="orphan-lib",
                        version="1.0.0",
                        files=[InstalledFile("orphan_mod.py", "sha", 15)],
                    )
                },
            )
            (meta_dir / "manifest.json").write_text(json.dumps(manifest.to_dict()), encoding="utf-8")

            context = ProjectContext(start_path=project_dir)
            args = argparse.Namespace(dry_run=True, yes=True)

            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cmd_prune(args, context)

            self.assertEqual(code, 0)
            self.assertIn("Dry-run", buf.getvalue())
            self.assertIn("orphan-lib", buf.getvalue())
            self.assertTrue(orphan_file.exists())


class TestCliOfflineInstall(unittest.TestCase):
    """Test offline installation mode and local cache resolution."""

    def test_offline_install_missing_wheel(self) -> None:
        """Verify offline install fails gracefully when requested package is not cached."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir)
            (project_dir / "vnma.toml").write_text(
                '[project]\nname="test"\n\n[dependencies]\nnon-existent-pkg = "==1.0.0"\n',
                encoding="utf-8",
            )
            context = ProjectContext(start_path=project_dir)
            args = argparse.Namespace(
                package=".",
                offline=True,
                find_links=None,
            )

            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cmd_install(args, context)

            self.assertEqual(code, 1)
            self.assertIn("Resolution error", buf.getvalue())
            self.assertIn("Ensure required wheels exist", buf.getvalue())

    def test_offline_install_with_find_links(self) -> None:
        """Verify offline install succeeds when wheel is provided via --find-links."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir)
            wheelhouse = project_dir / "wheelhouse"
            wheelhouse.mkdir(parents=True, exist_ok=True)

            wheel_file = wheelhouse / "local_tool-1.0.0-py3-none-any.whl"
            with zipfile.ZipFile(wheel_file, "w") as zf:
                zf.writestr(
                    "local_tool-1.0.0.dist-info/METADATA",
                    "Metadata-Version: 2.1\nName: local-tool\nVersion: 1.0.0\n",
                )
                zf.writestr("local_tool/__init__.py", "TOOL_VERSION = '1.0.0'\n")

            (project_dir / "vnma.toml").write_text(
                '[project]\nname="test"\n\n[dependencies]\nlocal-tool = "==1.0.0"\n',
                encoding="utf-8",
            )

            context = ProjectContext(start_path=project_dir)
            args = argparse.Namespace(
                package=".",
                offline=True,
                find_links=str(wheelhouse),
            )

            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cmd_install(args, context)

            self.assertEqual(code, 0)
            self.assertIn("Successfully installed local-tool==1.0.0", buf.getvalue())
            installed_init = project_dir / "vendor" / "local_tool" / "__init__.py"
            self.assertTrue(installed_init.is_file())


class TestCliUninstall(unittest.TestCase):
    """Test uninstall command with optional --del flag."""

    def test_uninstall_retains_in_toml_by_default(self) -> None:
        """Verify uninstall removes package from vendor but retains it in vnma.toml."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir)
            vendor_dir = project_dir / "vendor"
            meta_dir = vendor_dir / ".vnma_meta"
            meta_dir.mkdir(parents=True, exist_ok=True)

            (project_dir / "vnma.toml").write_text(
                '[project]\nname="test"\n\n[dependencies]\nsample-pkg = "==1.0.0"\n',
                encoding="utf-8",
            )

            mod_file = vendor_dir / "sample.py"
            mod_file.write_text("SAMPLE = 1\n", encoding="utf-8")

            manifest = VnmaManifest(
                python_version="3.14",
                packages={
                    "sample-pkg": InstalledPackageRecord(
                        name="sample-pkg",
                        version="1.0.0",
                        files=[InstalledFile("sample.py", "sha", 10)],
                    )
                },
            )
            (meta_dir / "manifest.json").write_text(json.dumps(manifest.to_dict()), encoding="utf-8")

            context = ProjectContext(start_path=project_dir)
            args = argparse.Namespace(package="sample-pkg", delete_from_toml=False)

            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cmd_uninstall(args, context)

            self.assertEqual(code, 0)
            self.assertFalse(mod_file.exists())
            toml_content = (project_dir / "vnma.toml").read_text(encoding="utf-8")
            self.assertIn("sample-pkg", toml_content)

    def test_uninstall_with_del_removes_from_toml(self) -> None:
        """Verify uninstall with --del removes package from vendor and vnma.toml."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir)
            vendor_dir = project_dir / "vendor"
            meta_dir = vendor_dir / ".vnma_meta"
            meta_dir.mkdir(parents=True, exist_ok=True)

            (project_dir / "vnma.toml").write_text(
                '[project]\nname="test"\n\n[dependencies]\nsample-pkg = "==1.0.0"\n',
                encoding="utf-8",
            )

            mod_file = vendor_dir / "sample.py"
            mod_file.write_text("SAMPLE = 1\n", encoding="utf-8")

            manifest = VnmaManifest(
                python_version="3.14",
                packages={
                    "sample-pkg": InstalledPackageRecord(
                        name="sample-pkg",
                        version="1.0.0",
                        files=[InstalledFile("sample.py", "sha", 10)],
                    )
                },
            )
            (meta_dir / "manifest.json").write_text(json.dumps(manifest.to_dict()), encoding="utf-8")

            context = ProjectContext(start_path=project_dir)
            args = argparse.Namespace(package="sample-pkg", delete_from_toml=True)

            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cmd_uninstall(args, context)

            self.assertEqual(code, 0)
            self.assertFalse(mod_file.exists())
            toml_content = (project_dir / "vnma.toml").read_text(encoding="utf-8")
            self.assertNotIn("sample-pkg", toml_content)


if __name__ == "__main__":
    unittest.main()
