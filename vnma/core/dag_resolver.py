"""Transitive DAG resolver supporting diamond dependencies and multi-source packages."""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Sequence

from vnma.core.dependency_inspector import DependencyInspector
from vnma.core.models import PackageSpec, WheelRelease, normalize_package_name
from vnma.pypi.git import GitCloner
from vnma.pypi.resolver import WheelResolver


class ResolutionPlan:
    """Execution plan containing topologically ordered dependencies and source mappings."""

    def __init__(
        self,
        ordered_specs: list[PackageSpec],
        all_resolved_specs: dict[str, PackageSpec],
        pypi_wheel_releases: dict[str, WheelRelease],
    ) -> None:
        self.ordered_specs = ordered_specs
        self.all_resolved_specs = all_resolved_specs
        self.pypi_wheel_releases = pypi_wheel_releases


class TransitiveDagResolver:
    """Resolves transitive dependency graphs with diamond deduplication and root precedence."""

    def __init__(
        self,
        cloner: GitCloner,
        pypi_resolver: WheelResolver,
        offline: bool = False,
    ) -> None:
        self._cloner = cloner
        self._pypi_resolver = pypi_resolver
        self._offline = offline

    def resolve(self, root_specs: Sequence[PackageSpec]) -> ResolutionPlan:
        """Traverse declared dependencies, discover sub-dependencies, and deduplicate diamonds."""
        all_resolved_specs: dict[str, PackageSpec] = {}
        root_spec_names: set[str] = set()
        dependencies_of: dict[str, set[str]] = {}
        pypi_specs_to_resolve: list[PackageSpec] = []
        pypi_wheel_releases: dict[str, WheelRelease] = {}
        visited_sources: set[str] = set()

        queue: deque[tuple[PackageSpec, str | None]] = deque(
            (spec, None) for spec in root_specs
        )

        for spec in root_specs:
            norm = normalize_package_name(spec.name)
            root_spec_names.add(norm)
            all_resolved_specs[norm] = spec

        while queue:
            spec, parent = queue.popleft()
            norm_name = normalize_package_name(spec.name)

            if parent:
                dependencies_of.setdefault(parent, set()).add(norm_name)

            # Diamond check: Root project has precedence; otherwise existing spec wins
            if parent is not None and norm_name in all_resolved_specs:
                continue

            all_resolved_specs[norm_name] = spec

            if spec.git_url:
                source_key = f"git:{spec.git_url}@{spec.git_ref or 'main'}"
                if source_key in visited_sources:
                    continue
                visited_sources.add(source_key)

                repo_path = self._cloner.fetch_repository(spec.git_url, spec.git_ref or "main")
                _, _, child_specs = DependencyInspector.inspect(repo_path)
                for child in child_specs:
                    queue.append((child, norm_name))

            elif spec.path:
                resolved_path = spec.path.resolve()
                source_key = f"path:{resolved_path}"
                if source_key in visited_sources:
                    continue
                visited_sources.add(source_key)

                _, _, child_specs = DependencyInspector.inspect(resolved_path)
                for child in child_specs:
                    queue.append((child, norm_name))

            else:
                pypi_specs_to_resolve.append(spec)

        # Resolve PyPI graph for all collected PyPI requirements
        if pypi_specs_to_resolve:
            resolved_pairs = self._pypi_resolver.resolve_graph(pypi_specs_to_resolve)
            for resolved_spec, wheel_rel in resolved_pairs:
                norm_pypi = normalize_package_name(resolved_spec.name)
                if norm_pypi not in root_spec_names:
                    all_resolved_specs[norm_pypi] = resolved_spec
                pypi_wheel_releases[norm_pypi] = wheel_rel

        # Topological sort: dependencies (leaves) before dependents
        nodes = set(all_resolved_specs.keys())
        in_degree: dict[str, int] = {node: 0 for node in nodes}
        dependents_of: dict[str, set[str]] = {node: set() for node in nodes}

        for parent, children in dependencies_of.items():
            if parent not in nodes:
                continue
            for child in children:
                if child in nodes and child != parent:
                    dependents_of[child].add(parent)
                    in_degree[parent] += 1

        ready: deque[str] = deque([node for node in nodes if in_degree[node] == 0])
        ordered_names: list[str] = []

        while ready:
            curr = ready.popleft()
            ordered_names.append(curr)
            for dep in dependents_of[curr]:
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    ready.append(dep)

        for node in nodes:
            if node not in ordered_names:
                ordered_names.append(node)

        ordered_specs = [all_resolved_specs[name] for name in ordered_names]

        return ResolutionPlan(
            ordered_specs=ordered_specs,
            all_resolved_specs=all_resolved_specs,
            pypi_wheel_releases=pypi_wheel_releases,
        )
