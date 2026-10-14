"""Unit tests for platform tag matching and wheel architecture compatibility."""

from __future__ import annotations

import unittest

from vnma.core.platform_tags import PlatformTagMatcher


class TestPlatformTagMatcher(unittest.TestCase):
    """Test wheel filename parsing and host compatibility calculation."""

    def setUp(self) -> None:
        """Create a platform tag matcher instance for current host environment."""
        self.matcher = PlatformTagMatcher()

    def test_parse_valid_wheel_filenames(self) -> None:
        """Verify PEP 427 components are parsed correctly from valid wheel names."""
        parsed = self.matcher.parse_wheel_filename("requests-2.31.0-py3-none-any.whl")
        self.assertIsNotNone(parsed)
        if parsed:
            self.assertEqual(parsed.distribution, "requests")
            self.assertEqual(parsed.version, "2.31.0")
            self.assertEqual(parsed.python_tags, ("py3",))
            self.assertEqual(parsed.abi_tags, ("none",))
            self.assertEqual(parsed.platform_tags, ("any",))

    def test_parse_compressed_multi_tags(self) -> None:
        """Verify wheel names with dot-separated multiple tags are split into tuples."""
        parsed = self.matcher.parse_wheel_filename("six-1.16.0-py2.py3-none-any.whl")
        self.assertIsNotNone(parsed)
        if parsed:
            self.assertEqual(parsed.python_tags, ("py2", "py3"))

    def test_parse_invalid_wheel_filename(self) -> None:
        """Verify non-wheel or malformed filenames return None."""
        self.assertIsNone(self.matcher.parse_wheel_filename("requests-2.31.0.tar.gz"))
        self.assertIsNone(self.matcher.parse_wheel_filename("random_file.txt"))

    def test_pure_python_compatibility(self) -> None:
        """Verify universal pure-Python wheels are always compatible."""
        self.assertTrue(self.matcher.is_wheel_compatible("requests-2.31.0-py3-none-any.whl"))
        self.assertTrue(self.matcher.is_wheel_compatible("six-1.16.0-py2.py3-none-any.whl"))

    def test_incompatible_platform_rejection(self) -> None:
        """Verify foreign platform wheels are rejected."""
        self.assertFalse(
            self.matcher.is_wheel_compatible(
                "mypkg-1.0.0-cp314-cp314-macosx_10_9_x86_64.whl"
            )
        )
        self.assertFalse(
            self.matcher.is_wheel_compatible(
                "mypkg-1.0.0-cp314-cp314-manylinux_2_28_aarch64.whl"
            )
        )

    def test_tag_priority_ordering(self) -> None:
        """Verify compatible wheels produce non-negative priorities and invalid produce -1."""
        priority_any = self.matcher.get_tag_priority("requests-2.31.0-py3-none-any.whl")
        self.assertGreaterEqual(priority_any, 0)

        priority_foreign = self.matcher.get_tag_priority(
            "mypkg-1.0.0-cp314-cp314-manylinux_2_28_aarch64.whl"
        )
        self.assertEqual(priority_foreign, -1)


if __name__ == "__main__":
    unittest.main()
