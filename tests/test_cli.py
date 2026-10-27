"""Unit tests for VNMA CLI commands including prune and offline installation."""

from __future__ import annotations

import argparse
import io
import json
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

from vnma.cli import build_parser, cmd_install, cmd_prune, cmd_uninstall, cmd_update
from vnma.core.context import ProjectContext
from vnma.core.lockfile import LockfileHandler
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


class TestCliUpdate(unittest.TestCase):
    """Test vnma update command and user pinning constraints."""

    def test_update_skips_pinned_dependencies(self) -> None:
        """Verify update ignores == pinned dependencies without raising errors."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir)
            (project_dir / "vnma.toml").write_text(
                '[project]\nname="test"\n\n[dependencies]\npinned-pkg = "==1.0.0"\n',
                encoding="utf-8",
            )
            context = ProjectContext(start_path=project_dir)
            args = argparse.Namespace(
                package=None,
                git=False,
                pip=False,
                offline=True,
                find_links=None,
            )

            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cmd_update(args, context)

            self.assertEqual(code, 0)
            self.assertIn("All declared dependencies are pinned or already up to date", buf.getvalue())

    def test_update_respects_git_filter(self) -> None:
        """Verify update with --git skips PyPI dependencies."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir)
            (project_dir / "vnma.toml").write_text(
                '[project]\nname="test"\n\n[dependencies]\npypi-pkg = "*"\n',
                encoding="utf-8",
            )
            context = ProjectContext(start_path=project_dir)
            args = argparse.Namespace(
                package=None,
                git=True,
                pip=False,
                offline=True,
                find_links=None,
            )

            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cmd_update(args, context)

            self.assertEqual(code, 0)
            self.assertIn("All declared dependencies are pinned or already up to date", buf.getvalue())


