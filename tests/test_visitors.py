"""Unit tests for artifact and project visitors including IDE integration and git configuration."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from vnma.core.cleaner import WorkspaceCleaner
from vnma.core.context import ProjectContext
from vnma.core.errors import ArtifactError
from vnma.visitors.artifact_visitors import BinaryDetectorVisitor, ScriptWrapperVisitor
from vnma.visitors.base import ArtifactElement
from vnma.visitors.git_visitors import GitignoreVisitor
from vnma.visitors.ide_visitors import VSCodeConfigVisitor, loads_jsonc


class TestArtifactVisitors(unittest.TestCase):
    """Test artifact visitor behavior on binary files and DLL collision detection."""

    def test_binary_detector_discovery(self) -> None:
        """Verify detector identifies native binaries and tracks directories."""
        detector = BinaryDetectorVisitor()
        artifact_dll = ArtifactElement(
            relative_path=Path("mypkg/libs/engine.dll"),
            absolute_path=Path("C:/dummy/mypkg/libs/engine.dll"),
            sha256="abc123sha",
            size_bytes=1024,
            is_data_script=False,
        )
        artifact_py = ArtifactElement(
            relative_path=Path("mypkg/__init__.py"),
            absolute_path=Path("C:/dummy/mypkg/__init__.py"),
            sha256="def456sha",
            size_bytes=256,
            is_data_script=False,
        )

        detector.visit_artifact(artifact_py)
        self.assertFalse(detector.has_binaries)
        self.assertEqual(detector.dll_directories, [])

        detector.visit_artifact(artifact_dll)
        self.assertTrue(detector.has_binaries)
        self.assertEqual(detector.dll_directories, ["mypkg/libs"])

    def test_cli_wrappers_do_not_embed_staging_paths(self) -> None:
        """Generated wrappers locate vendor relative to their executable."""
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp) / ".vnma-stage-abcd"
            bin_dir = stage / ".vnma_meta" / ".bin"
            scripts = ScriptWrapperVisitor(bin_dir, stage)
            scripts._generate_executable_wrapper("gram", "gram.__main__:main")
            sh = (bin_dir / "gram").read_text(encoding="utf-8")
            cmd = (bin_dir / "gram.cmd").read_text(encoding="utf-8")
            self.assertIn("VNMA_VENDOR", sh)
            self.assertIn("VNMA_VENDOR", cmd)
            self.assertNotIn(str(stage), sh)
            self.assertNotIn(str(stage), cmd)
            self.assertNotIn(" -c ", sh)
            self.assertNotIn(" -c ", cmd)

    def test_cli_wrapper_rejects_shell_injection_metadata(self) -> None:
        """Wheel metadata cannot inject shell syntax into generated launchers."""
        with tempfile.TemporaryDirectory() as temp:
            bin_dir = Path(temp) / ".vnma_meta" / ".bin"
            scripts = ScriptWrapperVisitor(bin_dir, Path(temp))
            with self.assertRaises(ArtifactError):
                scripts._generate_executable_wrapper("bad&whoami", "pkg:main")
            with self.assertRaises(ArtifactError):
                scripts._generate_executable_wrapper("safe", "pkg:main;__import__('os')")

    def test_dll_collision_detection(self) -> None:
        """Verify collision is flagged when two packages extract different DLL versions."""
        existing_hashes = {"libsdl2.dll": ("original_sha_123", "sdl-base")}
        detector = BinaryDetectorVisitor(existing_dll_hashes=existing_hashes)

        artifact = ArtifactElement(
            relative_path=Path("other/libsdl2.dll"),
            absolute_path=Path("C:/dummy/other/libsdl2.dll"),
            sha256="different_sha_456",
            size_bytes=2048,
            is_data_script=False,
        )
        detector.visit_artifact(artifact)

        self.assertEqual(len(detector.collisions), 1)
        self.assertIn("DLL collision detected for 'libsdl2.dll'", detector.collisions[0])


class TestProjectVisitors(unittest.TestCase):
    """Test project-level visitors for IDE configuration and git ignore updating."""

    def test_loads_jsonc_handling(self) -> None:
        """Verify JSON with comments and trailing commas is parsed safely."""
        jsonc_data = """
        {
            // Line comment
            "python.analysis.extraPaths": [
                "./existing",
            ], /* Block comment */
        }
        """
        parsed = loads_jsonc(jsonc_data)
        self.assertIn("python.analysis.extraPaths", parsed)
        self.assertEqual(parsed["python.analysis.extraPaths"], ["./existing"])

    def test_vscode_config_visitor_injection(self) -> None:
        """Verify VSCode settings are created or updated with vendor extraPaths."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir)
            (project_dir / "vnma.toml").write_text('[project]\nname="test"\n', encoding="utf-8")
            context = ProjectContext(start_path=project_dir)

            visitor = VSCodeConfigVisitor()
            changed = visitor.visit_project(context)
            self.assertTrue(changed)

            settings_file = project_dir / ".vscode" / "settings.json"
            self.assertTrue(settings_file.is_file())

            settings = json.loads(settings_file.read_text(encoding="utf-8"))
            self.assertIn("./vendor", settings.get("python.analysis.extraPaths", []))

    def test_vscode_config_visitor_linked_packages_and_cleanup(self) -> None:
        """Verify linked packages resolve to relative and absolute extraPaths while pruning userHome."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            lib_dir = base_dir / "external_pkg"
            lib_dir.mkdir()
            (lib_dir / "pyproject.toml").write_text('[project]\nname="external-pkg"\nversion="1.0.0"\n', encoding="utf-8")
            (lib_dir / "external_pkg").mkdir()
            (lib_dir / "external_pkg" / "__init__.py").write_text("x = 1\n", encoding="utf-8")

            project_dir = base_dir / "my_project"
            project_dir.mkdir()
            vscode_dir = project_dir / ".vscode"
            vscode_dir.mkdir()
            stale_settings = {
                "python.analysis.extraPaths": ["./vendor", "${userHome}/old/path"],
                "python.autoComplete.extraPaths": ["./vendor", "${userHome}/old/path"],
            }
            (vscode_dir / "settings.json").write_text(json.dumps(stale_settings), encoding="utf-8")

            lib_posix = lib_dir.resolve().as_posix()
            (project_dir / "vnma.toml").write_text(
                f'[project]\nname="my_project"\n\n[dependencies]\nexternal-pkg = {{ path = "{lib_posix}", editable = true }}\n',
                encoding="utf-8",
            )
            context = ProjectContext(start_path=project_dir)

            visitor = VSCodeConfigVisitor()
            changed = visitor.visit_project(context)
            self.assertTrue(changed)

            updated_settings = json.loads((vscode_dir / "settings.json").read_text(encoding="utf-8"))
            extra_paths = updated_settings["python.analysis.extraPaths"]
            self.assertIn("./vendor", extra_paths)
            self.assertNotIn("${userHome}/old/path", extra_paths)
            self.assertTrue(any("external_pkg" in p for p in extra_paths))

    def test_gitignore_visitor_idempotency(self) -> None:
        """Verify gitignore entries are added only once."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir)
            (project_dir / "vnma.toml").write_text('[project]\nname="test"\n', encoding="utf-8")
            context = ProjectContext(start_path=project_dir)

            visitor = GitignoreVisitor()
            first_run = visitor.visit_project(context)
            self.assertTrue(first_run)

            second_run = visitor.visit_project(context)
            self.assertFalse(second_run)

    def test_gitignore_visitor_smart_partial_append_and_cycles(self) -> None:
        """Verify existing lines remain intact, only missing entries are appended, and install/uninstall cycles do not grow the file."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir)
            (project_dir / "vnma.toml").write_text('[project]\nname="test"\n', encoding="utf-8")
            gitignore = project_dir / ".gitignore"
            initial_user_content = "__pycache__/\n*.pyc\nvendor/ # user comment\n.env\n"
            gitignore.write_text(initial_user_content, encoding="utf-8")

            context = ProjectContext(start_path=project_dir)
            visitor = GitignoreVisitor()
            cleaner = WorkspaceCleaner(context)

            # First visit: 'vendor/' is already present, so only the remaining 4 should be added
            changed = visitor.visit_project(context)
            self.assertTrue(changed)

            after_first = gitignore.read_text(encoding="utf-8")
            self.assertTrue(after_first.startswith(initial_user_content))
            self.assertNotIn("\n/vendor/\n", after_first)
            self.assertIn("/vendor_vnma/\n", after_first)
            self.assertIn(".vnma_meta/\n", after_first)
            self.assertIn("vnma_cache/\n", after_first)
            self.assertIn("vnma_skills.md\n", after_first)
            self.assertEqual(after_first.count(GitignoreVisitor.MARKER_HEADER), 1)

            # Simulate repeated uninstall/install cycles
            for _ in range(5):
                cleaner.purge(keep_config=True)
                self.assertFalse(visitor.visit_project(context))

            self.assertEqual(gitignore.read_text(encoding="utf-8"), after_first)

            # Simulate user deleting a single VNMA entry; only that entry should be re-added without duplicating header
            modified = after_first.replace("vnma_cache/\n", "")
            gitignore.write_text(modified, encoding="utf-8")

            self.assertTrue(visitor.visit_project(context))
            after_repair = gitignore.read_text(encoding="utf-8")
            self.assertEqual(after_repair.count(GitignoreVisitor.MARKER_HEADER), 1)
            self.assertEqual(after_repair.count("vnma_cache/"), 1)
            self.assertTrue(after_repair.endswith("vnma_cache/\n"))


if __name__ == "__main__":
    unittest.main()
