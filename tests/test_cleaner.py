"""Unit tests for WorkspaceCleaner and full VNMA workspace uninstallation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from vnma.cli import build_parser
from vnma.core.cleaner import WorkspaceCleaner
from vnma.core.context import ProjectContext


class TestWorkspaceCleaner(unittest.TestCase):
    """Test full workspace purging of vendor directories, lockfiles, and ide artifacts."""

    def test_purge_workspace_complete_cleanup(self) -> None:
        """Verify complete removal of VNMA artifacts leaving only user source files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)

            vendor_dir = base / "vendor"
            meta_dir = vendor_dir / ".vnma_meta"
            meta_dir.mkdir(parents=True, exist_ok=True)
            (vendor_dir / "sample.py").write_text("x = 1\n", encoding="utf-8")

            (base / "vnma.lock").write_text('{"packages": {}}\n', encoding="utf-8")
            (base / "vnma.toml").write_text('[project]\nname = "app"\n', encoding="utf-8")

            vscode_dir = base / ".vscode"
            vscode_dir.mkdir(parents=True, exist_ok=True)
            (vscode_dir / "settings.json").write_text(
                json.dumps({"python.analysis.extraPaths": ["./vendor", "${userHome}/Desktop/Gram"]}),
                encoding="utf-8",
            )

            (base / ".env").write_text("PYTHONPATH=./vendor\n", encoding="utf-8")
            (base / ".gitignore").write_text(
                "# --- VNMA (Vendor Manager) ---\n/vendor/\n/vendor_vnma/\n.vnma_meta/\nvnma_cache/\n",
                encoding="utf-8",
            )

            main_py = base / "main.py"
            main_py.write_text("print('hello')\n", encoding="utf-8")

            context = ProjectContext(start_path=base)
            cleaner = WorkspaceCleaner(context)
            actions = cleaner.purge(keep_config=False)

            self.assertGreater(len(actions), 0)
            self.assertFalse(vendor_dir.exists())
            self.assertFalse((base / "vnma.lock").exists())
            self.assertFalse((base / "vnma.toml").exists())
            self.assertFalse(vscode_dir.exists())
            self.assertFalse((base / ".env").exists())
            self.assertFalse((base / ".gitignore").exists())
            self.assertTrue(main_py.is_file())
            self.assertEqual(main_py.read_text(encoding="utf-8"), "print('hello')\n")

    def test_purge_workspace_preserves_user_settings_and_keep_config(self) -> None:
        """Verify user configs and other environment variables are preserved during purge."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)

            vendor_dir = base / "vendor"
            vendor_dir.mkdir(parents=True, exist_ok=True)
            (vendor_dir / "dep.py").write_text("a = 1\n", encoding="utf-8")

            (base / "vnma.lock").write_text('{"packages": {}}\n', encoding="utf-8")
            (base / "vnma.toml").write_text('[project]\nname = "my_app"\n', encoding="utf-8")

            vscode_dir = base / ".vscode"
            vscode_dir.mkdir(parents=True, exist_ok=True)
            (vscode_dir / "settings.json").write_text(
                json.dumps({
                    "editor.tabSize": 4,
                    "python.analysis.extraPaths": ["./vendor"],
                }),
                encoding="utf-8",
            )

            (base / ".env").write_text("DB_HOST=127.0.0.1\nPYTHONPATH=./vendor\n", encoding="utf-8")
            (base / ".gitignore").write_text(
                "*.log\n# --- VNMA (Vendor Manager) ---\n/vendor/\n",
                encoding="utf-8",
            )

            context = ProjectContext(start_path=base)
            cleaner = WorkspaceCleaner(context)
            cleaner.purge(keep_config=True)

            self.assertFalse(vendor_dir.exists())
            self.assertFalse((base / "vnma.lock").exists())
            self.assertTrue((base / "vnma.toml").is_file())

            settings = json.loads((vscode_dir / "settings.json").read_text(encoding="utf-8"))
            self.assertEqual(settings.get("editor.tabSize"), 4)
            self.assertNotIn("python.analysis.extraPaths", settings)

            env_content = (base / ".env").read_text(encoding="utf-8")
            self.assertIn("DB_HOST=127.0.0.1", env_content)
            self.assertNotIn("PYTHONPATH", env_content)

            git_content = (base / ".gitignore").read_text(encoding="utf-8")
            self.assertIn("*.log", git_content)
            self.assertNotIn("VNMA", git_content)


class TestCliUninstallWorkspace(unittest.TestCase):
    """Test CLI invocation of vnma uninstall without arguments."""

    def test_cli_uninstall_without_package_purges_workspace(self) -> None:
        """Verify running vnma uninstall -y purges vendor directory cleanly."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            vendor_dir = base / "vendor"
            vendor_dir.mkdir(parents=True, exist_ok=True)
            (vendor_dir / "mod.py").write_text("x = 1\n", encoding="utf-8")
            (base / "vnma.lock").write_text("{}", encoding="utf-8")
            (base / "vnma.toml").write_text('[project]\nname = "test"\n', encoding="utf-8")

            context = ProjectContext(start_path=base)
            parser = build_parser()
            args = parser.parse_args(["uninstall", "-y"])
            ret = args.handler(args, context)

            self.assertEqual(ret, 0)
            self.assertFalse(vendor_dir.exists())
            self.assertFalse((base / "vnma.lock").exists())
            self.assertFalse((base / "vnma.toml").exists())


if __name__ == "__main__":
    unittest.main()
