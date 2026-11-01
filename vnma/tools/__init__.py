"""Developer utilities and project maintenance tools for VNMA."""

from __future__ import annotations

from pathlib import Path

from vnma.tools.bigfiles import run_bigfiles
from vnma.tools.cacheclean import run_cacheclean
from vnma.tools.search import run_search

TOOL_REGISTRY = {
    "bigfiles": run_bigfiles,
    "bifgiles": run_bigfiles,
    "--bigfiles": run_bigfiles,
    "cacheclean": run_cacheclean,
    "--cacheclean": run_cacheclean,
    "clean-cache": run_cacheclean,
    "search": run_search,
    "--search": run_search,
}


def render_tools_help() -> str:
    """Format aesthetic help text for available workspace developer tools."""
    width = 76
    border = "+" + "-" * (width - 2) + "+"
    lines = [
        border,
        "| VNMA Developer Tools & Utilities".ljust(width - 1) + "|",
        border,
        "| Available tools:".ljust(width - 1) + "|",
        "|   * bigfiles   : Report files exceeding useful line-of-code thresholds".ljust(width - 1) + "|",
        "|                  Usage: vnma tools bigfiles [--l 500] [paths...]".ljust(width - 1) + "|",
        "|   * cacheclean : Purge all __pycache__ directories and .pyc/.pyo files".ljust(width - 1) + "|",
        "|                  Usage: vnma tools cacheclean [paths...]".ljust(width - 1) + "|",
        "|   * search     : Search files for strings or regex patterns".ljust(width - 1) + "|",
        "|                  Usage: vnma tools search \"PATTERN\" [--outputs f1 f2...]".ljust(width - 1) + "|",
        border,
    ]
    return "\n".join(lines)


def run_tool(tool_name: str | None, raw_args: list[str], project_root: Path) -> int:
    """Dispatch execution to the appropriate tool module."""
    if not tool_name or tool_name in ("-h", "--help", "help"):
        print(render_tools_help())
        return 0

    norm_name = tool_name.lower().strip()
    handler = TOOL_REGISTRY.get(norm_name)

    if not handler:
        # Check if any tool flag was passed within raw_args
        for arg in raw_args:
            if arg in TOOL_REGISTRY:
                remaining = [a for a in [tool_name] + raw_args if a != arg]
                return TOOL_REGISTRY[arg](project_root, remaining)

        print(f"[vnma tools] Unknown tool '{tool_name}'.")
        print(render_tools_help())
        return 1

    return handler(project_root, raw_args)
