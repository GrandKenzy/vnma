"""Project visitors configuring auto-completion and symbol indexers for IDEs."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from vnma.visitors.base import ProjectVisitor

if TYPE_CHECKING:
    from vnma.core.context import ProjectContext

_JSONC_PATTERN = re.compile(
    r'(\".*?\"|\'.*?\')|(/\*.*?\*/|//[^\r\n]*$)',
    re.MULTILINE | re.DOTALL,
)


def loads_jsonc(text: str) -> dict[str, object]:
    """Parse JSON with comments (JSONC) and trailing commas safely."""
    def _replacer(match: re.Match) -> str:
        if match.group(2) is not None:
            return ""
        return match.group(1)

    without_comments = _JSONC_PATTERN.sub(_replacer, text)
    clean_json = re.sub(r",\s*([}\]])", r"\1", without_comments)
    return json.loads(clean_json) if clean_json.strip() else {}


class VSCodeConfigVisitor(ProjectVisitor):
    """Configures Visual Studio Code Pylance/Jedi extra paths for symbol discovery."""

    def visit_project(self, context: ProjectContext) -> bool:
        """Inject vendor directory into .vscode/settings.json supporting JSONC."""
        vscode_dir = context.project_root / ".vscode"
        settings_file = vscode_dir / "settings.json"
        vendor_rel = f"./{context.vendor_name}"

        settings: dict[str, object] = {}
        if settings_file.exists():
            try:
                raw_text = settings_file.read_text(encoding="utf-8")
                settings = loads_jsonc(raw_text)
            except Exception:
                settings = {}

        linked_paths: list[str] = []
        try:
            from vnma.core.config import ConfigHandler
            from vnma.core.path_resolver import PortablePathResolver
            config = ConfigHandler.load(context.config_path, context.pyproject_path)
            for spec in config.get_all_specs(include_dev=True):
                if spec.editable and spec.path and spec.path.is_dir():
                    portable_str = PortablePathResolver.to_portable_string(spec.path, context.project_root)
                    if portable_str.startswith("~/"):
                        vscode_path = "${userHome}/" + portable_str[2:]
                    else:
                        vscode_path = portable_str
                    linked_paths.append(vscode_path)
        except Exception:
            pass

        target_paths = [vendor_rel, *linked_paths]
        changed = False
        for key in ("python.analysis.extraPaths", "python.autoComplete.extraPaths"):
            current_paths = list(settings.get(key, []))
            for p in target_paths:
                if p not in current_paths:
                    current_paths.append(p)
                    changed = True
            settings[key] = current_paths

        if changed or not settings_file.exists():
            vscode_dir.mkdir(parents=True, exist_ok=True)
            settings_file.write_text(json.dumps(settings, indent=4), encoding="utf-8")
            return True

        return False


class PyCharmConfigVisitor(ProjectVisitor):
    """Configures JetBrains PyCharm workspace roots and PYTHONPATH environments."""

    def visit_project(self, context: ProjectContext) -> bool:
        """Configure .idea IML modules and root .env for PyCharm."""
        changed = False
        vendor_name = context.vendor_name

        idea_dir = context.project_root / ".idea"
        if idea_dir.is_dir():
            iml_files = list(idea_dir.glob("*.iml"))
            for iml in iml_files:
                if self._patch_iml_file(iml, vendor_name):
                    changed = True

        env_file = context.project_root / ".env"
        env_entry = f"PYTHONPATH=./{vendor_name}"
        if not env_file.exists():
            env_file.write_text(f"{env_entry}\n", encoding="utf-8")
            changed = True
        else:
            text = env_file.read_text(encoding="utf-8", errors="replace")
            if "PYTHONPATH" not in text:
                new_text = text.rstrip() + f"\n{env_entry}\n"
                env_file.write_text(new_text, encoding="utf-8")
                changed = True

        return changed

    @staticmethod
    def _patch_iml_file(iml_path: Path, vendor_name: str) -> bool:
        """Add vendor directory as source folder to PyCharm module configuration."""
        content = iml_path.read_text(encoding="utf-8", errors="replace")
        target_snippet = f'<sourceFolder url="file://$MODULE_DIR$/{vendor_name}" isTestSource="false" />'

        if target_snippet in content:
            return False

        if "<content url=" in content:
            patched = re.sub(
                r"(<content url=\"[^\"]*\">)",
                rf"\1\n      {target_snippet}",
                content,
                count=1,
            )
            iml_path.write_text(patched, encoding="utf-8")
            return True

        return False
