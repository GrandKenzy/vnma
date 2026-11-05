"""Safe dispatcher used by generated console-script launchers."""

from __future__ import annotations

import importlib
import re
import sys


_IDENTIFIER_PATH = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$"
)


def main() -> int | None:
    """Import a validated target and invoke it with the launcher's arguments."""
    if len(sys.argv) < 4:
        raise SystemExit("VNMA launcher requires command, module, and attribute")

    command_name, module_name, attr_path = sys.argv[1:4]
    if not _IDENTIFIER_PATH.fullmatch(module_name) or not _IDENTIFIER_PATH.fullmatch(attr_path):
        raise SystemExit("VNMA launcher target is invalid")

    sys.argv = [command_name, *sys.argv[4:]]
    target = importlib.import_module(module_name)
    for attr_name in attr_path.split("."):
        target = getattr(target, attr_name)
    result = target()
    return result if isinstance(result, int) else None


if __name__ == "__main__":
    sys.exit(main())
