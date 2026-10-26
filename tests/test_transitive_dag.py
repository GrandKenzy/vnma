"""Unit tests for transitive DAG resolution, diamond dependency deduplication, and VNMA package compatibility."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from vnma.core.dag_resolver import TransitiveDagResolver
from vnma.core.dependency_inspector import DependencyInspector
from vnma.core.models import PackageSpec
from vnma.wheel.builder import SourceBuilder


class TestDependencyInspector(unittest.TestCase):
    """Test dependency extraction across vnma.toml, vnma_config.toml, and pyproject.toml."""

    def test_inspect_vnma_config_with_dependencies(self) -> None:
        """Verify DependencyInspector extracts declared dependencies from vnma_config.toml."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            dir_path = Path(tmp_dir)
            cfg_path = dir_path / "vnma_config.toml"
            cfg_path.write_text(
                '[package]\n'
                'name = "sub-lib"\n'
                'version = "1.2.0"\n\n'
                '[dependencies]\n'
                'shared-dep = ">=1.0.0"\n'
                'git-dep = { git = "https://github.com/org/git-dep.git", branch = "v1" }\n'
                'path-dep = { path = "../local-lib" }\n',
                encoding="utf-8",
            )

            name, modules, deps = DependencyInspector.inspect(dir_path)
            self.assertEqual(name, "sub-lib")
            dep_dict = {d.name: d for d in deps}

            self.assertIn("shared-dep", dep_dict)
            self.assertEqual(dep_dict["shared-dep"].specifier, ">=1.0.0")

            self.assertIn("git-dep", dep_dict)
            self.assertEqual(dep_dict["git-dep"].git_url, "https://github.com/org/git-dep.git")
            self.assertEqual(dep_dict["git-dep"].git_ref, "v1")

            self.assertIn("path-dep", dep_dict)
            self.assertTrue(dep_dict["path-dep"].path is not None)

    def test_inspect_vnma_toml(self) -> None:
        """Verify DependencyInspector extracts dependencies from standard vnma.toml."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            dir_path = Path(tmp_dir)
            (dir_path / "vnma.toml").write_text(
                '[project]\n'
                'name = "my-project"\n'
                'version = "2.0.0"\n\n'
                '[dependencies]\n'
                'helper = ">=0.5.0"\n',
                encoding="utf-8",
            )

            name, modules, deps = DependencyInspector.inspect(dir_path)
            self.assertEqual(name, "my-project")
            self.assertEqual(len(deps), 1)
            self.assertEqual(deps[0].name, "helper")
            self.assertEqual(deps[0].specifier, ">=0.5.0")


class TestTransitiveDagResolver(unittest.TestCase):
    """Test DAG resolution, topological ordering, and diamond deduplication."""

    def test_diamond_dependency_resolution(self) -> None:
        """Verify diamond structure: P1 -> P2 & P3; P3 -> P2.

        P2 should only appear once in resolution, and be ordered before P3.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            p2_dir = root / "proyecto2"
            p3_dir = root / "proyecto3"
            p2_dir.mkdir()
            p3_dir.mkdir()

            (p2_dir / "vnma_config.toml").write_text(
                '[package]\nname = "proyecto2"\nversion = "1.0.0"\n',
                encoding="utf-8",
            )

            (p3_dir / "vnma_config.toml").write_text(
                '[package]\nname = "proyecto3"\nversion = "1.0.0"\n\n'
                '[dependencies]\n'
                'proyecto2 = { path = "../proyecto2" }\n',
                encoding="utf-8",
            )

            mock_cloner = MagicMock()
            mock_resolver = MagicMock()
            mock_resolver.resolve_graph.return_value = []

            dag = TransitiveDagResolver(mock_cloner, mock_resolver)
            root_specs = [
                PackageSpec(name="proyecto2", path=p2_dir),
                PackageSpec(name="proyecto3", path=p3_dir),
            ]

            plan = dag.resolve(root_specs)

            names = [s.name for s in plan.ordered_specs]
            # Diamond check: proyecto2 is deduplicated and appears once
            self.assertEqual(names.count("proyecto2"), 1)
            self.assertEqual(names.count("proyecto3"), 1)

            # Topological check: proyecto2 must be installed before proyecto3
            idx_p2 = names.index("proyecto2")
            idx_p3 = names.index("proyecto3")
            self.assertLess(idx_p2, idx_p3)

    def test_pure_vnma_package_wheel_build(self) -> None:
        """Verify SourceBuilder synthesizes pyproject.toml when only vnma_config.toml exists."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            pkg_dir = root / "pure_vnma_pkg"
            pkg_dir.mkdir()
            (pkg_dir / "pure_vnma_pkg.py").write_text("MSG = 'pure vnma'\n", encoding="utf-8")
            (pkg_dir / "vnma_config.toml").write_text(
                '[package]\n'
                'name = "pure-vnma-pkg"\n'
                'version = "1.0.0"\n'
                'type = "pure-python"\n\n'
                '[exports]\n'
                'modules = ["pure_vnma_pkg"]\n',
                encoding="utf-8",
            )

            out_dir = root / "wheels"
            builder = SourceBuilder(out_dir)

            wheel_path = builder.build_wheel(pkg_dir)
            self.assertTrue(wheel_path.is_file())
            self.assertTrue(wheel_path.name.startswith("pure_vnma_pkg-1.0.0"))
            # Ensure the source directory remains clean without leftover pyproject.toml
            self.assertFalse((pkg_dir / "pyproject.toml").exists())


if __name__ == "__main__":
    unittest.main()