class TestLockfileRestore(unittest.TestCase):
    """Test reproducible restoration from vnma.lock and determinism."""

    def test_lockfile_restore_exact_from_cache(self) -> None:
        """Verify cmd_install restores directly from vnma.lock when synchronized."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir)
            wheelhouse = project_dir / "wheelhouse"
            wheelhouse.mkdir(parents=True, exist_ok=True)

            wheel_file = wheelhouse / "locked_mod-1.0.0-py3-none-any.whl"
            with zipfile.ZipFile(wheel_file, "w") as zf:
                zf.writestr(
                    "locked_mod-1.0.0.dist-info/METADATA",
                    "Metadata-Version: 2.1\nName: locked-mod\nVersion: 1.0.0\n",
                )
                zf.writestr("locked_mod/__init__.py", "LOCKED = True\n")

            (project_dir / "vnma.toml").write_text(
                '[project]\nname="test"\n\n[dependencies]\nlocked-mod = "==1.0.0"\n',
                encoding="utf-8",
            )

            import hashlib
            hasher = hashlib.sha256()
            with wheel_file.open("rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            whl_sha = hasher.hexdigest()

            lock_payload = {
                "lockfile_version": "1.0",
                "python_version": "3.14.0",
                "packages": {
                    "locked-mod": {
                        "version": "1.0.0",
                        "source": "pypi",
                        "wheel_filename": wheel_file.name,
                        "sha256": whl_sha,
                        "active_extras": [],
                        "has_native_binaries": False,
                        "dll_directories": [],
                        "files_count": 2,
                    }
                },
            }
            (project_dir / "vnma.lock").write_text(json.dumps(lock_payload, indent=2), encoding="utf-8")

            context = ProjectContext(start_path=project_dir)
            args = argparse.Namespace(
                package=None,
                offline=True,
                find_links=str(wheelhouse),
            )

            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cmd_install(args, context)

            self.assertEqual(code, 0)
            self.assertIn("Restoring exact dependencies from vnma.lock", buf.getvalue())
            installed_init = project_dir / "vendor" / "locked_mod" / "__init__.py"
            self.assertTrue(installed_init.is_file())

    def test_lockfile_byte_determinism(self) -> None:
        """Verify LockfileHandler.update produces identical bytes without timestamp volatility."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir)
            vendor_dir = project_dir / "vendor"
            meta_dir = vendor_dir / ".vnma_meta"
            meta_dir.mkdir(parents=True, exist_ok=True)

            (project_dir / "vnma.toml").write_text(
                '[project]\nname="det-test"\n\n[dependencies]\nfoo = "==1.0.0"\n',
                encoding="utf-8",
            )

            manifest = VnmaManifest(
                python_version="3.14.0",
                packages={
                    "foo": InstalledPackageRecord(
                        name="foo",
                        version="1.0.0",
                        wheel_filename="foo-1.0.0-py3-none-any.whl",
                        wheel_sha256="abc12345",
                    )
                },
            )
            (meta_dir / "manifest.json").write_text(json.dumps(manifest.to_dict()), encoding="utf-8")

            context = ProjectContext(start_path=project_dir)
            LockfileHandler.update(context)
            content_first = (project_dir / "vnma.lock").read_bytes()

            import time
            time.sleep(0.01)

            LockfileHandler.update(context)
            content_second = (project_dir / "vnma.lock").read_bytes()

            self.assertEqual(content_first, content_second)

    def test_cmd_run_without_target_runs_default_main(self) -> None:
        """Verify cmd_run resolves and executes default main.py without arguments."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir)
            vendor_dir = project_dir / "vendor"
            meta_dir = vendor_dir / ".vnma_meta"
            meta_dir.mkdir(parents=True, exist_ok=True)
            (project_dir / "vnma.toml").write_text('[project]\nname="test"\n', encoding="utf-8")
            output_file = project_dir / "output.txt"
            main_script = project_dir / "main.py"
            main_script.write_text(
                f"from pathlib import Path\nPath({str(output_file)!r}).write_text('ran_ok', encoding='utf-8')\n",
                encoding="utf-8",
            )

            context = ProjectContext(start_path=project_dir)
            parser = build_parser()
            args = parser.parse_args(["run"])
            code = args.handler(args, context)

            self.assertEqual(code, 0)
            self.assertTrue(output_file.is_file())
            self.assertEqual(output_file.read_text(encoding="utf-8"), "ran_ok")

    def test_cmd_run_with_directory_target(self) -> None:
        """Verify cmd_run resolves main.py inside specified directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir)
            vendor_dir = project_dir / "vendor"
            meta_dir = vendor_dir / ".vnma_meta"
            meta_dir.mkdir(parents=True, exist_ok=True)
            (project_dir / "vnma.toml").write_text('[project]\nname="test"\n', encoding="utf-8")
            src_dir = project_dir / "source"
            src_dir.mkdir(parents=True, exist_ok=True)
            output_file = project_dir / "output_src.txt"
            (src_dir / "main.py").write_text(
                f"from pathlib import Path\nPath({str(output_file)!r}).write_text('ran_source_ok', encoding='utf-8')\n",
                encoding="utf-8",
            )

            context = ProjectContext(start_path=project_dir)
            parser = build_parser()
            args = parser.parse_args(["run", "source"])
            code = args.handler(args, context)

            self.assertEqual(code, 0)
            self.assertTrue(output_file.is_file())
            self.assertEqual(output_file.read_text(encoding="utf-8"), "ran_source_ok")


