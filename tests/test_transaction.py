"""Crash recovery, rollback, and batch installation regression tests."""

from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from vnma.core.context import ProjectContext
from vnma.core.transaction import WorkspaceTransaction
from vnma.wheel.installer import WheelInstaller


def make_wheel(root: Path, distribution: str, version: str, module: str, content: str) -> Path:
    path = root / f"{distribution}-{version}-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"{module}/__init__.py", content)
        archive.writestr(
            f"{distribution}-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.1\nName: {distribution}\nVersion: {version}\n",
        )
    return path


class TestWorkspaceTransaction(unittest.TestCase):
    def test_direct_install_commits_and_cleans_staging(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "vnma.toml").write_text('[project]\nname = "app"\n', encoding="utf-8")
            context = ProjectContext(start_path=root)
            wheel = make_wheel(root, "example", "1.0", "example", "VERSION = 1\n")
            record = WheelInstaller(context).install(wheel, "example", "1.0")

            self.assertEqual(record.version, "1.0")
            self.assertTrue((root / "vendor/example/__init__.py").is_file())
            self.assertFalse((root / ".vnma-transaction.json").exists())
            self.assertFalse((root / ".vnma-transaction.lock").exists())
            self.assertFalse(list(root.glob(".vnma-stage-*")))
            self.assertFalse(list(root.glob(".vnma-backup-*")))

    def test_multi_wheel_batch_rollback_on_second_wheel_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / "vnma.toml"
            original = '[project]\nname = "app"\n'
            config.write_text(original, encoding="utf-8")
            context = ProjectContext(start_path=root)
            old = make_wheel(root, "example", "1.0", "example", "VERSION = 1\n")
            WheelInstaller(context).install(old, "example", "1.0")
            original_manifest = context.manifest_path.read_bytes()

            with self.assertRaises(zipfile.BadZipFile):
                with WorkspaceTransaction(context):
                    new = make_wheel(root, "example", "2.0", "example", "VERSION = 2\n")
                    WheelInstaller(context).install(new, "example", "2.0")
                    config.write_text('[project]\nname = "modified"\n', encoding="utf-8")
                    broken = root / "broken-1.0-py3-none-any.whl"
                    broken.write_bytes(b"corrupt")
                    WheelInstaller(context).install(broken, "broken", "1.0")

            self.assertEqual(config.read_text(encoding="utf-8"), original)
            self.assertEqual((root / "vendor/example/__init__.py").read_text(), "VERSION = 1\n")
            self.assertEqual(context.manifest_path.read_bytes(), original_manifest)
            self.assertFalse(list(root.glob(".vnma-stage-*")))
            self.assertFalse(list(root.glob(".vnma-backup-*")))

    def test_recover_crash_before_vendor_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "vnma.toml").write_text('[project]\nname = "app"\n', encoding="utf-8")
            context = ProjectContext(start_path=root)
            wheel = make_wheel(root, "stable", "1.0", "stable", "old\n")
            WheelInstaller(context).install(wheel, "stable", "1.0")
            txn = WorkspaceTransaction(context)
            txn.__enter__()
            replacement = make_wheel(root, "stable", "2.0", "stable", "new\n")
            WheelInstaller(context).install(replacement, "stable", "2.0")
            # Simulate a killed process: no __exit__ call; the journal
            # remains and the lock is made stale.
            context.vendor_name = txn.original_vendor
            context._transaction_active = False
            txn.lock.write_text("999999999", encoding="ascii")
            WorkspaceTransaction.recover(context)
            self.assertEqual((root / "vendor/stable/__init__.py").read_text(), "old\n")
            self.assertFalse(txn.stage.exists())
            self.assertFalse(txn.lock.exists())

    def test_recover_does_not_roll_back_completed_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "vnma.toml").write_text('[project]\nname = "app"\n', encoding="utf-8")
            context = ProjectContext(start_path=root)
            new = make_wheel(root, "stable", "1.0", "stable", "new\n")
            WheelInstaller(context).install(new, "stable", "1.0")
            txn = WorkspaceTransaction(context)
            txn.__enter__()
            txn.context.vendor_name = txn.original_vendor
            txn.context._transaction_active = False
            txn._journal("committed")
            txn.lock.write_text("999999999", encoding="ascii")
            WorkspaceTransaction.recover(context)
            self.assertTrue((root / "vendor/stable/__init__.py").is_file())
            self.assertFalse(txn.journal.exists())
            self.assertFalse(txn.stage.exists())

    def test_reject_external_vendor_without_changing_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "project"
            external = root / "other"
            project.mkdir()
            external.mkdir()
            untouched = external / "important.txt"
            untouched.write_text("must survive", encoding="utf-8")
            (project / "vnma.toml").write_text(
                '[project]\nname = "app"\n\n[tool.vnma]\nvendor_dir = "../other"\n',
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                with WorkspaceTransaction(ProjectContext(start_path=project)):
                    pass
            self.assertEqual(untouched.read_text(), "must survive")

    def test_batch_keeps_a_successful_graph(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "vnma.toml").write_text('[project]\nname = "app"\n', encoding="utf-8")
            context = ProjectContext(start_path=root)
            a = make_wheel(root, "first", "1.0", "first", "FIRST = 1\n")
            b = make_wheel(root, "second", "1.0", "second", "SECOND = 1\n")
            with WorkspaceTransaction(context):
                WheelInstaller(context).install(a, "first", "1.0")
                WheelInstaller(context).install(b, "second", "1.0")
            self.assertTrue((root / "vendor/first/__init__.py").exists())
            self.assertTrue((root / "vendor/second/__init__.py").exists())
            manifest = json.loads(context.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(set(manifest["packages"]), {"first", "second"})


if __name__ == "__main__":
    unittest.main()
