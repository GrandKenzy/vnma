"""Project visitor for automating safe, idempotent .gitignore entries."""

from __future__ import annotations

import re
from pathlib import Path

from typing import TYPE_CHECKING

from vnma.visitors.base import ProjectVisitor

if TYPE_CHECKING:
    from vnma.core.context import ProjectContext


class GitignoreVisitor(ProjectVisitor):
    """Ensures vendor artifact directories are properly ignored by Git."""

    MARKER_HEADER = "# --- VNMA (Vendor Manager) ---"
    ENTRIES = ["/vendor/", "/vendor_vnma/", ".vnma_meta/", "vnma_cache/", "vnma_skills.md"]

    def visit_project(self, context: ProjectContext) -> bool:
        """Inspect and update project .gitignore idempotently, appending to bottom."""
        gitignore_path = context.gitignore_path

        if not gitignore_path.exists():
            content = f"{self.MARKER_HEADER}\n" + "\n".join(self.ENTRIES) + "\n"
            gitignore_path.write_text(content, encoding="utf-8")
            return True

        original_text = gitignore_path.read_text(encoding="utf-8", errors="replace")
        lines = original_text.splitlines()

        missing_entries: list[str] = []
        for entry in self.ENTRIES:
            cleaned = entry.strip("/")
            pattern = re.compile(rf"^\s*/?{re.escape(cleaned)}/?\s*$")
            if not any(pattern.match(line) for line in lines):
                missing_entries.append(entry)

        if not missing_entries:
            return False

        # Strictly append missing entries to the bottom without overwriting existing rules
        new_content = original_text
        if new_content and not new_content.endswith("\n"):
            new_content += "\n"

        if self.MARKER_HEADER not in original_text:
            new_content += f"\n{self.MARKER_HEADER}\n"

        for entry in missing_entries:
            new_content += f"{entry}\n"

        gitignore_path.write_text(new_content, encoding="utf-8")
        return True
