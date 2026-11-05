"""Search code and markdown files for strings or regular expression patterns."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Sequence

TEXT_EXTENSIONS = {
    ".py",
    ".toml",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".rst",
    ".ini",
    ".cfg",
    ".sh",
    ".bat",
    ".cmd",
    ".ps1",
}

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


def search_pattern_in_files(
    files: Sequence[Path], pattern: str
) -> tuple[list[tuple[str, int, str]], int]:
    """Search for string or regex pattern in provided files.

    Returns (matches, total_files_searched), where each match is
    (file_path_str, line_number, line_preview).
    """
    try:
        regex = re.compile(pattern)
    except re.error:
        # Fall back to literal string search if not a valid regex
        regex = re.compile(re.escape(pattern))

    matches: list[tuple[str, int, str]] = []
    total_searched = 0

    for fpath in files:
        if not fpath.is_file():
            continue

        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        total_searched += 1
        for lineno, line in enumerate(content.splitlines(), start=1):
            if regex.search(line):
                preview = line.strip()
                if len(preview) > 90:
                    preview = preview[:87] + "..."
                matches.append((str(fpath), lineno, preview))

    return matches, total_searched


def render_search_results(
    matches: list[tuple[str, int, str]], pattern: str, total_files: int, project_root: Path
) -> str:
    """Format an aesthetic table displaying search matches."""
    width = 80
    border = "+" + "-" * (width - 2) + "+"

    if not matches:
        return "\n".join([
            border,
            f"| [vnma tools] Search Pattern: '{pattern}'".ljust(width - 1) + "|",
            border,
            f"| No matches found across {total_files} file(s) searched.".ljust(width - 1) + "|",
            border,
        ])

    lines = [
        border,
        f"| [vnma tools] Search Pattern: '{pattern}'".ljust(width - 1) + "|",
        border,
    ]

    for fpath_str, lineno, preview in matches:
        try:
            rel = Path(fpath_str).relative_to(project_root.resolve()).as_posix()
        except ValueError:
            rel = Path(fpath_str).name

        location = f"{rel}:{lineno}"
        content_preview = f" -> {preview}"
        max_line_len = width - 4
        full_line = f"| {location}{content_preview}"
        if len(full_line) > width - 1:
            full_line = full_line[: width - 4] + "..." + "|"
        else:
            full_line = full_line.ljust(width - 1) + "|"
        lines.append(full_line)

    lines.append(border)
    lines.append(f"| Found {len(matches)} match(es) in {total_files} file(s) searched.".ljust(width - 1) + "|")
    lines.append(border)
    return "\n".join(lines)


def run_search(project_root: Path, raw_args: list[str]) -> int:
    """Entry point for the search tool."""
    if any(h in raw_args for h in ("-h", "--help")):
        width = 72
        border = "+" + "-" * (width - 2) + "+"
        print(border)
        print("| [vnma tools] search - Pattern & String Searcher".ljust(width - 1) + "|")
        print(border)
        print("| Usage: vnma tools search \"PATTERN\" [--outputs file1 file2...]".ljust(width - 1) + "|")
        print("| Options:".ljust(width - 1) + "|")
        print("|   -o, --outputs <files/dirs>  Restrict search to specified targets".ljust(width - 1) + "|")
        print(border)
        return 0

    parser = argparse.ArgumentParser(prog="vnma tools search", add_help=False)
    parser.add_argument("pattern", nargs="?", default="")
    parser.add_argument("-o", "--outputs", nargs="*", default=None)

    args, unknown = parser.parse_known_args(raw_args)

    pattern = args.pattern
    outputs = args.outputs or []

    # If pattern wasn't captured by positional (e.g. --search passed as flag), extract from unknowns
    if not pattern:
        for u in unknown:
            if not u.startswith("-"):
                pattern = u
                break

    if not pattern:
        print("[vnma tools] Error: Please provide a search pattern (e.g. vnma tools search 'PATTERN')")
        return 1

    resolved_root = project_root.resolve()
    target_files: list[Path] = []

    if outputs:
        for item in outputs:
            clean_item = item.strip().rstrip(",")
            if not clean_item:
                continue
            p = Path(clean_item)
            if not p.is_absolute():
                p = resolved_root / p
            if p.is_file():
                target_files.append(p.resolve())
            elif p.is_dir():
                for root_dir, dirnames, filenames in os.walk(p.resolve()):
                    dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
                    for fname in filenames:
                        if Path(fname).suffix.lower() in TEXT_EXTENSIONS:
                            target_files.append((Path(root_dir) / fname).resolve())
    else:
        for root_dir, dirnames, filenames in os.walk(resolved_root):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
            for fname in filenames:
                ext = Path(fname).suffix.lower()
                if ext in TEXT_EXTENSIONS:
                    target_files.append((Path(root_dir) / fname).resolve())

    matches, total_files = search_pattern_in_files(target_files, pattern)
    print(render_search_results(matches, pattern, total_files, project_root))
    return 0
