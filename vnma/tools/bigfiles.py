"""Analyze and report large files exceeding useful line-of-code thresholds."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Sequence

EXCLUDED_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    ".venv",
    "venv",
    "env",
    ".idea",
    ".vscode",
    "build",
    "dist",
    ".eggs",
}

BINARY_EXTENSIONS = {
    ".dll", ".so", ".dylib", ".pyd", ".exe", ".bin", ".zip", ".whl", ".tar",
    ".gz", ".bz2", ".xz", ".ttf", ".woff", ".woff2", ".webp", ".png", ".jpg",
    ".jpeg", ".ico", ".ppm", ".tif", ".tiff", ".wav", ".mp3", ".ogg", ".xm",
    ".pyc", ".pyo", ".pdf", ".sqlite", ".db",
}


def count_useful_lines(file_path: Path) -> tuple[int, int, int]:
    """Count (useful_lines, comment_lines, blank_lines) for a code file.

    For Python files, excludes empty lines, inline/hash comments,
    and multi-line block docstrings.
    """
    if file_path.suffix.lower() in BINARY_EXTENSIONS:
        return (0, 0, 0)

    try:
        # Quick check for binary files (e.g. null bytes)
        with file_path.open("rb") as f:
            chunk = f.read(1024)
            if b"\x00" in chunk:
                return (0, 0, 0)
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return (0, 0, 0)

    lines = content.splitlines()
    blank_lines = 0
    comment_lines = 0
    useful_lines = 0

    is_py = file_path.suffix.lower() == ".py"
    in_multiline_docstring = False
    docstring_delim = ""

    for line in lines:
        stripped = line.strip()
        if not stripped:
            blank_lines += 1
            continue

        if is_py:
            if in_multiline_docstring:
                comment_lines += 1
                if docstring_delim in stripped:
                    in_multiline_docstring = False
                    docstring_delim = ""
                continue

            if stripped.startswith("#"):
                comment_lines += 1
                continue

            # Check for starting docstrings
            for delim in ('"""', "'''"):
                if stripped.startswith(delim):
                    remainder = stripped[len(delim):]
                    if delim in remainder:
                        comment_lines += 1
                    else:
                        in_multiline_docstring = True
                        docstring_delim = delim
                        comment_lines += 1
                    break
            else:
                useful_lines += 1
        else:
            if stripped.startswith(("#", "//", "/*", "*")):
                comment_lines += 1
            else:
                useful_lines += 1

    return useful_lines, comment_lines, blank_lines


def collect_target_files(project_root: Path, targets: Sequence[str] | None) -> list[Path]:
    """Collect files matching user-specified paths, globs, or defaults."""
    resolved_root = project_root.resolve()
    collected: list[Path] = []
    seen: set[Path] = set()

    if not targets:
        for root_dir, dirnames, filenames in os.walk(resolved_root):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
            for fname in filenames:
                fpath = (Path(root_dir) / fname).resolve()
                if fpath.is_file() and fpath not in seen:
                    seen.add(fpath)
                    collected.append(fpath)
        return collected

    for target in targets:
        clean_target = target.strip().rstrip(",")
        if not clean_target:
            continue

        # Handle glob patterns like "**" or "*.py"
        if any(ch in clean_target for ch in ("*", "?")):
            pattern = clean_target
            if pattern == "**":
                pattern = "**/*"
            for match in resolved_root.glob(pattern):
                if match.is_file():
                    res = match.resolve()
                    if not any(part in EXCLUDED_DIRS for part in res.parts) and res not in seen:
                        seen.add(res)
                        collected.append(res)
            continue

        target_path = Path(clean_target)
        if not target_path.is_absolute():
            target_path = resolved_root / target_path

        resolved_target = target_path.resolve()
        if not resolved_target.is_relative_to(resolved_root):
            continue

        if resolved_target.is_file():
            if resolved_target not in seen:
                seen.add(resolved_target)
                collected.append(resolved_target)
        elif resolved_target.is_dir():
            for root_dir, dirnames, filenames in os.walk(resolved_target):
                dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
                for fname in filenames:
                    fpath = (Path(root_dir) / fname).resolve()
                    if fpath.is_file() and fpath not in seen:
                        seen.add(fpath)
                        collected.append(fpath)

    return collected


