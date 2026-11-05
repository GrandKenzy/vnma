"""Clean and remove __pycache__ folders and compiled python bytecode files."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Sequence


def format_bytes(size: int) -> str:
    """Format byte size into human-readable string."""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.2f} KB"
    else:
        return f"{size / (1024 * 1024):.2f} MB"


def clean_caches(project_root: Path, targets: Sequence[str] | None = None) -> tuple[int, int, int]:
    """Recursively purge __pycache__ directories and .pyc/.pyo files.

    Returns (deleted_dirs_count, deleted_files_count, freed_bytes).
    """
    resolved_root = project_root.resolve()
    dirs_to_clean: list[Path] = []

    if targets:
        for t in targets:
            clean_t = t.strip().rstrip(",")
            if not clean_t:
                continue
            t_path = Path(clean_t)
            if not t_path.is_absolute():
                t_path = resolved_root / t_path
            res = t_path.resolve()
            if res.is_relative_to(resolved_root) and res.is_dir():
                dirs_to_clean.append(res)
    else:
        dirs_to_clean.append(resolved_root)

    deleted_dirs = 0
    deleted_files = 0
    freed_bytes = 0

    for base_dir in dirs_to_clean:
        for root_dir, dirnames, filenames in os.walk(base_dir, topdown=False):
            # Check for __pycache__ folder
            for d in list(dirnames):
                if d == "__pycache__":
                    full_dpath = Path(root_dir) / d
                    if full_dpath.is_dir() and not full_dpath.is_symlink():
                        # Calculate size
                        for r, _, fnames in os.walk(full_dpath):
                            for fname in fnames:
                                fp = Path(r) / fname
                                try:
                                    freed_bytes += fp.stat().st_size
                                    deleted_files += 1
                                except OSError:
                                    pass
                        try:
                            shutil.rmtree(full_dpath)
                            deleted_dirs += 1
                        except OSError:
                            pass

            # Check for standalone .pyc / .pyo files outside __pycache__
            for f in filenames:
                if f.endswith((".pyc", ".pyo")):
                    full_fpath = Path(root_dir) / f
                    if full_fpath.is_file() and not full_fpath.is_symlink():
                        try:
                            freed_bytes += full_fpath.stat().st_size
                            full_fpath.unlink(missing_ok=True)
                            deleted_files += 1
                        except OSError:
                            pass

    return deleted_dirs, deleted_files, freed_bytes


def render_cacheclean_report(deleted_dirs: int, deleted_files: int, freed_bytes: int) -> str:
    """Format an aesthetic alert box with cache cleanup results."""
    width = 72
    border = "+" + "-" * (width - 2) + "+"
    lines = [
        border,
        "| [vnma tools] PyCache Cleaner".ljust(width - 1) + "|",
        border,
        f"| Removed {deleted_dirs} '__pycache__' directory(ies)".ljust(width - 1) + "|",
        f"| Removed {deleted_files} compiled bytecode file(s) (.pyc/.pyo)".ljust(width - 1) + "|",
        f"| Total disk space freed: {format_bytes(freed_bytes)}".ljust(width - 1) + "|",
        border,
    ]
    return "\n".join(lines)


def run_cacheclean(project_root: Path, raw_args: list[str]) -> int:
    """Entry point for the cacheclean tool."""
    if any(h in raw_args for h in ("-h", "--help")):
        width = 72
        border = "+" + "-" * (width - 2) + "+"
        print(border)
        print("| [vnma tools] cacheclean - Bytecode Cache Cleaner".ljust(width - 1) + "|")
        print(border)
        print("| Usage: vnma tools cacheclean [paths...]".ljust(width - 1) + "|")
        print("| Actions:".ljust(width - 1) + "|")
        print("|   Recursively purges __pycache__ folders and .pyc/.pyo files".ljust(width - 1) + "|")
        print(border)
        return 0

    paths = [a for a in raw_args if not a.startswith("-")]
    d_count, f_count, freed = clean_caches(project_root, paths or None)
    print(render_cacheclean_report(d_count, f_count, freed))
    return 0
