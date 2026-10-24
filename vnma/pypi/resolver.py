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
        """Resolve a dependency DAG via deterministic bounded backtracking.

        Each decision rebuilds constraints from currently selected versions.
        Discarded versions therefore cannot leave stale transitive constraints.
        """
        from collections import defaultdict

        wheel_cache: dict[str, list[WheelRelease]] = {}
        metadata_cache: dict[tuple[str, str], tuple[str, ...]] = {}
        attempted = 0
        max_decisions = 10000

        def candidates(name: str) -> list[WheelRelease]:
            if name not in wheel_cache:
                releases = self._client.fetch_wheel_releases(name)
                compatible = [
                    release for release in releases
                    if self._matcher.get_tag_priority(release.filename) >= 0
                ]
                version_parser = Version if Version is not None else self._parse_version_tuple
                compatible.sort(
                    key=lambda release: (
                        version_parser(release.version),
                        -self._matcher.get_tag_priority(release.filename),
                    ),
                    reverse=True,
                )
                # Exactly one wheel per version, choosing the best platform tag.
                per_version: dict[str, WheelRelease] = {}
                for release in compatible:
                    per_version.setdefault(release.version, release)
                wheel_cache[name] = list(per_version.values())
            return wheel_cache[name]

        def requirements_for(
            selected: dict[str, WheelRelease],
        ) -> tuple[dict[str, list[tuple[str, str]]], dict[str, set[str]]]:
            constraints: dict[str, list[tuple[str, str]]] = {}
            extras: dict[str, set[str]] = defaultdict(set)
            processed: set[tuple[str, tuple[str, ...]]] = set()
            # Requested dependencies are deduplicated so cyclic graphs terminate.
            seen_edges: set[tuple[str, PackageSpec]] = set()
            queue: deque[tuple[PackageSpec, str]] = deque(
                (spec, "root") for spec in root_specs
            )
            while queue:
                spec, parent = queue.popleft()
                name = normalize_package_name(spec.name)
                edge = (parent, spec)
                if edge in seen_edges:
                    continue
                seen_edges.add(edge)
                constraints.setdefault(name, []).append((parent, spec.specifier))
                extras[name].update(spec.extras)
                if name not in selected:
                    continue
                signature = (name, tuple(sorted(extras[name])))
                if signature in processed:
                    continue
                processed.add(signature)
                wheel = selected[name]
                meta_key = (name, wheel.version)
                if meta_key not in metadata_cache:
                    data = self._client.fetch_package_data(name, wheel.version)
                    metadata_cache[meta_key] = tuple(
                        data.get("info", {}).get("requires_dist") or ()
                    )
                for raw_requirement in metadata_cache[meta_key]:
                    if self._evaluate_marker(raw_requirement, signature[1]):
                        queue.append(
                            (PackageSpec.parse(raw_requirement), f"{name}=={wheel.version}")
                        )
            return constraints, extras

        def solve(
            selected: dict[str, WheelRelease],
        ) -> tuple[dict[str, WheelRelease], dict[str, set[str]], list[str]]:
            nonlocal attempted
            attempted += 1
            if attempted > max_decisions:
                raise DependencyConflictError(
                    f"Dependency resolution exceeded {max_decisions} decisions."
                )

            constraints, extras = requirements_for(selected)
            for name, wheel in selected.items():
                if name not in constraints:
                    continue
                if any(
                    not self._matches_specifier(wheel.version, constraint)
                    for _, constraint in constraints[name]
                ):
                    details = " AND ".join(
                        f"{requester} requires {name}{specifier or '*'}"
                        for requester, specifier in constraints[name]
                    )
                    raise DependencyConflictError(
                        f"Diamond Dependency Conflict on '{name}': {details}"
                    )

            # Remove no-longer-reachable packages before deciding anything else.
            selected = {name: wheel for name, wheel in selected.items() if name in constraints}
            missing = next((name for name in constraints if name not in selected), None)
            if missing is None:
                return selected, extras, list(constraints)

            constraints_for_missing = constraints[missing]
            eligible = [
                release for release in candidates(missing)
                if all(
                    self._matches_specifier(release.version, specifier)
                    for _, specifier in constraints_for_missing
                )
            ]
            if not eligible:
                details = " AND ".join(
                    f"{requester} requires {missing}{specifier or '*'}"
                    for requester, specifier in constraints_for_missing
                )
                raise DependencyConflictError(
                    f"Diamond Dependency Conflict on '{missing}': {details} "
                    "(no compatible wheel)"
                )

            last_error: DependencyConflictError | None = None
            for wheel in eligible:
                try:
                    return solve({**selected, missing: wheel})
                except DependencyConflictError as err:
                    if "exceeded" in str(err):
                        raise
                    last_error = err
            raise last_error or DependencyConflictError(
                f"No compatible dependency graph for '{missing}'."
            )

        if not root_specs:
            return []
        selected, extras, traversal = solve({})
        return [
            (
                PackageSpec(
                    name=name,
                    specifier=f"=={selected[name].version}",
                    extras=tuple(sorted(extras.get(name, set()))),
                ),
                selected[name],
            )
            for name in traversal
            if name in selected
        ]

    @staticmethod
    def _evaluate_marker(raw_requirement: str, active_extras: tuple[str, ...]) -> bool:
        """Evaluate PEP 508 environment markers."""
        if ";" not in raw_requirement:
            return True
        _, marker_str = raw_requirement.split(";", 1)
        marker_str = marker_str.strip()

        if Marker is not None:
            marker = Marker(marker_str)
            # Extras are additive: any requested extra may activate a dependency.
            # Evaluating with an empty extra also preserves regular base markers.
            extras_to_check = active_extras or ("",)
            return any(
                marker.evaluate(environment={"extra": extra})
                for extra in extras_to_check
            )

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
