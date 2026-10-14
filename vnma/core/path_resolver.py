"""Cross-platform path resolution and session-independent path serialization."""

from __future__ import annotations

import os
from pathlib import Path


class PortablePathResolver:
    """Normalizes and converts filesystem paths into user-independent portable representations."""

    @classmethod
    def expand(cls, raw_path: str | Path, base_dir: Path | None = None) -> Path:
        """Expand user home, environment variables, and resolve relative paths."""
        text = str(raw_path).strip()
        if text.startswith(("%user%", "%USER%")):
            text = "~" + text[6:]
        elif "%user%" in text.lower():
            text = text.replace("%user%", "~").replace("%USER%", "~")

        expanded = os.path.expanduser(os.path.expandvars(text))
        path_obj = Path(expanded)
        if not path_obj.is_absolute() and base_dir is not None:
            return (base_dir / path_obj).resolve()
        return path_obj.resolve()

    @classmethod
    def to_portable_string(cls, path: str | Path, base_dir: Path | None = None) -> str:
        """Convert an absolute or relative path into a portable string with home or base relative tokens."""
        text = str(path).strip()
        if not text:
            return ""
        if not os.path.isabs(text) and not text.startswith(("~", "%user%", "%USER%")):
            if not ((len(text) >= 2 and text[1] == ":") or text.startswith(("/", "\\"))):
                if base_dir is None:
                    return Path(text).as_posix()

        resolved = cls.expand(path, base_dir=base_dir)

        if base_dir is not None:
            try:
                base_resolved = base_dir.resolve()
                rel = resolved.relative_to(base_resolved)
                return rel.as_posix()
            except ValueError:
                pass

        try:
            home = Path.home().resolve()
            rel_home = resolved.relative_to(home)
            return f"~/{rel_home.as_posix()}"
        except ValueError:
            pass

        return resolved.as_posix()