class TestCliGenerate(unittest.TestCase):
    """Test vnma generate command behavior for project and package manifests."""

    def test_generate_default_vnma_toml(self) -> None:
        """Verify generate creates vnma.toml with folder name, v1.0.0, and expected headers."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir) / "sample_app"
            project_dir.mkdir()

            context = ProjectContext(start_path=project_dir)
            parser = build_parser()
            args = parser.parse_args(["generate"])
            exit_code = args.handler(args, context)

            self.assertEqual(exit_code, 0)
            config_file = project_dir / "vnma.toml"
            self.assertTrue(config_file.is_file())

            content = config_file.read_text(encoding="utf-8")
            self.assertIn('[project]', content)
            self.assertIn('name = "sample_app"', content)
            self.assertIn('version = "1.0.0"', content)
            self.assertIn('[dependencies]', content)
            self.assertIn('[dev-dependencies]', content)
            self.assertIn('[tool.vnma]', content)

    def test_generate_existing_file_without_force(self) -> None:
        """Verify generate errors when target file exists and force is not provided."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir) / "app"
            project_dir.mkdir()
            (project_dir / "vnma.toml").write_text("existing", encoding="utf-8")

            context = ProjectContext(start_path=project_dir)
            parser = build_parser()
            args = parser.parse_args(["generate"])
            exit_code = args.handler(args, context)

            self.assertEqual(exit_code, 1)
            self.assertEqual((project_dir / "vnma.toml").read_text(encoding="utf-8"), "existing")

    def test_generate_existing_file_with_force(self) -> None:
        """Verify generate overwrites target file when force flag is set."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir) / "app"
            project_dir.mkdir()
            (project_dir / "vnma.toml").write_text("existing", encoding="utf-8")

            context = ProjectContext(start_path=project_dir)
            parser = build_parser()
            args = parser.parse_args(["generate", "--force"])
            exit_code = args.handler(args, context)

            self.assertEqual(exit_code, 0)
            content = (project_dir / "vnma.toml").read_text(encoding="utf-8")
            self.assertIn('name = "app"', content)
            self.assertIn('version = "1.0.0"', content)

    def test_generate_package_manifest(self) -> None:
        """Verify generate --package creates vnma_config.toml with expected headers."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir) / "sample_lib"
            project_dir.mkdir()

            context = ProjectContext(start_path=project_dir)
            parser = build_parser()
            args = parser.parse_args(["generate", "--package"])
            exit_code = args.handler(args, context)

            self.assertEqual(exit_code, 0)
            manifest_file = project_dir / "vnma_config.toml"
            self.assertTrue(manifest_file.is_file())

            content = manifest_file.read_text(encoding="utf-8")
            self.assertIn('[package]', content)
            self.assertIn('name = "sample_lib"', content)
            self.assertIn('version = "1.0.0"', content)
            self.assertIn('[runtime]', content)
            self.assertIn('[exports]', content)



class TestDependencyResolverCommandWiring(unittest.TestCase):
    """Verify link and reload construct a usable resolver, not WheelCache as a client."""

    def test_link_uses_default_pypi_client_for_required_dependencies(self) -> None:
        from unittest.mock import patch
        from vnma.core.models import PackageSpec

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "vnma.toml").write_text('[project]\nname = "test"\n', encoding="utf-8")
            context = ProjectContext(start_path=root)
            parser = build_parser()
            args = parser.parse_args(["link", str(root / "linked")])

            with (
                patch("vnma.cli.LinkManager") as managers,
                patch("vnma.cli.WheelResolver") as resolvers,
                patch("vnma.cli.LockfileHandler.update"),
            ):
                managers.return_value.link.return_value = (
                    PackageSpec(name="linked"),
                    [PackageSpec.parse("example-dependency>=1")],
                )
                resolvers.return_value.resolve_graph.return_value = []
                code = args.handler(args, context)
                self.assertEqual(code, 0)
                resolvers.assert_called_once_with()

    def test_reload_uses_default_pypi_client_for_declared_dependencies(self) -> None:
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "vnma.toml").write_text(
                '[project]\nname = "test"\n\n[dependencies]\nexample-dependency = ">=1"\n',
                encoding="utf-8",
            )
            context = ProjectContext(start_path=root)
            parser = build_parser()
            args = parser.parse_args(["reload"])

            with (
                patch("vnma.cli.LinkManager") as managers,
                patch("vnma.cli.WheelResolver") as resolvers,
                patch("vnma.cli.LockfileHandler.update"),
            ):
                managers.return_value.verify_links.return_value = []
                managers.return_value.get_linked_specs.return_value = []
                resolvers.return_value.resolve_graph.return_value = []
                code = args.handler(args, context)
                self.assertEqual(code, 0)
                resolvers.assert_called_once_with()




