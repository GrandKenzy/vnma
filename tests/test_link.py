"""Unit tests for vnma link, unlink, and reload zero-copy live development."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from vnma.cli import build_parser, cmd_link, cmd_reload, cmd_run, cmd_unlink
from vnma.core.config import ConfigHandler
from vnma.core.context import ProjectContext
from vnma.core.link_manager import LinkManager
from vnma.core.models import InstalledFile, InstalledPackageRecord, VnmaManifest
from vnma.runtime.runner import ScriptRunner


class TestLinkManager(unittest.TestCase):
    """Test LinkManager registration, live path projection, and unlink behavior."""

    def test_link_directory_and_inspect_metadata(self) -> None:
        """Verify link registers editable package and injects into bootstrap."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            lib_dir = base_dir / "my_lib"
            lib_dir.mkdir()
            (lib_dir / "vnma_config.toml").write_text(
                '[package]\nname = "my-lib"\nversion = "1.0.0"\n\n[exports]\nmodules = ["my_lib"]\n',
                encoding="utf-8",
            )
            pkg_code_dir = lib_dir / "my_lib"
            pkg_code_dir.mkdir()
            (pkg_code_dir / "__init__.py").write_text("MESSAGE = 'live_ok'\n", encoding="utf-8")

            proj_dir = base_dir / "proj"
            proj_dir.mkdir()
            (proj_dir / "vnma.toml").write_text('[project]\nname = "proj"\n\n[dependencies]\n', encoding="utf-8")

            context = ProjectContext(start_path=proj_dir)
            context.ensure_directories()
            manager = LinkManager(context)

            spec, deps = manager.link(str(lib_dir))
            self.assertEqual(spec.name, "my-lib")
            self.assertTrue(spec.editable)
            self.assertEqual(len(deps), 0)

            cfg = ConfigHandler.load(context.config_path)
            self.assertIn("my-lib", cfg.dependencies)
            dep_entry = cfg.dependencies["my-lib"]
            self.assertIsInstance(dep_entry, dict)
            self.assertTrue(dep_entry.get("editable"))

            bootstrap_content = (context.vendor_path / "__bootstrap__.py").read_text(encoding="utf-8")
            self.assertIn(lib_dir.resolve().as_posix(), bootstrap_content)

    def test_zero_copy_live_reflection(self) -> None:
        """Verify modifying source code in linked directory is immediately observed without reinstalling."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            lib_dir = base_dir / "gram"
            lib_dir.mkdir()
            (lib_dir / "vnma_config.toml").write_text(
                '[package]\nname = "gram"\nversion = "1.0.0"\n',
                encoding="utf-8",
            )
            gram_pkg = lib_dir / "gram"
            gram_pkg.mkdir()
            code_file = gram_pkg / "__init__.py"
            code_file.write_text("VALUE = 'initial'\n", encoding="utf-8")

            proj_dir = base_dir / "app"
            proj_dir.mkdir()
            (proj_dir / "vnma.toml").write_text('[project]\nname = "app"\n\n[dependencies]\n', encoding="utf-8")

            context = ProjectContext(start_path=proj_dir)
            context.ensure_directories()
            manager = LinkManager(context)
            manager.link(str(lib_dir))

            output_file = proj_dir / "out.txt"
            main_script = proj_dir / "main.py"
            main_script.write_text(
                f"import gram\nfrom pathlib import Path\nPath({str(output_file)!r}).write_text(gram.VALUE, encoding='utf-8')\n",
                encoding="utf-8",
            )

            runner = ScriptRunner(context)
            ret1 = runner.run_script(main_script)
            self.assertEqual(ret1, 0)
            self.assertEqual(output_file.read_text(encoding="utf-8"), "initial")

            code_file.write_text("VALUE = 'updated_live'\n", encoding="utf-8")

            ret2 = runner.run_script(main_script)
            self.assertEqual(ret2, 0)
            self.assertEqual(output_file.read_text(encoding="utf-8"), "updated_live")

    def test_unlink_package(self) -> None:
        """Verify unlinking removes configuration and cleans bootstrap."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            lib_dir = base_dir / "tool_pkg"
            lib_dir.mkdir()
            (lib_dir / "pyproject.toml").write_text(
                '[project]\nname = "tool-pkg"\nversion = "0.1.0"\n',
                encoding="utf-8",
            )

            proj_dir = base_dir / "proj"
            proj_dir.mkdir()
            (proj_dir / "vnma.toml").write_text('[project]\nname = "proj"\n\n[dependencies]\n', encoding="utf-8")

            context = ProjectContext(start_path=proj_dir)
            context.ensure_directories()
            manager = LinkManager(context)

            manager.link(str(lib_dir))
            self.assertEqual(len(manager.get_linked_specs()), 1)

            unlinked = manager.unlink("tool-pkg")
            self.assertIsNotNone(unlinked)
            self.assertEqual(unlinked.name, "tool-pkg")
            self.assertEqual(len(manager.get_linked_specs()), 0)

            cfg = ConfigHandler.load(context.config_path)
            self.assertNotIn("tool-pkg", cfg.dependencies)

    def test_broken_link_verification_and_alert_formatting(self) -> None:
        """Verify missing linked directories are detected and formatted in an aesthetic alert."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            lib_dir = base_dir / "ephemeral_lib"
            lib_dir.mkdir()

            proj_dir = base_dir / "proj"
            proj_dir.mkdir()
            (proj_dir / "vnma.toml").write_text('[project]\nname = "proj"\n\n[dependencies]\n', encoding="utf-8")

            context = ProjectContext(start_path=proj_dir)
            context.ensure_directories()
            manager = LinkManager(context)

            manager.link(str(lib_dir))
            self.assertEqual(len(manager.verify_links()), 0)

            import shutil
            shutil.rmtree(lib_dir)

            broken = manager.verify_links()
            self.assertEqual(len(broken), 1)
            self.assertEqual(broken[0][0], "ephemeral-lib")

            alert = manager.render_broken_links_alert(broken)
            self.assertIn("+---", alert)
            self.assertIn("[!]", alert)
            self.assertIn("ephemeral-lib", alert)
            self.assertIn("Restore directory or run 'vnma unlink", alert)


class TestCliLinkCommands(unittest.TestCase):
    """Test CLI commands vnma link, unlink, reload, and run integration."""

    def test_cli_link_and_unlink(self) -> None:
        """Verify CLI link and unlink subcommands."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            lib_dir = base_dir / "sample_plugin"
            lib_dir.mkdir()
            (lib_dir / "vnma_config.toml").write_text(
                '[package]\nname = "sample-plugin"\nversion = "1.0.0"\n',
                encoding="utf-8",
            )

            proj_dir = base_dir / "cli_app"
            proj_dir.mkdir()
            (proj_dir / "vnma.toml").write_text('[project]\nname = "cli_app"\n\n[dependencies]\n', encoding="utf-8")

            context = ProjectContext(start_path=proj_dir)
            context.ensure_directories()
            parser = build_parser()

            link_args = parser.parse_args(["link", str(lib_dir)])
            ret_link = link_args.handler(link_args, context)
            self.assertEqual(ret_link, 0)

            unlink_args = parser.parse_args(["unlink", "sample-plugin"])
            ret_unlink = unlink_args.handler(unlink_args, context)
            self.assertEqual(ret_unlink, 0)

    def test_cmd_run_aborts_cleanly_on_broken_link(self) -> None:
        """Verify vnma run halts with aesthetic warning if a linked path is missing."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            lib_dir = base_dir / "gone_lib"
            lib_dir.mkdir()

            proj_dir = base_dir / "app"
            proj_dir.mkdir()
            (proj_dir / "vnma.toml").write_text('[project]\nname = "app"\n\n[dependencies]\n', encoding="utf-8")

            context = ProjectContext(start_path=proj_dir)
            context.ensure_directories()
            LinkManager(context).link(str(lib_dir))

            import shutil
            shutil.rmtree(lib_dir)

            parser = build_parser()
            run_args = parser.parse_args(["run"])
            code = run_args.handler(run_args, context)
            self.assertEqual(code, 1)

    def test_cmd_reload_prunes_orphans(self) -> None:
        """Verify vnma reload reconciles dependency graph and cleans orphaned packages."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            proj_dir = base_dir / "app"
            proj_dir.mkdir()
            vendor_dir = proj_dir / "vendor"
            meta_dir = vendor_dir / ".vnma_meta"
            meta_dir.mkdir(parents=True, exist_ok=True)
            (proj_dir / "vnma.toml").write_text('[project]\nname = "app"\n\n[dependencies]\n', encoding="utf-8")

            orphan_dir = vendor_dir / "unused_pkg"
            orphan_dir.mkdir()
            (orphan_dir / "unused.py").write_text("x = 1\n", encoding="utf-8")

            manifest = VnmaManifest(
                python_version="3.14.0",
                packages={
                    "unused-pkg": InstalledPackageRecord(
                        name="unused-pkg",
                        version="1.0.0",
                        wheel_filename="unused_pkg-1.0.0-py3-none-any.whl",
                        files=[InstalledFile(relative_path="unused_pkg/unused.py", sha256="", size_bytes=6)],
                    )
                },
            )
            import json
            (meta_dir / "manifest.json").write_text(json.dumps(manifest.to_dict()), encoding="utf-8")

            context = ProjectContext(start_path=proj_dir)
            parser = build_parser()
            reload_args = parser.parse_args(["reload"])
            ret = reload_args.handler(reload_args, context)

            self.assertEqual(ret, 0)
            self.assertFalse((vendor_dir / "unused_pkg").exists())


if __name__ == "__main__":
    unittest.main()
