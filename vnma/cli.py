"""Command-line interface and subcommands for VNMA."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from vnma.core.config import ConfigHandler, VnmaConfig
from vnma.core.context import ProjectContext
from vnma.core.lockfile import LockfileHandler
from vnma.core.models import PackageSpec, normalize_package_name
from vnma.core.package_config import PackageConfig
from vnma.pypi.cache import WheelCache
from vnma.pypi.git import GitCloner
from vnma.pypi.local_index import LocalWheelIndex
from vnma.pypi.resolver import DependencyConflictError, WheelResolver
from vnma.runtime.bootstrap import BootstrapGenerator
from vnma.runtime.runner import ScriptRunner
from vnma.visitors.git_visitors import GitignoreVisitor
from vnma.visitors.ide_visitors import PyCharmConfigVisitor, VSCodeConfigVisitor
from vnma.wheel.builder import SourceBuilder
from vnma.wheel.installer import WheelInstaller
from vnma.wheel.pruner import OrphanPruner
from vnma.wheel.uninstaller import WheelUninstaller


def cmd_init(args: argparse.Namespace, context: ProjectContext) -> int:
    """Initialize VNMA configuration, directories, and developer environment."""
    context.ensure_directories()

    if not context.config_path.exists() and not context.pyproject_path.exists():
        initial_cfg = VnmaConfig(
            project_name=context.project_root.name,
            version="0.1.0",
            vendor_dir=context.vendor_name,
        )
        ConfigHandler.save(context.config_path, initial_cfg)
        print(f"[vnma] Created {context.config_path.name}")

    BootstrapGenerator(context.vendor_path).generate()
    context.accept(GitignoreVisitor())
    context.accept(VSCodeConfigVisitor())
    context.accept(PyCharmConfigVisitor())

    print(f"[vnma] Project initialized with vendor directory '{context.vendor_name}'")
    return 0


def cmd_install(args: argparse.Namespace, context: ProjectContext) -> int:
    """Install a package or restore all dependencies resolving transitive DAG constraints."""
    context.ensure_directories()
    cache = WheelCache()
    installer = WheelInstaller(context)
    builder = SourceBuilder(cache.cache_dir)
    cloner = GitCloner()

    offline = getattr(args, "offline", False)
    find_links = getattr(args, "find_links", None)
    search_dirs = [cache.cache_dir]
    if find_links:
        search_dirs.append(Path(find_links))

    if offline:
        local_index = LocalWheelIndex(search_directories=search_dirs)
        resolver = WheelResolver(client=local_index)
        print("[vnma] Offline mode enabled. Resolving strictly from local wheel caches.")
    else:
        resolver = WheelResolver()

    target_pkg = args.package

    if not target_pkg or target_pkg == ".":
        config = ConfigHandler.load(context.config_path, context.pyproject_path)
        specs = config.get_all_specs()
        if not specs:
            print("[vnma] No dependencies found to install.")
            return 0

        pypi_specs: list[PackageSpec] = []
        for spec in specs:
            if spec.path:
                _install_local_spec(spec, builder, installer)
            elif spec.git_url:
                if offline:
                    print(f"[vnma] WARNING: Git dependency '{spec.name}' may require network connectivity.")
                _install_git_spec(spec, cloner, builder, installer)
            else:
                pypi_specs.append(spec)

        if pypi_specs:
            origin = "local cache" if offline else "PyPI"
            print(f"[vnma] Resolving {len(pypi_specs)} package(s) from {origin} and transitive dependencies...")
            try:
                resolved_pairs = resolver.resolve_graph(pypi_specs)
            except (DependencyConflictError, ValueError) as err:
                print(f"[vnma] Resolution error: {err}")
                if offline:
                    print("[vnma] Hint: Ensure required wheels exist in ~/.vnma/cache/wheels or pass --find-links <dir>")
                return 1

            for spec, wheel_rel in resolved_pairs:
                _download_and_install(spec, wheel_rel, cache, installer)

        LockfileHandler.update(context)
        print(f"[vnma] Synchronized {context.lock_path.name}")
        return 0

    root_spec = PackageSpec.parse(target_pkg)

    if root_spec.path:
        record = _install_local_spec(root_spec, builder, installer)
        ConfigHandler.add_dependency(
            context.config_path,
            record.name,
            {"path": str(root_spec.path.as_posix())},
        )
        LockfileHandler.update(context)
        print(f"[vnma] Synchronized {context.lock_path.name}")
        return 0

    if root_spec.git_url:
        if offline:
            print(f"[vnma] WARNING: Git dependency '{root_spec.name}' may require network connectivity.")
        record = _install_git_spec(root_spec, cloner, builder, installer)
        ConfigHandler.add_dependency(
            context.config_path,
            record.name,
            {"git": root_spec.git_url, "branch": root_spec.git_ref or "main"},
        )
        LockfileHandler.update(context)
        print(f"[vnma] Synchronized {context.lock_path.name}")
        return 0

    origin = "local cache" if offline else "PyPI"
    print(f"[vnma] Resolving '{root_spec.name}' from {origin} and transitive dependencies...")
    try:
        resolved_pairs = resolver.resolve_graph([root_spec])
    except (DependencyConflictError, ValueError) as err:
        print(f"[vnma] Resolution error: {err}")
        if offline:
            print("[vnma] Hint: Ensure required wheels exist in ~/.vnma/cache/wheels or pass --find-links <dir>")
        return 1

    primary_record = None
    for spec, wheel_rel in resolved_pairs:
        record = _download_and_install(spec, wheel_rel, cache, installer)
        if spec.name == root_spec.name:
            primary_record = record

    if primary_record:
        ConfigHandler.add_dependency(
            context.config_path,
            primary_record.name,
            f"=={primary_record.version}",
        )

    LockfileHandler.update(context)
    print(f"[vnma] Synchronized {context.lock_path.name}")
    return 0


def _install_local_spec(
    spec: PackageSpec,
    builder: SourceBuilder,
    installer: WheelInstaller,
):
    """Build and install package from local filesystem source path."""
    src_path = spec.path
    if not src_path or not src_path.is_dir():
        raise FileNotFoundError(f"Source directory not found: {src_path}")

    pkg_cfg = PackageConfig.load_from_dir(src_path)
    if pkg_cfg:
        print(f"[vnma] Loaded explicit configuration from {src_path / 'vnma_config.toml'}")

    print(f"[vnma] Building wheel from local source '{src_path.name}'...")
    wheel_path = builder.build_wheel(src_path)

    ver = pkg_cfg.version if pkg_cfg and pkg_cfg.version else "0.0.0"
    if ver == "0.0.0":
        # Extract from wheel filename
        parts = wheel_path.stem.split("-")
        if len(parts) >= 2:
            ver = parts[1]

    print(f"[vnma] Installing built wheel {wheel_path.name} into vendor...")
    record = installer.install(wheel_path, spec.name, ver, package_config=pkg_cfg)
    print(
        f"[vnma] Successfully installed {record.name}=={record.version} from {src_path} "
        f"({len(record.files)} files, native_binaries={record.has_native_binaries})"
    )
    return record


def _install_git_spec(
    spec: PackageSpec,
    cloner: GitCloner,
    builder: SourceBuilder,
    installer: WheelInstaller,
):
    """Clone, build and install package from remote git repository."""
    print(f"[vnma] Cloning git repository {spec.git_url} (ref: {spec.git_ref})...")
    repo_path = cloner.fetch_repository(spec.git_url or "", spec.git_ref or "main")

    pkg_cfg = PackageConfig.load_from_dir(repo_path)
    if pkg_cfg:
        print(f"[vnma] Loaded explicit configuration from {repo_path / 'vnma_config.toml'}")

    print(f"[vnma] Building wheel from repository '{repo_path.name}'...")
    wheel_path = builder.build_wheel(repo_path)

    ver = pkg_cfg.version if pkg_cfg and pkg_cfg.version else "0.0.0"
    if ver == "0.0.0":
        parts = wheel_path.stem.split("-")
        if len(parts) >= 2:
            ver = parts[1]

    print(f"[vnma] Installing built wheel {wheel_path.name} into vendor...")
    record = installer.install(wheel_path, spec.name, ver, package_config=pkg_cfg)
    print(
        f"[vnma] Successfully installed {record.name}=={record.version} from git "
        f"({len(record.files)} files, native_binaries={record.has_native_binaries})"
    )
    return record


def _download_and_install(
    spec: PackageSpec,
    wheel_release,
    cache: WheelCache,
    installer: WheelInstaller,
):
    """Download wheel from cache/PyPI and install into vendor directory."""
    print(f"[vnma] Fetching {wheel_release.filename}...")
    wheel_path = cache.download_wheel(
        wheel_release.url,
        wheel_release.filename,
        wheel_release.sha256,
    )
    print(f"[vnma] Installing {wheel_release.filename} into vendor...")
    record = installer.install(wheel_path, spec.name, wheel_release.version)
    print(
        f"[vnma] Successfully installed {record.name}=={record.version} "
        f"({len(record.files)} files, native_binaries={record.has_native_binaries})"
    )
    return record


def cmd_uninstall(args: argparse.Namespace, context: ProjectContext) -> int:
    """Uninstall a package and clean its files and configuration entries."""
    raw_target = args.package
    spec = PackageSpec.parse(raw_target)
    uninstaller = WheelUninstaller(context)

    if uninstaller.uninstall(spec.name):
        ConfigHandler.remove_dependency(context.config_path, spec.name)
        LockfileHandler.update(context)
        print(f"[vnma] Successfully uninstalled '{spec.name}' and synchronized {context.lock_path.name}")
        return 0

    print(f"[vnma] Package '{spec.name}' is not currently installed.")
    return 1


def cmd_prune(args: argparse.Namespace, context: ProjectContext) -> int:
    """Identify and remove orphaned packages not reachable from project dependencies."""
    pruner = OrphanPruner(context)
    orphans = pruner.find_orphans()

    if not orphans:
        print("[vnma] No orphaned packages found. Vendor tree is clean.")
        return 0

    if getattr(args, "dry_run", False):
        print(f"[vnma] Dry-run: The following {len(orphans)} orphaned package(s) would be removed:")
        for pkg in orphans:
            print(f"  - {pkg}")
        return 0

    if not getattr(args, "yes", False):
        try:
            confirm = input(f"[vnma] Prune {len(orphans)} orphaned package(s)? [y/N]: ").strip().lower()
            if confirm not in ("y", "yes"):
                print("[vnma] Pruning aborted.")
                return 0
        except (KeyboardInterrupt, EOFError):
            print("\n[vnma] Pruning aborted.")
            return 0

    pruned = pruner.prune(dry_run=False)
    print(f"[vnma] Successfully pruned {len(pruned)} orphaned package(s): {', '.join(pruned)}")
    print(f"[vnma] Synchronized {context.lock_path.name}")
    return 0


def cmd_list(args: argparse.Namespace, context: ProjectContext) -> int:
    """Display all packages and versions installed in the vendor directory."""
    installer = WheelInstaller(context)
    manifest = installer._load_manifest()

    if not manifest.packages:
        print("[vnma] No packages installed in vendor directory.")
        return 0

    print(f"[vnma] Packages installed in '{context.vendor_name}':")
    print(f"{'Package':<25} {'Version':<15} {'Native':<10}")
    print("-" * 52)
    for name, record in sorted(manifest.packages.items()):
        native_flag = "Yes" if record.has_native_binaries else "No"
        print(f"{name:<25} {record.version:<15} {native_flag:<10}")

    return 0


def cmd_sync_ide(args: argparse.Namespace, context: ProjectContext) -> int:
    """Regenerate IDE workspace configuration for VS Code and PyCharm."""
    vs_updated = context.accept(VSCodeConfigVisitor())
    pc_updated = context.accept(PyCharmConfigVisitor())
    git_updated = context.accept(GitignoreVisitor())

    print(
        f"[vnma] IDE sync finished (vscode_changed={vs_updated}, "
        f"pycharm_changed={pc_updated}, gitignore_changed={git_updated})"
    )
    return 0


def cmd_run(args: argparse.Namespace, context: ProjectContext) -> int:
    """Execute a Python script with the vendor directory configured."""
    script_path = Path(args.script)
    if not script_path.exists():
        print(f"[vnma] Error: Script '{args.script}' not found.")
        return 1

    runner = ScriptRunner(context)
    return runner.run_script(script_path, args.args)


def cmd_exec(args: argparse.Namespace, context: ProjectContext) -> int:
    """Execute a CLI tool installed in the vendor binary directory."""
    runner = ScriptRunner(context)
    try:
        return runner.exec_binary(args.binary, args.args)
    except FileNotFoundError as err:
        print(f"[vnma] Error: {err}")
        return 1


def cmd_check(args: argparse.Namespace, context: ProjectContext) -> int:
    """Verify runtime compatibility and python version consistency."""
    ver_file = context.meta_path / "python_version"
    current_ver = (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )

    if not ver_file.exists():
        print("[vnma] No metadata found. Vendor has not been built yet.")
        return 0

    saved_ver = ver_file.read_text(encoding="utf-8").strip()
    if saved_ver != current_ver:
        print(
            f"[vnma] WARNING: Vendor was built with Python {saved_ver}, "
            f"but you are running Python {current_ver}."
        )
        print("[vnma] Native binary extensions (.pyd/.so) may fail to load.")
        print("[vnma] Run 'vnma install .' to rebuild dependencies.")
        return 2

    print(f"[vnma] Health check passed. Runtime matches Python {current_ver}.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="vnma",
        description="VNMA — Vendor Manager for Python",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize project vendor configuration")
    init_parser.set_defaults(handler=cmd_init)

    install_parser = subparsers.add_parser("install", help="Install a package or restore dependencies")
    install_parser.add_argument(
        "package",
        nargs="?",
        default=None,
        help="Package name, version, local directory path, or git+ URL",
    )
    install_parser.add_argument(
        "--offline",
        action="store_true",
        help="Install strictly from local wheel cache without network calls",
    )
    install_parser.add_argument(
        "--find-links",
        type=str,
        default=None,
        help="Directory to search for local wheel archives",
    )
    install_parser.set_defaults(handler=cmd_install)

    uninstall_parser = subparsers.add_parser("uninstall", help="Uninstall a vendored package")
    uninstall_parser.add_argument("package", help="Package to remove (e.g. pygame-2.5.6)")
    uninstall_parser.set_defaults(handler=cmd_uninstall)

    prune_parser = subparsers.add_parser("prune", help="Remove orphaned packages not defined in vnma.toml")
    prune_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview orphaned packages without removing them",
    )
    prune_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Automatically confirm pruning of orphaned packages",
    )
    prune_parser.set_defaults(handler=cmd_prune)

    list_parser = subparsers.add_parser("list", help="List vendored packages")
    list_parser.set_defaults(handler=cmd_list)

    sync_parser = subparsers.add_parser("sync-ide", help="Synchronize IDE settings for VS Code and PyCharm")
    sync_parser.set_defaults(handler=cmd_sync_ide)

    run_parser = subparsers.add_parser("run", help="Run a Python script with vendor environment active")
    run_parser.add_argument("script", help="Path to Python script to execute")
    run_parser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments passed to the script")
    run_parser.set_defaults(handler=cmd_run)

    exec_parser = subparsers.add_parser("exec", help="Execute an installed binary from vendor/.bin")
    exec_parser.add_argument("binary", help="Binary or CLI name (e.g. pytest)")
    exec_parser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments passed to the binary")
    exec_parser.set_defaults(handler=cmd_exec)

    check_parser = subparsers.add_parser("check", help="Check vendor runtime compatibility")
    check_parser.set_defaults(handler=cmd_check)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI application entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)
    context = ProjectContext()
    return args.handler(args, context)


if __name__ == "__main__":
    sys.exit(main())
