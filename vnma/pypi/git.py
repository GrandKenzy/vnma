"""Git repository cloner and cache manager for remote package sources."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
from pathlib import Path


class GitCloneError(RuntimeError):
    """Raised when cloning a remote git repository fails."""


class GitCloner:
    """Clones or updates remote git repositories into local cache."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        """Initialize git cache directory."""
        if cache_dir is None:
            self._cache_dir = Path.home() / ".vnma" / "cache" / "git"
        else:
            self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_rmtree(target_dir: Path) -> None:
        """Recursively remove a directory clearing read-only attributes on Windows."""
        if not target_dir.exists():
            return

        def _handle_readonly(func, path, exc_info):
            try:
                os.chmod(path, stat.S_IWRITE)
                func(path)
            except Exception:
                pass

        shutil.rmtree(target_dir, onerror=_handle_readonly)
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)

    def fetch_repository(self, git_url: str, git_ref: str = "main") -> Path:
        """Clone or update target git reference into cached workspace."""
        hasher = hashlib.sha256()
        hasher.update(git_url.strip().encode("utf-8"))
        hasher.update(git_ref.strip().encode("utf-8"))
        repo_hash = hasher.hexdigest()[:16]

        repo_dir = self._cache_dir / repo_hash

        if (repo_dir / ".git").is_dir():
            fetch_cmd = ["git", "fetch", "--depth", "1", "origin", git_ref]
            res = subprocess.run(fetch_cmd, cwd=str(repo_dir), capture_output=True, text=True)
            if res.returncode == 0:
                subprocess.run(
                    ["git", "checkout", "-B", git_ref, "FETCH_HEAD"],
                    cwd=str(repo_dir),
                    capture_output=True,
                )
                subprocess.run(
                    ["git", "clean", "-fdx"],
                    cwd=str(repo_dir),
                    capture_output=True,
                )
                return repo_dir

        self._safe_rmtree(repo_dir)

        cmd = [
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            git_ref,
            git_url,
            str(repo_dir),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            self._safe_rmtree(repo_dir)
            fallback_cmd = ["git", "clone", git_url, str(repo_dir)]
            fallback_res = subprocess.run(fallback_cmd, capture_output=True, text=True)
            if fallback_res.returncode != 0:
                raise GitCloneError(
                    f"Failed to clone git repository {git_url} (ref: {git_ref}):\n"
                    f"{fallback_res.stderr or result.stderr or result.stdout}"
                )
            subprocess.run(["git", "checkout", git_ref], cwd=str(repo_dir), capture_output=True)

        return repo_dir
