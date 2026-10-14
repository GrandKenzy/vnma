"""Visitor interfaces and concrete implementations for VNMA."""

from vnma.visitors.artifact_visitors import (
    BinaryDetectorVisitor,
    RecordCollectorVisitor,
    ScriptWrapperVisitor,
)
from vnma.visitors.base import (
    ArtifactElement,
    ArtifactVisitor,
    ProjectVisitor,
    VisitableArtifact,
    VisitableProject,
)
from vnma.visitors.git_visitors import GitignoreVisitor
from vnma.visitors.ide_visitors import PyCharmConfigVisitor, VSCodeConfigVisitor

__all__ = [
    "ArtifactElement",
    "ArtifactVisitor",
    "BinaryDetectorVisitor",
    "GitignoreVisitor",
    "ProjectVisitor",
    "PyCharmConfigVisitor",
    "RecordCollectorVisitor",
    "ScriptWrapperVisitor",
    "VSCodeConfigVisitor",
    "VisitableArtifact",
    "VisitableProject",
]
