"""Dependency resolution, interval algebra, and diamond conflict detection."""

from __future__ import annotations

import re
import sys
from collections import deque
from typing import Sequence

from vnma.core.models import PackageSpec, WheelRelease, normalize_package_name
from vnma.core.platform_tags import PlatformTagMatcher
from vnma.pypi.client import PyPIClient

try:
    from packaging.markers import Marker
    from packaging.specifiers import SpecifierSet
    from packaging.version import Version
except ImportError:
    Marker = None
    SpecifierSet = None
    Version = None


class DependencyConflictError(RuntimeError):
    """Raised when an unresolvable diamond dependency conflict (empty intersection) occurs."""


class WheelResolver:
    """Selects optimal platform-compatible wheels and resolves transitive dependency DAGs."""

    def __init__(
        self,
        client: PyPIClient | None = None,
        tag_matcher: PlatformTagMatcher | None = None,
    ) -> None:
        """Initialize resolver with PyPI client and platform tag evaluator."""
        self._client = client or PyPIClient()
        self._matcher = tag_matcher or PlatformTagMatcher()

    def resolve_wheel(self, spec: PackageSpec) -> WheelRelease:
        """Find the highest version, highest priority compatible wheel for a PackageSpec."""
        exact_version = self._extract_exact_version(spec.specifier)
        releases = self._client.fetch_wheel_releases(spec.name, exact_version)

        if not releases:
            raise ValueError(f"No wheel releases discovered for '{spec.name}' on PyPI")

        compatible_candidates: list[tuple[int, WheelRelease]] = []
        for release in releases:
            if not self._matches_specifier(release.version, spec.specifier):
                continue
            priority = self._matcher.get_tag_priority(release.filename)
            if priority >= 0:
                compatible_candidates.append((priority, release))

        if not compatible_candidates:
            raise DependencyConflictError(
                f"Empty compatible version intersection for '{spec.name}' "
                f"with constraint '{spec.specifier}' on current platform."
            )

        ver_parser = Version if Version is not None else self._parse_version_tuple
        compatible_candidates.sort(
            key=lambda item: (ver_parser(item[1].version), -item[0]),
            reverse=True,
        )
        return compatible_candidates[0][1]

    def resolve_graph(
        self, root_specs: Sequence[PackageSpec]
    ) -> list[tuple[PackageSpec, WheelRelease]]:
        """Resolve transitive dependency graph with cumulative constraints and retraction."""
        constraints_by_pkg: dict[str, list[tuple[str, str]]] = {}
        extras_by_pkg: dict[str, set[str]] = {}
        resolved_wheels: dict[str, WheelRelease] = {}
        direct_deps: dict[str, list[PackageSpec]] = {}

        queue: deque[tuple[PackageSpec, str]] = deque((s, "root") for s in root_specs)

        while queue:
            current_spec, requester = queue.popleft()
            pkg = normalize_package_name(current_spec.name)

            constraints_by_pkg.setdefault(pkg, []).append((requester, current_spec.specifier))
            extras_by_pkg.setdefault(pkg, set()).update(current_spec.extras)

            combined_spec_str = ",".join(
                s for _, s in constraints_by_pkg[pkg] if s and s != "*"
            )

            already_resolved = resolved_wheels.get(pkg)
            if already_resolved and self._matches_specifier(already_resolved.version, combined_spec_str):
                active_extras = tuple(sorted(extras_by_pkg[pkg]))
                exact_data = self._client.fetch_package_data(pkg, already_resolved.version)
                raw_reqs = exact_data.get("info", {}).get("requires_dist") or []
                updated_children: list[PackageSpec] = []
                for raw_req in raw_reqs:
                    if not self._evaluate_marker(raw_req, active_extras):
                        continue
                    child_spec = PackageSpec.parse(raw_req)
                    updated_children.append(child_spec)

                new_specs = [c for c in updated_children if c not in direct_deps.get(pkg, [])]
                if new_specs:
                    direct_deps[pkg] = updated_children
                    for child in new_specs:
                        queue.append((child, f"{pkg}=={already_resolved.version}"))
                continue

            merged_spec = PackageSpec(name=pkg, specifier=combined_spec_str)
            try:
                wheel = self.resolve_wheel(merged_spec)
            except DependencyConflictError as err:
                req_summary = " AND ".join(
                    f"{req} requires {pkg}{sp or '*'}" for req, sp in constraints_by_pkg[pkg]
                )
                raise DependencyConflictError(
                    f"Diamond Dependency Conflict on '{pkg}': {req_summary}"
                ) from err

            resolved_wheels[pkg] = wheel
            active_extras = tuple(sorted(extras_by_pkg[pkg]))
            exact_data = self._client.fetch_package_data(pkg, wheel.version)
            raw_reqs = exact_data.get("info", {}).get("requires_dist") or []

            children: list[PackageSpec] = []
            for raw_req in raw_reqs:
                if not self._evaluate_marker(raw_req, active_extras):
                    continue
                child_spec = PackageSpec.parse(raw_req)
                children.append(child_spec)

            direct_deps[pkg] = children
            for child in children:
                queue.append((child, f"{pkg}=={wheel.version}"))

        reachable_pkgs: set[str] = set()
        reach_queue: deque[str] = deque(normalize_package_name(s.name) for s in root_specs)
        for s in root_specs:
            reachable_pkgs.add(normalize_package_name(s.name))

        while reach_queue:
            curr = reach_queue.popleft()
            for child in direct_deps.get(curr, []):
                child_norm = normalize_package_name(child.name)
                if child_norm in resolved_wheels and child_norm not in reachable_pkgs:
                    reachable_pkgs.add(child_norm)
                    reach_queue.append(child_norm)

        final_pairs: list[tuple[PackageSpec, WheelRelease]] = []
        for pkg, whl in resolved_wheels.items():
            if pkg in reachable_pkgs:
                pkg_extras = tuple(sorted(extras_by_pkg.get(pkg, set())))
                final_pairs.append(
                    (PackageSpec(name=pkg, specifier=f"=={whl.version}", extras=pkg_extras), whl)
                )

        return final_pairs

    @staticmethod
    def _evaluate_marker(raw_requirement: str, active_extras: tuple[str, ...]) -> bool:
        """Evaluate PEP 508 environment markers."""
        if ";" not in raw_requirement:
            return True
        _, marker_str = raw_requirement.split(";", 1)
        marker_str = marker_str.strip()

        if Marker is not None:
            if "extra" in marker_str and not active_extras:
                return False
            env = {"extra": active_extras[0] if active_extras else ""}
            return Marker(marker_str).evaluate(environment=env)

        if "extra ==" in marker_str or "extra==" in marker_str:
            return False
        if "sys_platform" in marker_str:
            if f"'{sys.platform}'" not in marker_str and f'"{sys.platform}"' not in marker_str:
                if "==" in marker_str:
                    return False
        return True

    @staticmethod
    def _extract_exact_version(specifier: str) -> str | None:
        """Extract exact version string when pinned with '==' and singular."""
        if specifier.startswith("==") and "," not in specifier:
            return specifier[2:].strip()
        return None

    @classmethod
    def _matches_specifier(cls, version: str, specifier: str) -> bool:
        """Evaluate compound comma-separated version specifiers."""
        if not specifier or specifier == "*":
            return True

        if SpecifierSet is not None and Version is not None:
            try:
                return Version(version) in SpecifierSet(specifier)
            except Exception:
                return False

        clauses = [c.strip() for c in specifier.split(",") if c.strip()]
        v_tuple = cls._parse_version_tuple(version)

        for clause in clauses:
            if clause.startswith("=="):
                if v_tuple != cls._parse_version_tuple(clause[2:]):
                    return False
            elif clause.startswith("!="):
                if v_tuple == cls._parse_version_tuple(clause[2:]):
                    return False
            elif clause.startswith(">="):
                if not (v_tuple >= cls._parse_version_tuple(clause[2:])):
                    return False
            elif clause.startswith("<="):
                if not (v_tuple <= cls._parse_version_tuple(clause[2:])):
                    return False
            elif clause.startswith("~="):
                target = cls._parse_version_tuple(clause[2:])
                upper = (*target[:-2], target[-2] + 1, 0) if len(target) >= 2 else (target[0] + 1, 0)
                if not (target <= v_tuple < upper):
                    return False
            elif clause.startswith(">"):
                if not (v_tuple > cls._parse_version_tuple(clause[1:])):
                    return False
            elif clause.startswith("<"):
                if not (v_tuple < cls._parse_version_tuple(clause[1:])):
                    return False
        return True

    @staticmethod
    def _parse_version_tuple(version_str: str) -> tuple[int, ...]:
        """Convert standard version string into comparable integer tuple."""
        clean = re.sub(r"[^\d.]", "", version_str.strip().split("+")[0])
        nums = [int(p) for p in clean.split(".") if p.isdigit()]
        return tuple(nums) or (0,)
