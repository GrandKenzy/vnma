"""Unit tests for cross-platform portable path resolution."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from vnma.core.path_resolver import PortablePathResolver


class TestPortablePathResolver(unittest.TestCase):
    """Test user home, environment variables, and session portability conversions."""

    def test_expand_tilde_and_percent_user(self) -> None:
        """Verify ~ and %user% tokens expand to the current user home directory."""
        home = Path.home().resolve()

        resolved_tilde = PortablePathResolver.expand("~/Documents/test_lib")
        self.assertEqual(resolved_tilde, home / "Documents" / "test_lib")

        resolved_percent = PortablePathResolver.expand("%user%/Documents/test_lib")
        self.assertEqual(resolved_percent, home / "Documents" / "test_lib")

        resolved_percent_upper = PortablePathResolver.expand("%USER%/Documents/test_lib")
        self.assertEqual(resolved_percent_upper, home / "Documents" / "test_lib")

    def test_expand_with_base_dir(self) -> None:
        """Verify relative paths resolve against provided base directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            resolved = PortablePathResolver.expand("sub/folder", base_dir=base)
            self.assertEqual(resolved, (base / "sub" / "folder").resolve())

    def test_to_portable_string_home_relative(self) -> None:
        """Verify paths inside user profile serialize to ~/ relative representations."""
        home = Path.home().resolve()
        target = home / "Desktop" / "SampleRepo"
        portable = PortablePathResolver.to_portable_string(target)
        self.assertEqual(portable, "~/Desktop/SampleRepo")

    def test_to_portable_string_project_relative(self) -> None:
        """Verify paths inside base directory serialize to project relative representations."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            target = base / "packages" / "plugin"
            portable = PortablePathResolver.to_portable_string(target, base_dir=base)
            self.assertEqual(portable, "packages/plugin")

    def test_to_portable_string_preserves_simple_relative(self) -> None:
        """Verify already relative module identifiers remain unmodified."""
        self.assertEqual(PortablePathResolver.to_portable_string("core_modules"), "core_modules")
        self.assertEqual(PortablePathResolver.to_portable_string("src"), "src")


if __name__ == "__main__":
    unittest.main()
