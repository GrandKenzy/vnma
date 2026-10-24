"""Workspace cleaner for purging VNMA vendored artifacts and workspace configurations."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from vnma.core.context import ProjectContext
from vnma.visitors.git_visitors import GitignoreVisitor
from vnma.visitors.ide_visitors import loads_jsonc


class WorkspaceCleaner:
    """Removes all VNMA vendor trees, lockfiles, and ide integration artifacts from a project."""

    def __init__(self, context: ProjectContext) -> None:
        """Initialize cleaner with project context."""
        self._context = context

    def purge(self, keep_config: bool = False) -> list[str]:
        """Perform complete cleanup of VNMA vendor trees and support files in the project."""
        actions: list[str] = []
        actions.extend(self._clean_vendor_directories())
        actions.extend(self._clean_lockfile())
        actions.extend(self._clean_config(keep_config=keep_config))
        actions.extend(self._clean_ide_settings())
        actions.extend(self._clean_gitignore())
        return actions

    def _clean_vendor_directories(self) -> list[str]:
        """Remove only VNMA-owned vendor directories within the project root.

        Never delete an unrelated vendor/ directory that caused VNMA to use
        vendor_vnma/ instead, or a configured path outside the workspace.
        """
        actions: list[str] = []
        root = self._context.project_root.resolve()
        candidates = [
            self._context.vendor_path,
            root / "vendor",
            root / "vendor_vnma",
        ]
        visited: set[Path] = set()

        for cand in candidates:
            resolved = cand.resolve()
            if resolved in visited:
                continue
            visited.add(resolved)

            if not cand.is_dir():
                continue

            if cand.is_symlink() or resolved == root or not resolved.is_relative_to(root):
                actions.append(f"Skipped unsafe vendor directory '{cand}' (outside workspace or symlink)")
                continue

            # VNMA creates this marker when managing a vendor directory.
            # A directory named 'vendor' alone is never enough to authorize deletion.
            if not (resolved / ".vnma_meta").is_dir():
                actions.append(f"Preserved unmanaged directory '{cand}'")
                continue

            try:
                shutil.rmtree(cand)
            except OSError as err:
                raise RuntimeError(f"Could not remove VNMA vendor directory '{cand}': {err}") from err
            actions.append(f"Removed '{cand.name}/' directory")

        return actions

    def _clean_lockfile(self) -> list[str]:
        """Remove vnma.lock file."""
        actions: list[str] = []
        lock_path = self._context.lock_path
        if lock_path.is_file():
            lock_path.unlink(missing_ok=True)
            actions.append(f"Removed '{lock_path.name}'")
        return actions

    def _clean_config(self, keep_config: bool = False) -> list[str]:
        """Remove vnma.toml or strip [tool.vnma] table from pyproject.toml."""
        actions: list[str] = []
        if keep_config:
            return actions

        config_path = self._context.config_path
        if config_path.is_file():
            config_path.unlink(missing_ok=True)
            actions.append(f"Removed '{config_path.name}'")

        pyproject_path = self._context.pyproject_path
        if pyproject_path.is_file():
            content = pyproject_path.read_text(encoding="utf-8", errors="replace")
            if "[tool.vnma]" in content:
                cleaned = re.sub(
                    r"\[tool\.vnma\][^\[]*",
                    "",
                    content,
                ).strip() + "\n"
                pyproject_path.write_text(cleaned, encoding="utf-8")
                actions.append("Cleaned '[tool.vnma]' from 'pyproject.toml'")

        return actions

    def _clean_ide_settings(self) -> list[str]:
        """Remove VNMA injected paths from VSCode and PyCharm workspace settings."""
        actions: list[str] = []
        root = self._context.project_root

        vscode_file = root / ".vscode" / "settings.json"
        if vscode_file.is_file():
            try:
                settings = loads_jsonc(vscode_file.read_text(encoding="utf-8"))
                modified = False
                for key in ("python.analysis.extraPaths", "python.autoComplete.extraPaths"):
                    if key in settings and isinstance(settings[key], list):
                        filtered = [
                            p for p in settings[key]
                            if not self._is_vnma_path(str(p))
                        ]
                        if len(filtered) != len(settings[key]):
                            modified = True
                        if filtered:
                            settings[key] = filtered
                        else:
                            del settings[key]
                            modified = True

                if modified:
                    if not settings:
                        vscode_file.unlink(missing_ok=True)
                        actions.append("Removed '.vscode/settings.json'")
                        vscode_dir = root / ".vscode"
                        try:
                            if not any(vscode_dir.iterdir()):
                                vscode_dir.rmdir()
                        except OSError:
                            pass
                    else:
                        vscode_file.write_text(json.dumps(settings, indent=4), encoding="utf-8")
                        actions.append("Cleaned VNMA paths from '.vscode/settings.json'")
            except Exception:
                pass

        env_file = root / ".env"
        if env_file.is_file():
            try:
                lines = env_file.read_text(encoding="utf-8", errors="replace").splitlines()
                kept = [
                    line for line in lines
                    if not line.strip().startswith(("PYTHONPATH=./vendor", "PYTHONPATH=./vendor_vnma", "PYTHONPATH=vendor"))
                ]
                clean_body = "\n".join(kept).strip()
                if not clean_body:
                    env_file.unlink(missing_ok=True)
                    actions.append("Removed '.env'")
                elif len(kept) != len(lines):
                    env_file.write_text(clean_body + "\n", encoding="utf-8")
                    actions.append("Cleaned VNMA PYTHONPATH from '.env'")
            except Exception:
                pass

        idea_dir = root / ".idea"
        if idea_dir.is_dir():
            for iml in idea_dir.glob("*.iml"):
                try:
                    text = iml.read_text(encoding="utf-8", errors="replace")
                    cleaned_iml = re.sub(
                        r'\s*<sourceFolder\s+url="file://\$MODULE_DIR\$/(?:vendor|vendor_vnma)"\s+isTestSource="false"\s*/>',
                        "",
                        text,
                    )
                    if cleaned_iml != text:
                        iml.write_text(cleaned_iml, encoding="utf-8")
                        actions.append(f"Cleaned sourceFolder from '{iml.name}'")
                except Exception:
                    pass

        return actions

    def _clean_gitignore(self) -> list[str]:
        """Remove VNMA ignore markers and vendor directory entries from .gitignore."""
        actions: list[str] = []
        gitignore_file = self._context.gitignore_path
        if not gitignore_file.is_file():
            return actions

        try:
            lines = gitignore_file.read_text(encoding="utf-8", errors="replace").splitlines()
            ignored_tokens = set(GitignoreVisitor.ENTRIES) | {"/vendor/", "/vendor_vnma/", ".vnma_meta/", "vnma_cache/", "vendor/", "vendor_vnma/"}
            kept_lines: list[str] = []

            for line in lines:
                stripped = line.strip()
                if stripped == GitignoreVisitor.MARKER_HEADER:
                    continue
                if stripped in ignored_tokens or stripped.strip("/") in [t.strip("/") for t in ignored_tokens]:
                    continue
                kept_lines.append(line)

            remaining_content = "\n".join(kept_lines).strip()
            if not remaining_content:
                gitignore_file.unlink(missing_ok=True)
                actions.append("Removed '.gitignore'")
            elif len(kept_lines) != len(lines):
                gitignore_file.write_text(remaining_content + "\n", encoding="utf-8")
                actions.append("Cleaned VNMA entries from '.gitignore'")
        except Exception:
            pass

        return actions

    def _is_vnma_path(self, path_str: str) -> bool:
        """Check if an IDE path string references VNMA vendor roots or linked user home paths."""
        norm = path_str.replace("\\", "/").strip()
        if norm in ("./vendor", "./vendor_vnma", "vendor", "vendor_vnma"):
            return True
        if norm.startswith(("./vendor/", "./vendor_vnma/", "vendor/", "vendor_vnma/")):
            return True
        if norm.startswith("${userHome}"):
            return True
        vendor_posix = self._context.vendor_path.as_posix()
        if norm == vendor_posix or norm.startswith(f"{vendor_posix}/"):
            return True
        return False
