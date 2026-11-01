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

    @staticmethod
    def _normalize_ignore_rule(rule: str) -> str:
        """Normalize a gitignore rule line to its core target token for comparison."""
        stripped = rule.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("!"):
            return ""
        # Strip inline comments preceded by whitespace
        stripped = re.sub(r"\s+#.*$", "", stripped).strip()
        # Normalize leading/trailing gitignore path wildcards and slashes
        while stripped.startswith(("./", "**/")):
            if stripped.startswith("./"):
                stripped = stripped[2:]
            elif stripped.startswith("**/"):
                stripped = stripped[3:]
        while stripped.endswith(("/**", "/*")):
            stripped = stripped[:-3] if stripped.endswith("/**") else stripped[:-2]
        return stripped.strip("/")

    @classmethod
    def _line_matches_entry(cls, line: str, entry: str) -> bool:
        """Return True if an existing .gitignore line already covers the target entry."""
        norm_line = cls._normalize_ignore_rule(line)
        if not norm_line:
            return False
        norm_entry = cls._normalize_ignore_rule(entry)
        return norm_line == norm_entry

    def visit_project(self, context: ProjectContext) -> bool:
        """Inspect and update project .gitignore idempotently, appending only missing lines at the bottom."""
        gitignore_path = context.gitignore_path

        if not gitignore_path.exists():
            content = f"{self.MARKER_HEADER}\n" + "\n".join(self.ENTRIES) + "\n"
            gitignore_path.write_text(content, encoding="utf-8")
            return True

        original_text = gitignore_path.read_text(encoding="utf-8-sig", errors="replace")
        lines = original_text.splitlines()

        missing_entries: list[str] = []
        for entry in self.ENTRIES:
            if not any(self._line_matches_entry(line, entry) for line in lines):
                missing_entries.append(entry)

        if not missing_entries:
            return False

        # Strictly append only missing entries to the bottom while leaving existing lines intact
        base_content = original_text.rstrip("\r\n")
        has_header = any(line.strip() == self.MARKER_HEADER for line in lines)
        missing_block = "\n".join(missing_entries) + "\n"

        if not base_content.strip():
            new_content = f"{self.MARKER_HEADER}\n{missing_block}"
        elif has_header:
            new_content = f"{base_content}\n{missing_block}"
        else:
            new_content = f"{base_content}\n\n{self.MARKER_HEADER}\n{missing_block}"

        gitignore_path.write_text(new_content, encoding="utf-8")
        return True
