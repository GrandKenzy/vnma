"""Unit tests for WheelArchive extraction, path normalization, and security enforcement."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

from vnma.visitors.base import ArtifactElement, ArtifactVisitor
from vnma.wheel.archive import SecurityError, WheelArchive


class DummyVisitor(ArtifactVisitor):
    """Collector visitor recording all visited artifacts in memory."""

    def __init__(self) -> None:
        """Initialize empty artifact collection."""
        self.visited: list[ArtifactElement] = []

    def visit_artifact(self, artifact: ArtifactElement) -> None:
        """Record artifact element."""
        self.visited.append(artifact)


class TestWheelArchivePaths(unittest.TestCase):
    """Test path sanitization and PEP 427 .data category mapping."""

    def test_standard_purelib_data_mapping(self) -> None:
        """Verify .data/purelib/ paths are flattened to destination root."""
        rel_path, is_script = WheelArchive._normalize_wheel_member_path(
            "sample-1.0.data/purelib/sample/__init__.py"
        )
        self.assertEqual(rel_path, Path("sample/__init__.py"))
        self.assertFalse(is_script)

    def test_platlib_data_mapping(self) -> None:
        """Verify .data/platlib/ paths are flattened to destination root."""
        rel_path, is_script = WheelArchive._normalize_wheel_member_path(
            "sample-1.0.data/platlib/sample/_native.pyd"
        )
        self.assertEqual(rel_path, Path("sample/_native.pyd"))
        self.assertFalse(is_script)

    def test_scripts_data_mapping(self) -> None:
        """Verify .data/scripts/ paths are redirected into metadata scripts directory."""
        rel_path, is_script = WheelArchive._normalize_wheel_member_path(
            "sample-1.0.data/scripts/cli_tool.exe"
        )
        self.assertEqual(
            rel_path, Path(".vnma_meta", ".scripts_raw", "cli_tool.exe")
        )
        self.assertTrue(is_script)

    def test_path_traversal_blocked(self) -> None:
        """Verify entries containing .. raise SecurityError."""
        with self.assertRaises(SecurityError):
            WheelArchive._normalize_wheel_member_path("../outside.py")

        with self.assertRaises(SecurityError):
            WheelArchive._normalize_wheel_member_path("sample/../../outside.py")


class TestWheelArchiveExtraction(unittest.TestCase):
    """Test safe extraction and visitor dispatching."""

    def test_extract_valid_wheel(self) -> None:
        """Verify archive contents are extracted and hash is calculated in one pass."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            wheel_file = tmp_root / "sample-1.0.0-py3-none-any.whl"
            dest_dir = tmp_root / "vendor"

            file_bytes = b"print('hello from vendored package')\n"
            expected_sha = hashlib.sha256(file_bytes).hexdigest()

            with zipfile.ZipFile(wheel_file, "w") as zf:
                zf.writestr("sample/__init__.py", file_bytes)

            archive = WheelArchive(wheel_file)
            visitor = DummyVisitor()
            artifacts = archive.extract_and_visit(dest_dir, [visitor])

            self.assertEqual(len(artifacts), 1)
            self.assertEqual(artifacts[0].sha256, expected_sha)
            self.assertEqual(artifacts[0].size_bytes, len(file_bytes))
            self.assertEqual(len(visitor.visited), 1)

            extracted_file = dest_dir / "sample" / "__init__.py"
            self.assertTrue(extracted_file.is_file())
            self.assertEqual(extracted_file.read_bytes(), file_bytes)


if __name__ == "__main__":
    unittest.main()
