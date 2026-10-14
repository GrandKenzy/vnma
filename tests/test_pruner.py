"""Unit tests for OrphanPruner transitive reachability and orphan purging."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from vnma.core.context import ProjectContext
from vnma.core.models import InstalledFile, InstalledPackageRecord, PackageSpec, VnmaManifest
from vnma.wheel.pruner import OrphanPruner


class TestOrphanPruner(unittest.TestCase):
    """Test orphan package discovery and uninstallation."""

    def test_reachability_and_orphan_detection(self) -> None:
        """Verify reachability traverses transitive dependencies and identifies disconnected packages."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir)
            vendor_dir = project_dir / "vendor"
            meta_dir = vendor_dir / ".vnma_meta"
            meta_dir.mkdir(parents=True, exist_ok=True)

            (project_dir / "vnma.toml").write_text(
                '[project]\nname = "test"\n\n[dependencies]\nparent-pkg = "==1.0.0"\n',
                encoding="utf-8",
            )

            parent_dist = vendor_dir / "parent_pkg-1.0.0.dist-info"
            parent_dist.mkdir(parents=True, exist_ok=True)
            (parent_dist / "METADATA").write_text(
                "Metadata-Version: 2.1\nName: parent-pkg\nVersion: 1.0.0\nRequires-Dist: child-pkg>=1.0.0\n",
                encoding="utf-8",
            )

            child_dist = vendor_dir / "child_pkg-1.0.0.dist-info"
            child_dist.mkdir(parents=True, exist_ok=True)
            (child_dist / "METADATA").write_text(
                "Metadata-Version: 2.1\nName: child-pkg\nVersion: 1.0.0\n",
                encoding="utf-8",
            )

            orphan_dist = vendor_dir / "orphan_pkg-2.0.0.dist-info"
            orphan_dist.mkdir(parents=True, exist_ok=True)
            (orphan_dist / "METADATA").write_text(
                "Metadata-Version: 2.1\nName: orphan-pkg\nVersion: 2.0.0\n",
                encoding="utf-8",
            )

            (vendor_dir / "parent.py").write_text("PARENT = 1\n", encoding="utf-8")
            (vendor_dir / "child.py").write_text("CHILD = 1\n", encoding="utf-8")
            (vendor_dir / "orphan.py").write_text("ORPHAN = 1\n", encoding="utf-8")

            manifest = VnmaManifest(
                python_version="3.14",
                packages={
                    "parent-pkg": InstalledPackageRecord(
                        name="parent-pkg",
                        version="1.0.0",
                        files=[
                            InstalledFile("parent.py", "sha_p", 10),
                            InstalledFile("parent_pkg-1.0.0.dist-info/METADATA", "sha_meta_p", 50),
                        ],
                    ),
                    "child-pkg": InstalledPackageRecord(
                        name="child-pkg",
                        version="1.0.0",
                        files=[
                            InstalledFile("child.py", "sha_c", 10),
                            InstalledFile("child_pkg-1.0.0.dist-info/METADATA", "sha_meta_c", 50),
                        ],
                    ),
                    "orphan-pkg": InstalledPackageRecord(
                        name="orphan-pkg",
                        version="2.0.0",
                        files=[
                            InstalledFile("orphan.py", "sha_o", 10),
                            InstalledFile("orphan_pkg-2.0.0.dist-info/METADATA", "sha_meta_o", 50),
                        ],
                    ),
                },
            )

            manifest_path = meta_dir / "manifest.json"
            manifest_path.write_text(json.dumps(manifest.to_dict()), encoding="utf-8")

            context = ProjectContext(start_path=project_dir)
            pruner = OrphanPruner(context)

            orphans = pruner.find_orphans()
            self.assertEqual(orphans, ["orphan-pkg"])

            dry_run_pruned = pruner.prune(dry_run=True)
            self.assertEqual(dry_run_pruned, ["orphan-pkg"])
            self.assertTrue((vendor_dir / "orphan.py").exists())

            pruned = pruner.prune(dry_run=False)
            self.assertEqual(pruned, ["orphan-pkg"])
            self.assertFalse((vendor_dir / "orphan.py").exists())
            self.assertTrue((vendor_dir / "parent.py").exists())
            self.assertTrue((vendor_dir / "child.py").exists())

            remaining_orphans = pruner.find_orphans()
            self.assertEqual(remaining_orphans, [])


if __name__ == "__main__":
    unittest.main()