def render_bigfiles_table(results: list[tuple[int, int, int, str]], threshold: int, total_scanned: int) -> str:
    """Format an aesthetic table showing files exceeding the threshold."""
    if not results:
        width = 76
        border = "+" + "-" * (width - 2) + "+"
        lines = [
            border,
            f"| [vnma tools] Big Files Audit (Threshold: >= {threshold} useful lines)".ljust(width - 1) + "|",
            border,
            f"| No files exceeded {threshold} useful lines (Total scanned: {total_scanned})".ljust(width - 1) + "|",
            border,
        ]
        return "\n".join(lines)

    max_path_len = max(len(r[3]) for r in results)
    path_col_width = max(max_path_len + 2, 35)
    total_width = 10 + 10 + 12 + path_col_width + 5
    border = "+" + "-" * (total_width - 2) + "+"

    header_title = f"| [vnma tools] Big Files Audit (Threshold: >= {threshold} useful lines)"
    lines = [
        border,
        header_title.ljust(total_width - 1) + "|",
        border,
        f"| {'Useful':<8} | {'Total':<8} | {'Comments':<10} | {'File Path':<{path_col_width}} |",
        border,
    ]

    for useful, total, comments, rel_path in results:
        row = f"| {useful:<8} | {total:<8} | {comments:<10} | {rel_path:<{path_col_width}} |"
        lines.append(row)

    lines.append(border)
    summary = f"| Found {len(results)} file(s) exceeding threshold (Total scanned: {total_scanned})"
    lines.append(summary.ljust(total_width - 1) + "|")
    lines.append(border)
    return "\n".join(lines)


def run_bigfiles(project_root: Path, raw_args: list[str]) -> int:
    """Entry point for the bigfiles tool."""
    if any(h in raw_args for h in ("-h", "--help")):
        width = 72
        border = "+" + "-" * (width - 2) + "+"
        print(border)
        print("| [vnma tools] bigfiles - Useful Line-of-Code Auditor".ljust(width - 1) + "|")
        print(border)
        print("| Usage: vnma tools bigfiles [--l <threshold>] [paths...]".ljust(width - 1) + "|")
        print("| Options:".ljust(width - 1) + "|")
        print("|   -l, --l, --lines <N>  Minimum useful lines threshold (default: 500)".ljust(width - 1) + "|")
        print("|   paths                 Optional files, directories or globs (e.g. **)".ljust(width - 1) + "|")
        print(border)
        return 0

    parser = argparse.ArgumentParser(prog="vnma tools bigfiles", add_help=False)
    parser.add_argument("-l", "--l", "--limit", "--lines", dest="threshold", type=int, default=500)
    parser.add_argument("paths", nargs="*")

    args, unknown = parser.parse_known_args(raw_args)
    all_paths = list(args.paths) + [u for u in unknown if not u.startswith("-")]

    target_files = collect_target_files(project_root, all_paths)
    matching_records: list[tuple[int, int, int, str]] = []

    for fpath in target_files:
        useful, comments, blanks = count_useful_lines(fpath)
        total = useful + comments + blanks
        if useful >= args.threshold:
            try:
                rel_str = str(fpath.relative_to(project_root.resolve())).replace("\\", "/")
            except ValueError:
                rel_str = fpath.name
            matching_records.append((useful, total, comments, rel_str))

    matching_records.sort(key=lambda item: item[0], reverse=True)
    table = render_bigfiles_table(matching_records, args.threshold, len(target_files))
    print(table)
    return 0
