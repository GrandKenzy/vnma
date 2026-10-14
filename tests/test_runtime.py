"""Unit tests for runtime bootstrap generation and hermetic projection setup."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from vnma.runtime.bootstrap import BootstrapGenerator


class TestBootstrapGenerator(unittest.TestCase):
    """Test generation of runtime loader scripts and static DLL registries."""

    def test_bootstrap_file_generation(self) -> None:
        """Verify __bootstrap__.py, __init__.py, and sitecustomize.py are created."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            vendor_dir = Path(tmp_dir) / "vendor"
            vendor_dir.mkdir(parents=True, exist_ok=True)

            generator = BootstrapGenerator(vendor_dir)
            bootstrap_path = generator.generate(
                dll_subdirectories=["native_pkg/lib64", "audio/dlls"],
                hermetic=True,
            )

            self.assertTrue(bootstrap_path.is_file())
            init_path = vendor_dir / "__init__.py"
            self.assertTrue(init_path.is_file())
            sitecustomize_path = vendor_dir / ".vnma_meta" / "site" / "sitecustomize.py"
            self.assertTrue(sitecustomize_path.is_file())

            content = bootstrap_path.read_text(encoding="utf-8")
            self.assertIn("'native_pkg/lib64'", content)
            self.assertIn("'audio/dlls'", content)
            self.assertIn("_HERMETIC_DEFAULT = True", content)
            self.assertIn("def bootstrap()", content)

            site_content = sitecustomize_path.read_text(encoding="utf-8")
            self.assertIn("import __bootstrap__", site_content)
            self.assertIn("sys.path.insert(0, str(_VENDOR))", site_content)

    def test_bootstrap_extra_module_paths(self) -> None:
        """Verify extra module export paths are recorded in __bootstrap__.py."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            vendor_dir = Path(tmp_dir) / "vendor"
            vendor_dir.mkdir(parents=True, exist_ok=True)

            generator = BootstrapGenerator(vendor_dir)
            bootstrap_path = generator.generate(
                extra_paths=["src", "core_modules"],
                hermetic=False,
            )
            content = bootstrap_path.read_text(encoding="utf-8")
            self.assertIn("_HERMETIC_DEFAULT = False", content)
            self.assertIn("'core_modules'", content)
            self.assertIn("'src'", content)


class TestScriptRunnerIsolation(unittest.TestCase):
    """Test ScriptRunner environment building and hermetic isolation."""

    def test_runner_hermetic_pythonpath(self) -> None:
        """Verify ambient PYTHONPATH is excluded by default but retained when hermetic is 0."""
        import os
        from vnma.core.context import ProjectContext
        from vnma.runtime.runner import ScriptRunner

        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir)
            (project_dir / "vnma.toml").write_text('[project]\nname="test"\n', encoding="utf-8")
            context = ProjectContext(start_path=project_dir)
            runner = ScriptRunner(context)

            old_pp = os.environ.get("PYTHONPATH")
            old_herm = os.environ.get("VNMA_HERMETIC")
            try:
                os.environ["PYTHONPATH"] = "some/external/site"
                os.environ.pop("VNMA_HERMETIC", None)

                env = runner._build_vendor_env()
                self.assertNotIn("some/external/site", env["PYTHONPATH"])
                self.assertEqual(env["PYTHONNOUSERSITE"], "1")

                os.environ["VNMA_HERMETIC"] = "0"
                env_open = runner._build_vendor_env()
                self.assertIn("some/external/site", env_open["PYTHONPATH"])
            finally:
                if old_pp is not None:
                    os.environ["PYTHONPATH"] = old_pp
                else:
                    os.environ.pop("PYTHONPATH", None)
                if old_herm is not None:
                    os.environ["VNMA_HERMETIC"] = old_herm
                else:
                    os.environ.pop("VNMA_HERMETIC", None)


class TestEntryPointResolver(unittest.TestCase):
    """Test resolution of entrypoint scripts, directories, and defaults."""

    def test_resolve_default_root_main(self) -> None:
        """Verify default resolution finds main.py in project root."""
        from vnma.runtime.runner import EntryPointResolver

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            main_file = root / "main.py"
            main_file.write_text("print('hello')", encoding="utf-8")

            resolver = EntryPointResolver(root)
            resolved = resolver.resolve(None)
            self.assertEqual(resolved, main_file.resolve())

    def test_resolve_default_src_main(self) -> None:
        """Verify default resolution finds src/main.py when root has no entry point."""
        from vnma.runtime.runner import EntryPointResolver

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            src_dir = root / "src"
            src_dir.mkdir(parents=True, exist_ok=True)
            main_file = src_dir / "main.py"
            main_file.write_text("print('hello from src')", encoding="utf-8")

            resolver = EntryPointResolver(root)
            resolved = resolver.resolve(None)
            self.assertEqual(resolved, main_file.resolve())

    def test_resolve_directory_target(self) -> None:
        """Verify passing a directory resolves main.py or __main__.py inside it."""
        from vnma.runtime.runner import EntryPointResolver

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_dir = root / "source"
            source_dir.mkdir(parents=True, exist_ok=True)
            main_file = source_dir / "main.py"
            main_file.write_text("print('hello from source')", encoding="utf-8")

            resolver = EntryPointResolver(root)
            resolved = resolver.resolve("source")
            self.assertEqual(resolved, main_file.resolve())

    def test_resolve_explicit_file(self) -> None:
        """Verify passing an explicit script file resolves directly."""
        from vnma.runtime.runner import EntryPointResolver

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            custom_script = root / "test_custom.py"
            custom_script.write_text("print('custom')", encoding="utf-8")

            resolver = EntryPointResolver(root)
            resolved = resolver.resolve("test_custom.py")
            self.assertEqual(resolved, custom_script.resolve())

    def test_resolve_not_found_raises_filenotfounderror(self) -> None:
        """Verify resolving non-existent target or missing defaults raises FileNotFoundError."""
        from vnma.runtime.runner import EntryPointResolver

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            resolver = EntryPointResolver(root)

            with self.assertRaises(FileNotFoundError):
                resolver.resolve(None)

            with self.assertRaises(FileNotFoundError):
                resolver.resolve("non_existent_dir")


if __name__ == "__main__":
    unittest.main()


