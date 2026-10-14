"""Unit tests for dependency graph resolution, SemVer matching, and diamond conflict detection."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock

from vnma.core.models import PackageSpec, WheelRelease
from vnma.core.platform_tags import PlatformTagMatcher
from vnma.pypi.resolver import DependencyConflictError, WheelResolver


class MockPyPIClient:
    """Mock PyPI client returning pre-configured releases and package metadata."""

    def __init__(self, packages: dict[str, dict[str, Any]]) -> None:
        """Initialize mock client with package dictionary."""
        self._packages = packages

    def fetch_wheel_releases(
        self, package_name: str, exact_version: str | None = None
    ) -> list[WheelRelease]:
        """Return configured wheel releases for requested package."""
        pkg_data = self._packages.get(package_name, {})
        releases = pkg_data.get("releases", [])
        if exact_version:
            return [r for r in releases if r.version == exact_version]
        return releases

    def fetch_package_data(
        self, package_name: str, version: str | None = None
    ) -> dict[str, Any]:
        """Return mock requires_dist metadata."""
        pkg_data = self._packages.get(package_name, {})
        reqs = pkg_data.get("requires_dist", {}).get(version, [])
        return {"info": {"requires_dist": reqs}}


class TestResolverSpecifierMatching(unittest.TestCase):
    """Test SemVer and range comparison logic."""

    def test_exact_match(self) -> None:
        """Verify exact version matching with ==."""
        self.assertTrue(WheelResolver._matches_specifier("2.0.0", "==2.0.0"))
        self.assertFalse(WheelResolver._matches_specifier("2.0.1", "==2.0.0"))

    def test_compound_intervals(self) -> None:
        """Verify compound lower and upper bounds."""
        spec = ">=1.0.0,<2.0.0"
        self.assertTrue(WheelResolver._matches_specifier("1.0.0", spec))
        self.assertTrue(WheelResolver._matches_specifier("1.9.9", spec))
        self.assertFalse(WheelResolver._matches_specifier("0.9.9", spec))
        self.assertFalse(WheelResolver._matches_specifier("2.0.0", spec))

    def test_compatible_release_tilde(self) -> None:
        """Verify compatible release ~= matching."""
        self.assertTrue(WheelResolver._matches_specifier("1.2.3", "~=1.2.0"))
        self.assertTrue(WheelResolver._matches_specifier("1.2.9", "~=1.2.0"))
        self.assertFalse(WheelResolver._matches_specifier("1.3.0", "~=1.2.0"))
        self.assertFalse(WheelResolver._matches_specifier("1.1.9", "~=1.2.0"))

    def test_exclusion_operator(self) -> None:
        """Verify != excludes specific versions."""
        self.assertTrue(WheelResolver._matches_specifier("2.0.1", "!=2.0.0"))
        self.assertFalse(WheelResolver._matches_specifier("2.0.0", "!=2.0.0"))


class TestEnvironmentMarkers(unittest.TestCase):
    """Test evaluation of PEP 508 environment markers."""

    def test_marker_without_semicolon(self) -> None:
        """Verify requirements without markers always evaluate to True."""
        self.assertTrue(WheelResolver._evaluate_marker("urllib3>=1.26.0", ()))

    def test_extra_marker_filtering(self) -> None:
        """Verify requirements requiring extras are skipped when extra is inactive."""
        req = "socksio>=1.0.0; extra == 'socks'"
        self.assertFalse(WheelResolver._evaluate_marker(req, ()))
        self.assertTrue(WheelResolver._evaluate_marker(req, ("socks",)))


class TestTransitiveGraphResolution(unittest.TestCase):
    """Test resolving dependency DAGs and detecting diamond conflicts."""

    def setUp(self) -> None:
        """Build mock package catalog."""
        self.whl_pkg_a_10 = WheelRelease(
            filename="pkg_a-1.0.0-py3-none-any.whl",
            url="https://fake.url/pkg_a-1.0.0-py3-none-any.whl",
            sha256="abc",
            version="1.0.0",
            python_tag="py3",
            abi_tag="none",
            platform_tag="any",
        )
        self.whl_dep_b_15 = WheelRelease(
            filename="dep_b-1.5.0-py3-none-any.whl",
            url="https://fake.url/dep_b-1.5.0-py3-none-any.whl",
            sha256="def",
            version="1.5.0",
            python_tag="py3",
            abi_tag="none",
            platform_tag="any",
        )
        self.whl_dep_b_20 = WheelRelease(
            filename="dep_b-2.0.0-py3-none-any.whl",
            url="https://fake.url/dep_b-2.0.0-py3-none-any.whl",
            sha256="ghi",
            version="2.0.0",
            python_tag="py3",
            abi_tag="none",
            platform_tag="any",
        )

    def test_successful_transitive_resolution(self) -> None:
        """Verify root package dependencies are recursively discovered and resolved."""
        packages = {
            "pkg-a": {
                "releases": [self.whl_pkg_a_10],
                "requires_dist": {"1.0.0": ["dep-b>=1.0.0"]},
            },
            "dep-b": {
                "releases": [self.whl_dep_b_15],
                "requires_dist": {"1.5.0": []},
            },
        }
        client = MockPyPIClient(packages)
        resolver = WheelResolver(client=client)

        resolved = resolver.resolve_graph([PackageSpec.parse("pkg-a==1.0.0")])
        resolved_names = {spec.name for spec, _ in resolved}
        self.assertIn("pkg-a", resolved_names)
        self.assertIn("dep-b", resolved_names)

    def test_diamond_conflict_detection(self) -> None:
        """Verify diamond conflict between two parents requiring disjoint version ranges."""
        whl_parent_1 = WheelRelease(
            filename="parent_one-1.0.0-py3-none-any.whl",
            url="https://fake.url/p1",
            sha256="111",
            version="1.0.0",
            python_tag="py3",
            abi_tag="none",
            platform_tag="any",
        )
        whl_parent_2 = WheelRelease(
            filename="parent_two-1.0.0-py3-none-any.whl",
            url="https://fake.url/p2",
            sha256="222",
            version="1.0.0",
            python_tag="py3",
            abi_tag="none",
            platform_tag="any",
        )
        packages = {
            "parent-one": {
                "releases": [whl_parent_1],
                "requires_dist": {"1.0.0": ["dep-b<1.8.0"]},
            },
            "parent-two": {
                "releases": [whl_parent_2],
                "requires_dist": {"1.0.0": ["dep-b>=2.0.0"]},
            },
            "dep-b": {
                "releases": [self.whl_dep_b_15, self.whl_dep_b_20],
                "requires_dist": {"1.5.0": [], "2.0.0": []},
            },
        }
        client = MockPyPIClient(packages)
        resolver = WheelResolver(client=client)

        with self.assertRaises(DependencyConflictError) as ctx:
            resolver.resolve_graph(
                [PackageSpec.parse("parent-one"), PackageSpec.parse("parent-two")]
            )

        self.assertIn("Diamond Dependency Conflict", str(ctx.exception))

    def test_version_retraction_prunes_discarded_transitives(self) -> None:
        """Verify that when a version changes, transitives of the discarded version are pruned."""
        whl_app = WheelRelease("app-1.0.0-py3-none-any.whl", "https://app", "1", "1.0.0", "py3", "none", "any")
        whl_limiter = WheelRelease("limiter-1.0.0-py3-none-any.whl", "https://lim", "2", "1.0.0", "py3", "none", "any")
        whl_worker_20 = WheelRelease("worker-2.0.0-py3-none-any.whl", "https://w2", "3", "2.0.0", "py3", "none", "any")
        whl_worker_10 = WheelRelease("worker-1.0.0-py3-none-any.whl", "https://w1", "4", "1.0.0", "py3", "none", "any")
        whl_helper_new = WheelRelease("helper_new-1.0.0-py3-none-any.whl", "https://hn", "5", "1.0.0", "py3", "none", "any")
        whl_helper_old = WheelRelease("helper_old-1.0.0-py3-none-any.whl", "https://ho", "6", "1.0.0", "py3", "none", "any")

        packages = {
            "app": {
                "releases": [whl_app],
                "requires_dist": {"1.0.0": ["worker>=1.0.0"]},
            },
            "limiter": {
                "releases": [whl_limiter],
                "requires_dist": {"1.0.0": ["worker<2.0.0"]},
            },
            "worker": {
                "releases": [whl_worker_20, whl_worker_10],
                "requires_dist": {
                    "2.0.0": ["helper-new==1.0.0"],
                    "1.0.0": ["helper-old==1.0.0"],
                },
            },
            "helper-new": {
                "releases": [whl_helper_new],
                "requires_dist": {"1.0.0": []},
            },
            "helper-old": {
                "releases": [whl_helper_old],
                "requires_dist": {"1.0.0": []},
            },
        }

        client = MockPyPIClient(packages)
        resolver = WheelResolver(client=client)
        resolved = resolver.resolve_graph([PackageSpec.parse("app"), PackageSpec.parse("limiter")])
        resolved_names = {spec.name for spec, _ in resolved}

        self.assertIn("app", resolved_names)
        self.assertIn("limiter", resolved_names)
        self.assertIn("worker", resolved_names)
        self.assertIn("helper-old", resolved_names)
        self.assertNotIn("helper-new", resolved_names)


if __name__ == "__main__":
    unittest.main()

