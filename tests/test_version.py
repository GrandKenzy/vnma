"""Check that source, distribution metadata, and clients agree on VNMA version."""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

import vnma
from vnma.pypi.client import PyPIClient


class TestVersionConsistency(unittest.TestCase):
    def test_package_version_matches_pyproject_and_project_manifest(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with (repo_root / "pyproject.toml").open("rb") as stream:
            pyproject = tomllib.load(stream)
        with (repo_root / "vnma.toml").open("rb") as stream:
            project_manifest = tomllib.load(stream)

        self.assertEqual(pyproject["project"]["version"], "0.3.1")
        self.assertEqual(vnma.__version__, "0.3.1")
        self.assertEqual(project_manifest["project"]["version"], "0.3.1")

    def test_pypi_client_reports_current_version(self) -> None:
        self.assertEqual(PyPIClient()._user_agent, f"vnma/{vnma.__version__}")


if __name__ == "__main__":
    unittest.main()
