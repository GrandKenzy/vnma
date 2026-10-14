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


if __name__ == "__main__":
    unittest.main()