class TestCliTestCommand(unittest.TestCase):
    """Test vnma test command test discovery and runner invocation."""

    def test_cli_test_discovers_tests_dir(self) -> None:
        """Verify vnma test discovers 'tests' folder."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "tests").mkdir()
            (root / "tests" / "test_sample.py").write_text(
                "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self): pass\n",
                encoding="utf-8"
            )
            context = ProjectContext(start_path=root)
            parser = build_parser()
            args = parser.parse_args(["test"])

            with patch("vnma.runtime.runner.ScriptRunner.run_module", return_value=0) as mock_run:
                code = args.handler(args, context)
                self.assertEqual(code, 0)
                mock_run.assert_called_once()
                call_args = mock_run.call_args[0]
                self.assertIn(call_args[0], ("pytest", "unittest"))

    def test_cli_test_discovers_test_dir_when_tests_absent(self) -> None:
        """Verify vnma test discovers 'test' folder when 'tests' does not exist."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "test").mkdir()
            (root / "test" / "test_sample.py").write_text(
                "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self): pass\n",
                encoding="utf-8"
            )
            context = ProjectContext(start_path=root)
            parser = build_parser()
            args = parser.parse_args(["test"])

            with patch("vnma.runtime.runner.ScriptRunner.run_module", return_value=0) as mock_run:
                code = args.handler(args, context)
                self.assertEqual(code, 0)
                mock_run.assert_called_once()

    def test_cli_test_with_explicit_target_and_args(self) -> None:
        """Verify vnma test forwards explicit file target and flags."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "test").mkdir()
            test_file = root / "test" / "custom.py"
            test_file.write_text("x = 1\n", encoding="utf-8")

            context = ProjectContext(start_path=root)
            parser = build_parser()
            args = parser.parse_args(["test", "test/custom.py", "-v"])

            with patch("vnma.runtime.runner.ScriptRunner.run_module", return_value=0) as mock_run:
                code = args.handler(args, context)
                self.assertEqual(code, 0)
                mock_run.assert_called_once()
                runner_args = mock_run.call_args[0][1]
                self.assertTrue(any("test/custom.py" in str(a) for a in runner_args))
                self.assertIn("-v", runner_args)

    def test_cli_test_no_test_directory_found(self) -> None:
        """Verify vnma test returns error code 1 when no test directory exists."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            context = ProjectContext(start_path=root)
            parser = build_parser()
            args = parser.parse_args(["test"])

            buf = io.StringIO()
            with redirect_stdout(buf):
                code = args.handler(args, context)
            self.assertEqual(code, 1)
            self.assertIn("No test directory", buf.getvalue())



