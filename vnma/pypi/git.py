"""Git repository cloner and cache manager for remote package sources."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
from pathlib import Path

from vnma.core.timeouts import COMMAND_TIMEOUT_SECONDS
from vnma.core.errors import VnmaError


class GitCloneError(VnmaError):
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
                path_obj = Path(path)
                mode = stat.S_IRUSR | stat.S_IWUSR
                if path_obj.is_dir():
                    mode |= stat.S_IXUSR
                os.chmod(path, mode)
                func(path)
            except OSError:
                pass

        shutil.rmtree(target_dir, onerror=_handle_readonly)
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)

    def fetch_repository(self, git_url: str, git_ref: str = "main") -> Path:
        """Clone or update target git reference into cached workspace."""
        clean_url = git_url.strip()
        clean_ref = git_ref.strip()
        if clean_url.startswith("-") or clean_ref.startswith("-"):
            raise GitCloneError(f"Security: Malformed or flag-injected git URL or ref: '{git_url}'")

        hasher = hashlib.sha256()
        hasher.update(clean_url.encode("utf-8"))
        hasher.update(clean_ref.encode("utf-8"))
        repo_hash = hasher.hexdigest()[:16]

        repo_dir = self._cache_dir / repo_hash

        if (repo_dir / ".git").is_dir():
            fetch_cmd = ["git", "fetch", "--depth", "1", "origin", clean_ref]
            res = self._run(fetch_cmd, cwd=repo_dir)
            if res.returncode == 0:
                self._run(
                    ["git", "checkout", "-B", clean_ref, "FETCH_HEAD"],
                    cwd=repo_dir,
                )
                self._run(
                    ["git", "clean", "-fdx"],
                    cwd=repo_dir,
                )
                return repo_dir

        self._safe_rmtree(repo_dir)

        cmd = [
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            clean_ref,
            "--",
            clean_url,
            str(repo_dir),
        ]
        result = self._run(cmd)
        if result.returncode != 0:
            self._safe_rmtree(repo_dir)
            fallback_cmd = ["git", "clone", "--", clean_url, str(repo_dir)]
            fallback_res = self._run(fallback_cmd)
            if fallback_res.returncode != 0:
                raise GitCloneError(
                    f"Failed to clone git repository {git_url} (ref: {git_ref}):\n"
                    f"{fallback_res.stderr or result.stderr or result.stdout}"
                )
            self._run(["git", "checkout", git_ref], cwd=repo_dir)

        return repo_dir

    @staticmethod
    def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        """Run git with a finite upper bound so network operations cannot hang forever."""
        try:
            return subprocess.run(
                cmd,
                cwd=str(cwd) if cwd else None,
                capture_output=True,
                text=True,
                timeout=COMMAND_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as err:
            raise GitCloneError(
                f"Git command timed out after {COMMAND_TIMEOUT_SECONDS} seconds: {cmd[1]}"
            ) from err
