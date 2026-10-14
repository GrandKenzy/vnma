"""Visitor patterns and visitable elements for VNMA processing pipelines."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vnma.core.context import ProjectContext


@dataclass(slots=True, frozen=True)
class ArtifactElement:
    """Represents an artifact file inside a distribution wheel or vendor directory."""

    relative_path: Path
    absolute_path: Path
    sha256: str = ""
    size_bytes: int = 0
    is_data_script: bool = False


class ArtifactVisitor(ABC):
    """Abstract visitor defining operations on unpacked artifact elements."""

    @abstractmethod
    def visit_artifact(self, artifact: ArtifactElement) -> None:
        """Process an individual artifact element."""
        raise NotImplementedError


class VisitableArtifact(ABC):
    """Protocol for entities that can accept an ArtifactVisitor."""

    @abstractmethod
    def accept(self, visitor: ArtifactVisitor) -> None:
        """Accept an artifact visitor."""
        raise NotImplementedError


class ProjectVisitor(ABC):
    """Abstract visitor for inspecting or configuring the project workspace."""

    @abstractmethod
    def visit_project(self, context: ProjectContext) -> Any:
        """Execute project-level mutation or inspection."""
        raise NotImplementedError


class VisitableProject(ABC):
    """Protocol for project contexts accepting project-level visitors."""

    @abstractmethod
    def accept(self, visitor: ProjectVisitor) -> Any:
        """Accept a project visitor."""
        raise NotImplementedError