class TestCliInsertImport(unittest.TestCase):
    """Test vnma insert-import command execution, shebang preservation, and idempotency."""

    def test_insert_import_creates_new_file(self) -> None:
        """Verify insert-import creates main.py with bootstrap when target does not exist."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            context = ProjectContext(start_path=root)
            parser = build_parser()
            args = parser.parse_args(["insert-import"])

            buf = io.StringIO()
            with redirect_stdout(buf):
                code = args.handler(args, context)

            self.assertEqual(code, 0)
            target = root / "main.py"
            self.assertTrue(target.is_file())
            content = target.read_text(encoding="utf-8")
            self.assertIn("import vendor.__bootstrap__  # From VNMA.", content)
            self.assertIn("def main() -> None:", content)

    def test_insert_import_existing_file(self) -> None:
        """Verify insert-import injects at top of an existing script."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            target = root / "main.py"
            target.write_text("print('hello')\n", encoding="utf-8")

            context = ProjectContext(start_path=root)
            parser = build_parser()
            args = parser.parse_args(["insert-import"])

            buf = io.StringIO()
            with redirect_stdout(buf):
                code = args.handler(args, context)

            self.assertEqual(code, 0)
            content = target.read_text(encoding="utf-8")
            self.assertTrue(content.startswith("import vendor.__bootstrap__  # From VNMA.\n"))
            self.assertIn("print('hello')", content)

    def test_insert_import_with_shebang(self) -> None:
        """Verify insert-import preserves shebang line and inserts right after it."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            target = root / "main.py"
            target.write_text("#!/usr/bin/env python3\nprint('cli')\n", encoding="utf-8")

            context = ProjectContext(start_path=root)
            parser = build_parser()
            args = parser.parse_args(["insert-import"])

            code = args.handler(args, context)
            self.assertEqual(code, 0)
            lines = target.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0], "#!/usr/bin/env python3")
            self.assertEqual(lines[1], "import vendor.__bootstrap__  # From VNMA.")
            self.assertEqual(lines[2], "print('cli')")

    def test_insert_import_idempotent(self) -> None:
        """Verify running insert-import multiple times does not duplicate the import."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            target = root / "main.py"
            target.write_text("import vendor.__bootstrap__  # From VNMA.\nprint('ok')\n", encoding="utf-8")

            context = ProjectContext(start_path=root)
            parser = build_parser()
            args = parser.parse_args(["insert-import"])

            buf = io.StringIO()
            with redirect_stdout(buf):
                code = args.handler(args, context)

            self.assertEqual(code, 0)
            self.assertIn("already present", buf.getvalue())
            content = target.read_text(encoding="utf-8")
            self.assertEqual(content.count("vendor.__bootstrap__"), 1)

    def test_insert_import_custom_target(self) -> None:
        """Verify insert-import accepts a custom script path."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            custom = root / "cli" / "entry.py"

            context = ProjectContext(start_path=root)
            parser = build_parser()
            args = parser.parse_args(["insert-import", "cli/entry.py"])

            code = args.handler(args, context)
            self.assertEqual(code, 0)
            self.assertTrue(custom.is_file())
            content = custom.read_text(encoding="utf-8")
            self.assertIn("import vendor.__bootstrap__  # From VNMA.", content)


    def test_insert_import_empty_file(self) -> None:
        """Verify insert-import works on an empty file."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            target = root / "main.py"
            target.write_text("", encoding="utf-8")

            context = ProjectContext(start_path=root)
            parser = build_parser()
            args = parser.parse_args(["insert-import"])

            code = args.handler(args, context)
            self.assertEqual(code, 0)
            content = target.read_text(encoding="utf-8")
            self.assertEqual(content, "import vendor.__bootstrap__  # From VNMA.\n")
            compile(content, str(target), "exec")

    def test_insert_import_future_annotations(self) -> None:
        """Verify bootstrap is placed after from __future__ import annotations."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            target = root / "main.py"
            source = '"""Módulo de ejemplo."""\nfrom __future__ import annotations\n\ndef main() -> None:\n    pass\n'
            target.write_text(source, encoding="utf-8")

            context = ProjectContext(start_path=root)
            parser = build_parser()
            args = parser.parse_args(["insert-import"])

            code = args.handler(args, context)
            self.assertEqual(code, 0)
            content = target.read_text(encoding="utf-8")
            compile(content, str(target), "exec")

            lines = content.splitlines()
            self.assertEqual(lines[0], '"""Módulo de ejemplo."""')
            self.assertEqual(lines[1], "from __future__ import annotations")
            self.assertEqual(lines[2], "import vendor.__bootstrap__  # From VNMA.")

    def test_insert_import_multiple_and_multiline_future(self) -> None:
        """Verify bootstrap is placed after multiline and multiple __future__ imports."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            target = root / "main.py"
            source = (
                "from __future__ import (\n"
                "    annotations,\n"
                "    division,\n"
                ")\n"
                "from __future__ import print_function\n"
                "\n"
                "import sys\n"
            )
            target.write_text(source, encoding="utf-8")

            context = ProjectContext(start_path=root)
            parser = build_parser()
            args = parser.parse_args(["insert-import"])

            code = args.handler(args, context)
            self.assertEqual(code, 0)
            content = target.read_text(encoding="utf-8")
            compile(content, str(target), "exec")

            lines = content.splitlines()
            self.assertEqual(lines[4], "from __future__ import print_function")
            self.assertEqual(lines[5], "import vendor.__bootstrap__  # From VNMA.")

    def test_insert_import_shebang_encoding_docstring_future(self) -> None:
        """Verify full header with shebang, encoding, docstring, and __future__."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            target = root / "main.py"
            source = (
                "#!/usr/bin/env python3\n"
                "# -*- coding: utf-8 -*-\n"
                '"""Full header docstring."""\n'
                "from __future__ import annotations\n"
                "\n"
                "import os\n"
            )
            target.write_text(source, encoding="utf-8")

            context = ProjectContext(start_path=root)
            parser = build_parser()
            args = parser.parse_args(["insert-import"])

            code = args.handler(args, context)
            self.assertEqual(code, 0)
            content = target.read_text(encoding="utf-8")
            compile(content, str(target), "exec")

            lines = content.splitlines()
            self.assertEqual(lines[0], "#!/usr/bin/env python3")
            self.assertEqual(lines[1], "# -*- coding: utf-8 -*-")
            self.assertEqual(lines[2], '"""Full header docstring."""')
            self.assertEqual(lines[3], "from __future__ import annotations")
            self.assertEqual(lines[4], "import vendor.__bootstrap__  # From VNMA.")

    def test_insert_import_docstring_with_future_text(self) -> None:
        """Verify docstring containing 'from __future__' text is not confused for AST import."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            target = root / "main.py"
            source = (
                '"""\n'
                'Docstring mentions:\n'
                'from __future__ import annotations\n'
                '"""\n'
                "import os\n"
            )
            target.write_text(source, encoding="utf-8")

            context = ProjectContext(start_path=root)
            parser = build_parser()
            args = parser.parse_args(["insert-import"])

            code = args.handler(args, context)
            self.assertEqual(code, 0)
            content = target.read_text(encoding="utf-8")
            compile(content, str(target), "exec")

            lines = content.splitlines()
            self.assertEqual(lines[4], "import vendor.__bootstrap__  # From VNMA.")
            self.assertEqual(lines[5], "import os")

    def test_insert_import_comments_and_strings_with_bootstrap_keyword(self) -> None:
        """Verify comments or strings with '__bootstrap__' do not trigger false positive."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            target = root / "main.py"
            source = (
                "# Note: __bootstrap__ is mentioned here\n"
                'note = "vendor.__bootstrap__"\n'
            )
            target.write_text(source, encoding="utf-8")

            context = ProjectContext(start_path=root)
            parser = build_parser()
            args = parser.parse_args(["insert-import"])

            code = args.handler(args, context)
            self.assertEqual(code, 0)
            content = target.read_text(encoding="utf-8")
            compile(content, str(target), "exec")
            self.assertIn("import vendor.__bootstrap__  # From VNMA.", content)

            # Second execution must be idempotent and not duplicate
            bytes_before = target.read_bytes()
            code2 = args.handler(args, context)
            self.assertEqual(code2, 0)
            self.assertEqual(target.read_bytes(), bytes_before)

    def test_insert_import_crlf_and_utf8_bom(self) -> None:
        """Verify UTF-8 BOM and CRLF line endings are strictly preserved."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            target = root / "main.py"
            bom = b"\xef\xbb\xbf"
            source_crlf = bom + b"print('crlf')\r\n"
            target.write_bytes(source_crlf)

            context = ProjectContext(start_path=root)
            parser = build_parser()
            args = parser.parse_args(["insert-import"])

            code = args.handler(args, context)
            self.assertEqual(code, 0)
            raw = target.read_bytes()
            self.assertTrue(raw.startswith(bom))
            text_part = raw[3:].decode("utf-8")
            self.assertIn("\r\n", text_part)
            self.assertNotIn("\n\n", text_part.replace("\r\n", "\n"))
            self.assertTrue(text_part.startswith("import vendor.__bootstrap__  # From VNMA.\r\n"))

            # Idempotent second execution
            code2 = args.handler(args, context)
            self.assertEqual(code2, 0)
            self.assertEqual(target.read_bytes(), raw)

    def test_insert_import_invalid_syntax_does_not_modify(self) -> None:
        """Verify file with invalid syntax is not overwritten and returns error code."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            target = root / "main.py"
            source = "def broken(\n"
            target.write_text(source, encoding="utf-8")

            context = ProjectContext(start_path=root)
            parser = build_parser()
            args = parser.parse_args(["insert-import"])

            code = args.handler(args, context)
            self.assertEqual(code, 1)
            self.assertEqual(target.read_text(encoding="utf-8"), source)

    def test_insert_import_misplaced_future_does_not_modify(self) -> None:
        """Verify file with illegally placed __future__ is not modified."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            target = root / "main.py"
            source = "import os\nfrom __future__ import annotations\n"
            target.write_text(source, encoding="utf-8")

            context = ProjectContext(start_path=root)
            parser = build_parser()
            args = parser.parse_args(["insert-import"])

            code = args.handler(args, context)
            self.assertEqual(code, 1)
            self.assertEqual(target.read_text(encoding="utf-8"), source)

if __name__ == "__main__":
    unittest.main()



