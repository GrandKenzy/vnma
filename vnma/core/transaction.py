"""Workspace-level staging and rollback for VNMA mutations.

A transaction changes only a private vendor tree until the complete command
succeeds. A journal and previous vendor backup allow recovery after crashes.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import uuid
from functools import wraps
from pathlib import Path
from typing import Callable, Any

from vnma.core.context import ProjectContext


class WorkspaceTransaction:
    """Stage vendor operations, commit a whole batch, or restore previous state."""

    JOURNAL = ".vnma-transaction.json"
    LOCK = ".vnma-transaction.lock"
    SIDE_CARS = (
        "vnma.toml", "pyproject.toml", "vnma.lock", ".gitignore",
        ".env", ".vscode/settings.json",
    )

    def __init__(self, context: ProjectContext) -> None:
        self.context = context
        self.root = context.project_root.resolve()
        self.original_vendor = context.vendor_name
        self.target = context.vendor_path.resolve()
        identifier = uuid.uuid4().hex
        self.stage = self.root / f".vnma-stage-{identifier}"
        self.backup = self.root / f".vnma-backup-{identifier}"
        self.journal = self.root / self.JOURNAL
        self.lock = self.root / self.LOCK
        self.snapshots: dict[str, str | None] = {}
        self.existed = False
        self._active = False
        self._aborted = False
        self._committed = False

    @staticmethod
    def _remove_tree(path: Path) -> None:
        if path.is_symlink():
            raise RuntimeError(f"Refusing to remove symlink during recovery: {path}")
        if path.is_dir():
            shutil.rmtree(path)

    @classmethod
    def recover(cls, context: ProjectContext) -> None:
        """Roll back an interrupted transaction if its owning process exited."""
        root = context.project_root.resolve()
        journal_path = root / cls.JOURNAL
        lock_path = root / cls.LOCK
        if not journal_path.is_file():
            if lock_path.exists():
                raise RuntimeError(
                    "VNMA transaction lock exists without a recovery journal; "
                    "check for another running VNMA process before removing it."
                )
            return
        data = json.loads(journal_path.read_text(encoding="utf-8"))
        if lock_path.is_file():
            try:
                pid = int(lock_path.read_text(encoding="ascii").strip())
                os.kill(pid, 0)
            except (OSError, ValueError):
                pass
            else:
                raise RuntimeError(f"VNMA transaction owned by active process {pid}")

        def safe_path(name: str) -> Path:
            if not name or Path(name).is_absolute():
                raise RuntimeError("Unsafe path found in VNMA recovery journal")
            path = root / name
            if not path.resolve().is_relative_to(root) or path.resolve() == root:
                raise RuntimeError("Transaction path escapes workspace")
            return path

        target = safe_path(data["target"])
        backup = safe_path(data["backup"])
        stage = safe_path(data["stage"])
        if data.get("phase") == "committed":
            # Once committed, restoring pre-transaction sidecars would make
            # the new vendor tree disagree with its config and lockfile.
            cls._remove_tree(backup)
            cls._remove_tree(stage)
            journal_path.unlink(missing_ok=True)
            lock_path.unlink(missing_ok=True)
            context.vendor_name = data["target"]
            return
        if backup.exists():
            cls._remove_tree(target)
            backup.rename(target)
        elif not data["existed"] and target.is_dir():
            cls._remove_tree(target)
        # Original vendor may have been untouched when a crash happened in staging.
        cls._remove_tree(stage)
        cls._restore_sidecars(root, data["snapshots"])
        journal_path.unlink(missing_ok=True)
        lock_path.unlink(missing_ok=True)
        # Recover the target chosen before the crash, not an incidental fallback.
        context.vendor_name = data["target"]

    @staticmethod
    def _restore_sidecars(root: Path, snapshots: dict[str, str | None]) -> None:
        for name, payload in snapshots.items():
            path = root / name
            if payload is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(base64.b64decode(payload))

    def _journal(self, phase: str) -> None:
        payload = {
            "phase": phase,
            "target": self.original_vendor,
            "stage": self.stage.name,
            "backup": self.backup.name,
            "existed": self.existed,
            "snapshots": self.snapshots,
        }
        temp = self.journal.with_suffix(".tmp")
        temp.write_text(json.dumps(payload), encoding="utf-8")
        temp.replace(self.journal)

    def __enter__(self) -> WorkspaceTransaction:
        if getattr(self.context, "_transaction_active", False):
            raise RuntimeError("Nested workspace transactions are unsupported")
        self.recover(self.context)
        self.original_vendor = self.context.vendor_name
        self.target = self.context.vendor_path.resolve()
        if (
            self.target == self.root
            or not self.target.is_relative_to(self.root)
            or self.context.vendor_path.is_symlink()
        ):
            raise ValueError("Vendor directory must be inside project workspace")
        try:
            fd = os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="ascii") as stream:
                stream.write(str(os.getpid()))
            self.existed = self.target.exists()
            if self.existed and not self.target.is_dir():
                raise ValueError(f"Vendor path is not a directory: {self.target}")
            self.snapshots = {
                name: (
                    base64.b64encode((self.root / name).read_bytes()).decode("ascii")
                    if (self.root / name).is_file() else None
                )
                for name in self.SIDE_CARS
            }
            self._journal("staging")
            if self.existed:
                shutil.copytree(self.target, self.stage, symlinks=True)
            else:
                self.stage.mkdir()
            self.context.vendor_name = self.stage.name
            self.context._transaction_active = True
            self._active = True
            return self
        except BaseException:
            self.context.vendor_name = self.original_vendor
            self._remove_tree(self.stage)
            self.journal.unlink(missing_ok=True)
            self.lock.unlink(missing_ok=True)
            raise

    def abort(self) -> None:
        """Request rollback after a nonzero CLI return code."""
        self._aborted = True

    def _rollback(self) -> None:
        self.context.vendor_name = self.original_vendor
        self.context._transaction_active = False
        if self.backup.exists():
            self._remove_tree(self.target)
            self.backup.rename(self.target)
        elif not self.existed and self.target.exists():
            self._remove_tree(self.target)
        self._restore_sidecars(self.root, self.snapshots)
        self._remove_tree(self.stage)

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        if not self._active:
            return False
        try:
            if exc_type is not None or self._aborted:
                self._rollback()
            else:
                self._journal("committing")
                if self.existed:
                    self.target.rename(self.backup)
                self.stage.rename(self.target)
                self.context.vendor_name = self.original_vendor
                self.context._transaction_active = False
                # Update IDE settings only after the final vendor path is known.
                from vnma.wheel.installer import WheelInstaller
                WheelInstaller(self.context)._sync_environment()
                self._journal("committed")
                self._committed = True
                self._remove_tree(self.backup)
        except BaseException:
            # A failure *after* durable commit must never restore a partially
            # deleted backup. Keep the journal for cleanup at next invocation.
            if not self._committed:
                self._rollback()
            raise
        finally:
            self.context.vendor_name = self.original_vendor
            self.context._transaction_active = False
            self._remove_tree(self.stage)
            if not self._committed or not self.backup.exists():
                self.journal.unlink(missing_ok=True)
            self.lock.unlink(missing_ok=True)
            self._active = False
        return False


def atomic_workspace_command(function: Callable[..., int]) -> Callable[..., int]:
    """Wrap a mutating CLI command as one all-or-nothing vendor operation."""
    @wraps(function)
    def wrapped(args: Any, context: ProjectContext) -> int:
        with WorkspaceTransaction(context) as txn:
            status = function(args, context)
            if status != 0:
                txn.abort()
            return status
    return wrapped
