"""Command-line interface and subcommands for VNMA."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from vnma.core.cleaner import WorkspaceCleaner
from vnma.core.config import ConfigHandler, VnmaConfig
from vnma.core.context import ProjectContext
from vnma.core.link_manager import LinkManager
from vnma.core.lockfile import LockfileHandler
from vnma.core.transaction import atomic_workspace_command, WorkspaceTransaction
from vnma.core.models import PackageSpec, normalize_package_name
from vnma.core.package_config import PackageConfig
from vnma.pypi.cache import WheelCache
from vnma.pypi.client import PyPIClient
from vnma.pypi.git import GitCloner
from vnma.pypi.local_index import LocalWheelIndex
from vnma.pypi.resolver import DependencyConflictError, WheelResolver
from vnma.runtime.bootstrap import BootstrapGenerator
from vnma.runtime.runner import EntryPointResolver, ScriptRunner
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


def cmd_generate(args: argparse.Namespace, context: ProjectContext) -> int:
    """Generate an empty TOML configuration template with current directory context."""
    force = getattr(args, "force", False)
    is_package = getattr(args, "package", False)
    folder_name = context.project_root.name

    if is_package:
        target_path = context.project_root / "vnma_config.toml"
        if target_path.exists() and not force:
            print(f"[vnma] Error: '{target_path.name}' already exists. Use --force to overwrite.")
            return 1

        content = (
            "[package]\n"
            f'name = "{folder_name}"\n'
            'version = "1.0.0"\n'
            'type = "pure-python"\n\n'
            "[runtime]\n"
            "dll_directories = []\n"
            "hermetic = true\n\n"
            "[exports]\n"
            "modules = []\n"
            "entry_points = {}\n"
        )
        target_path.write_text(content, encoding="utf-8")
        print(f"[vnma] Generated package manifest '{target_path.name}' for '{folder_name}' (v1.0.0)")
        return 0

    target_path = context.config_path
    if target_path.exists() and not force:
        print(f"[vnma] Error: '{target_path.name}' already exists. Use --force to overwrite.")
        return 1

    config = VnmaConfig(
        project_name=folder_name,
        version="1.0.0",
        vendor_dir=context.vendor_name,
    )
    ConfigHandler.save(target_path, config)
    print(f"[vnma] Generated '{target_path.name}' for project '{folder_name}' (v1.0.0)")
    return 0


@atomic_workspace_command
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
    is_dev = getattr(args, "dev", False)

    if not target_pkg or target_pkg == ".":
        config = ConfigHandler.load(context.config_path, context.pyproject_path)
        specs = config.get_all_specs(include_dev=is_dev)
        if not specs:
            print("[vnma] No dependencies found to install.")
            return 0

        if LockfileHandler.is_synchronized(context, config):
            lock_data = LockfileHandler.load(context.lock_path)
            if lock_data and LockfileHandler.is_vendor_synchronized(context, lock_data):
                print(f"[vnma] All locked dependencies already satisfied in {context.vendor_name}/.")
                return 0
            if lock_data:
                print(f"[vnma] Restoring exact dependencies from {context.lock_path.name}...")
                _restore_from_lock(
                    context,
                    lock_data,
                    cache,
                    installer,
                    builder,
                    cloner,
                    offline=offline,
                    find_links=find_links,
                )
                LockfileHandler.update(context)
                print(f"[vnma] Restored environment matching {context.lock_path.name}")
                return 0

        pypi_specs: list[PackageSpec] = []
        for spec in specs:
            if spec.path:
                if spec.editable:
                    link_spec, link_deps = LinkManager(context).link(str(spec.path))
                    pypi_specs.extend(link_deps)
                else:
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
    is_editable = getattr(args, "editable", False) or root_spec.editable

    if is_editable:
        target_path = str(root_spec.path or target_pkg)
        link_spec, link_deps = LinkManager(context).link(target_path)
        if link_deps:
            try:
                resolved_pairs = resolver.resolve_graph(link_deps)
                for dep_spec, wheel_rel in resolved_pairs:
                    _download_and_install(dep_spec, wheel_rel, cache, installer)
            except Exception:
                pass
        LockfileHandler.update(context)
        print(f"[vnma] Synchronized {context.lock_path.name}")
        return 0

    if root_spec.path:
        record = _install_local_spec(root_spec, builder, installer)
        add_fn = ConfigHandler.add_dev_dependency if is_dev else ConfigHandler.add_dependency
        add_fn(
            context.config_path,
            record.name,
            {"path": str(root_spec.path.as_posix())},
            pyproject_path=context.pyproject_path,
        )
        LockfileHandler.update(context)
        print(f"[vnma] Synchronized {context.lock_path.name}")
        return 0

    if root_spec.git_url:
        if offline:
            print(f"[vnma] WARNING: Git dependency '{root_spec.name}' may require network connectivity.")
        record = _install_git_spec(root_spec, cloner, builder, installer)
        add_fn = ConfigHandler.add_dev_dependency if is_dev else ConfigHandler.add_dependency
        add_fn(
            context.config_path,
            record.name,
            {"git": root_spec.git_url, "branch": root_spec.git_ref or "main"},
            pyproject_path=context.pyproject_path,
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
        add_fn = ConfigHandler.add_dev_dependency if is_dev else ConfigHandler.add_dependency
        add_fn(
            context.config_path,
            primary_record.name,
            root_spec.specifier if root_spec.specifier else f"=={primary_record.version}",
            pyproject_path=context.pyproject_path,
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
        parts = wheel_path.stem.split("-")
        if len(parts) >= 2:
            ver = parts[1]

    print(f"[vnma] Installing built wheel {wheel_path.name} into vendor...")
    record = installer.install(
        wheel_path,
        spec.name,
        ver,
        package_config=pkg_cfg,
        active_extras=spec.extras,
    )
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
    record = installer.install(
        wheel_path,
        spec.name,
        ver,
        package_config=pkg_cfg,
        active_extras=spec.extras,
    )
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
    record = installer.install(
        wheel_path,
        spec.name,
        wheel_release.version,
        active_extras=spec.extras,
    )
    print(
        f"[vnma] Successfully installed {record.name}=={record.version} "
        f"({len(record.files)} files, native_binaries={record.has_native_binaries})"
    )
    return record


def _restore_from_lock(
    context: ProjectContext,
    lock_data: dict[str, Any],
    cache: WheelCache,
    installer: WheelInstaller,
    builder: SourceBuilder,
    cloner: GitCloner,
    offline: bool = False,
    find_links: str | None = None,
) -> None:
    """Restore locked packages strictly using recorded hashes and wheel artifacts."""
    packages = lock_data.get("packages", {})
    manifest = installer._load_manifest()
    pypi_client: PyPIClient | None = None

    for pkg_name, info in sorted(packages.items()):
        norm_name = normalize_package_name(pkg_name)
        ver = info.get("version", "")
        expected_sha = info.get("sha256", "")
        wheel_name = info.get("wheel_filename", "")
        extras = tuple(info.get("active_extras", []))

        existing_record = manifest.packages.get(norm_name)
        if existing_record and existing_record.version == ver:
            if not expected_sha or existing_record.wheel_sha256 == expected_sha:
                continue

        source = info.get("source", "pypi")
        if source == "editable" or info.get("editable"):
            from vnma.core.path_resolver import PortablePathResolver
            local_path = PortablePathResolver.expand(info.get("path", ""), base_dir=context.project_root)
            LinkManager(context).link(str(local_path))
            continue

        if source == "local":
            local_path = Path(info.get("path", ""))
            spec = PackageSpec(name=norm_name, path=local_path, extras=extras)
            _install_local_spec(spec, builder, installer)
            continue

        if source == "git":
            spec = PackageSpec(
                name=norm_name,
                git_url=info.get("git_url", ""),
                git_ref=info.get("git_ref", "main"),
                extras=extras,
            )
            _install_git_spec(spec, cloner, builder, installer)
            continue

        wheel_file: Path | None = None
        if wheel_name:
            cached_candidate = cache.get_wheel_path(wheel_name)
            if cached_candidate and (not expected_sha or WheelCache._verify_sha256(cached_candidate, expected_sha)):
                wheel_file = cached_candidate
            elif find_links:
                candidate_path = Path(find_links) / wheel_name
                if candidate_path.is_file() and (not expected_sha or WheelCache._verify_sha256(candidate_path, expected_sha)):
                    wheel_file = candidate_path

        if not wheel_file:
            if offline:
                raise FileNotFoundError(
                    f"Locked wheel '{wheel_name}' for package '{norm_name}' not found in local cache."
                )
            if pypi_client is None:
                pypi_client = PyPIClient()
            releases = pypi_client.fetch_wheel_releases(norm_name, requested_version=ver)
            matched_rel = None
            if wheel_name:
                for rel in releases:
                    if rel.filename == wheel_name:
                        matched_rel = rel
                        break
            if not matched_rel and releases:
                matched_rel = releases[0]
            if not matched_rel:
                raise ValueError(
                    f"No release distribution found on PyPI matching locked package '{norm_name}=={ver}'."
                )
            print(f"[vnma] Fetching {matched_rel.filename}...")
            wheel_file = cache.download_wheel(
                matched_rel.url,
                matched_rel.filename,
                expected_sha256=expected_sha or matched_rel.sha256,
            )

        print(f"[vnma] Restoring {wheel_file.name} into vendor...")
        record = installer.install(wheel_file, norm_name, ver, active_extras=extras)
        manifest.packages[norm_name] = record


@atomic_workspace_command
def cmd_update(args: argparse.Namespace, context: ProjectContext) -> int:
    """Update dependencies to latest compatible versions ignoring user-pinned packages."""
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
        print("[vnma] Offline mode enabled. Resolving updates strictly from local wheel caches.")
    else:
        resolver = WheelResolver()

    is_dev = getattr(args, "dev", False)
    config = ConfigHandler.load(context.config_path, context.pyproject_path)
    specs = config.get_all_specs(include_dev=is_dev)
    if not specs:
        print("[vnma] No dependencies found to update.")
        return 0

    target_pkg = getattr(args, "package", None)
    if target_pkg:
        norm_target = normalize_package_name(target_pkg)
        specs = [s for s in specs if s.name == norm_target]
        if not specs:
            print(f"[vnma] Package '{target_pkg}' is not declared in project dependencies.")
            return 1

    only_git = getattr(args, "git", False)
    only_pip = getattr(args, "pip", False)

    updated_count = 0
    pypi_specs_to_resolve: list[PackageSpec] = []

    for spec in specs:
        raw_val = config.dependencies.get(spec.name) or config.dev_dependencies.get(spec.name)

        if spec.git_url:
            if only_pip:
                continue
            is_pinned_git = False
            if isinstance(raw_val, dict):
                if "commit" in raw_val or "tag" in raw_val:
                    is_pinned_git = True
            if is_pinned_git:
                continue
            print(f"[vnma] Updating git dependency '{spec.name}' from {spec.git_url} (ref: {spec.git_ref})...")
            _install_git_spec(spec, cloner, builder, installer)
            updated_count += 1
        elif spec.path:
            if only_git or only_pip:
                continue
            print(f"[vnma] Rebuilding local dependency '{spec.name}' from {spec.path}...")
            _install_local_spec(spec, builder, installer)
            updated_count += 1
        else:
            if only_git:
                continue
            is_pinned_pypi = False
            if isinstance(raw_val, str) and (raw_val.startswith("==") or raw_val.startswith("===")):
                is_pinned_pypi = True
            elif spec.specifier.startswith("==") or spec.specifier.startswith("==="):
                is_pinned_pypi = True
            if is_pinned_pypi:
                continue
            pypi_specs_to_resolve.append(spec)

    if pypi_specs_to_resolve:
        origin = "local cache" if offline else "PyPI"
        print(f"[vnma] Resolving latest updates for {len(pypi_specs_to_resolve)} package(s) from {origin}...")
        try:
            resolved_pairs = resolver.resolve_graph(pypi_specs_to_resolve)
        except (DependencyConflictError, ValueError) as err:
            print(f"[vnma] Update resolution error: {err}")
            return 1

        for r_spec, wheel_rel in resolved_pairs:
            _download_and_install(r_spec, wheel_rel, cache, installer)
            updated_count += 1

    if updated_count == 0:
        print("[vnma] All declared dependencies are pinned or already up to date.")
        return 0

    LockfileHandler.update(context)
    print(f"[vnma] Successfully updated {updated_count} package(s) and synchronized {context.lock_path.name}")
    return 0


def cmd_uninstall(args: argparse.Namespace, context: ProjectContext) -> int:
    """Uninstall a package transactionally; full project purge remains explicit."""
    if getattr(args, "package", None) and not getattr(args, "all", False):
        with WorkspaceTransaction(context) as txn:
            status = _cmd_uninstall(args, context)
            if status != 0:
                txn.abort()
            return status
    return _cmd_uninstall(args, context)


def _cmd_uninstall(args: argparse.Namespace, context: ProjectContext) -> int:
    """Uninstall a package or completely purge VNMA support from the project directory."""
    raw_target = getattr(args, "package", None)
    purge_all = getattr(args, "all", False)

    if not raw_target or purge_all:
        if not getattr(args, "yes", False) and sys.stdin.isatty():
            try:
                choice = input("[vnma] Remove all VNMA vendors and project support files? [y/N]: ").strip().lower()
                if choice not in ("y", "yes"):
                    print("[vnma] Uninstall cancelled by user.")
                    return 0
            except (KeyboardInterrupt, EOFError):
                print("\n[vnma] Operation aborted.")
                return 1

        keep_config = getattr(args, "keep_config", False)
        cleaner = WorkspaceCleaner(context)
        actions = cleaner.purge(keep_config=keep_config)

        if not actions:
            print("[vnma] Workspace is already clean. No VNMA artifacts found.")
            return 0

        for act in actions:
            print(f"[vnma] {act}")
        print("[vnma] Project cleaned successfully.")
        return 0

    spec = PackageSpec.parse(raw_target)
    uninstaller = WheelUninstaller(context)

    if uninstaller.uninstall(spec.name):
        if getattr(args, "delete_from_toml", False):
            ConfigHandler.remove_dependency(
                context.config_path,
                spec.name,
                pyproject_path=context.pyproject_path,
            )
            print(
                f"[vnma] Successfully uninstalled '{spec.name}', removed from "
                f"{context.config_path.name} and synchronized {context.lock_path.name}"
            )
        else:
            print(
                f"[vnma] Successfully uninstalled '{spec.name}' from {context.vendor_name}/ "
                f"(retained in {context.config_path.name}, use --del to remove)"
            )
        LockfileHandler.update(context)
        return 0

    print(f"[vnma] Package '{spec.name}' is not currently installed.")
    return 1



@atomic_workspace_command
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
    """Execute a Python script or entrypoint with the vendor directory configured."""
    manager = LinkManager(context)
    broken = manager.verify_links()
    if broken:
        print(manager.render_broken_links_alert(broken))
        return 1

    target = args.target
    extra_args = list(args.args)
    if target and target.startswith("-"):
        extra_args.insert(0, target)
        target = None

    resolver = EntryPointResolver(context.project_root)
    try:
        script_path = resolver.resolve(target)
    except FileNotFoundError as err:
        print(f"[vnma] Error: {err}")
        return 1

    runner = ScriptRunner(context)
    return runner.run_script(script_path, extra_args)


@atomic_workspace_command
def cmd_link(args: argparse.Namespace, context: ProjectContext) -> int:
    """Link a local directory in zero-copy live development mode."""
    context.ensure_directories()
    manager = LinkManager(context)
    try:
        linked_spec, deps = manager.link(args.path)
    except FileNotFoundError:
        alert = LinkManager.render_broken_links_alert([(args.path, Path(args.path))])
        print(alert)
        return 1

    print(f"[vnma] Successfully linked '{linked_spec.name}' from {linked_spec.path}")
    print("[vnma] Mode: Live development (Zero-Copy). Changes in source files apply immediately.")

    if deps:
        print(f"[vnma] Resolving {len(deps)} declared dependency/dependencies for '{linked_spec.name}'...")
        cache = WheelCache()
        installer = WheelInstaller(context)
        resolver = WheelResolver()
        try:
            resolved = resolver.resolve_graph(deps)
        except (DependencyConflictError, ValueError) as err:
            print(f"[vnma] Resolution error for linked package dependencies: {err}")
            return 1
        for r_spec, wheel_rel in resolved:
            _download_and_install(r_spec, wheel_rel, cache, installer)
        LockfileHandler.update(context)

    return 0


@atomic_workspace_command
def cmd_unlink(args: argparse.Namespace, context: ProjectContext) -> int:
    """Remove a linked local package and restore standard configuration."""
    manager = LinkManager(context)
    unlinked = manager.unlink(args.target)
    if not unlinked:
        print(f"[vnma] Error: No linked package matching '{args.target}' found.")
        return 1

    print(f"[vnma] Successfully unlinked '{unlinked.name}'.")
    print("[vnma] Tip: Run 'vnma reload' to automatically prune dependencies that are no longer needed.")
    return 0


@atomic_workspace_command
def cmd_reload(args: argparse.Namespace, context: ProjectContext) -> int:
    """Verify links, reconcile transitive dependencies, and automatically prune orphans."""
    context.ensure_directories()
    manager = LinkManager(context)
    broken = manager.verify_links()
    if broken:
        print(manager.render_broken_links_alert(broken))
        return 1

    linked_specs = manager.get_linked_specs()
    extra_deps: list[PackageSpec] = []
    for l_spec in linked_specs:
        if l_spec.path and l_spec.path.is_dir():
            _, _, deps = manager.inspect_target(l_spec.path)
            extra_deps.extend(deps)

    config = ConfigHandler.load(context.config_path, context.pyproject_path)
    root_specs = config.get_all_specs(include_dev=True)
    pypi_specs = [s for s in root_specs if not s.path and not s.git_url]
    pypi_specs.extend([s for s in extra_deps if not s.path and not s.git_url])

    cache = WheelCache()
    installer = WheelInstaller(context)
    resolver = WheelResolver()

    if pypi_specs:
        try:
            resolved = resolver.resolve_graph(pypi_specs)
        except (DependencyConflictError, ValueError) as err:
            print(f"[vnma] Reload resolution error: {err}")
            return 1

        manifest = installer._load_manifest()
        for r_spec, wheel_rel in resolved:
            expected_ver = r_spec.specifier.lstrip("=")
            if r_spec.name not in manifest.packages or (expected_ver and manifest.packages[r_spec.name].version != expected_ver):
                _download_and_install(r_spec, wheel_rel, cache, installer)

    pruner = OrphanPruner(context)
    pruned = pruner.prune(dry_run=False, extra_root_specs=extra_deps)
    if pruned:
        print(f"[vnma] Automatically pruned {len(pruned)} unused package(s): {', '.join(pruned)}")

    manager.sync_bootstrap()
    manager._sync_environment()
    LockfileHandler.update(context)
    print(f"[vnma] Reload completed successfully ({len(linked_specs)} link(s) active).")
    return 0


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

    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate an empty TOML configuration template with project headers",
    )
    generate_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Overwrite existing configuration file if present",
    )
    generate_parser.add_argument(
        "-p",
        "--package",
        "--lib",
        action="store_true",
        dest="package",
        help="Generate package-level vnma_config.toml for libraries",
    )
    generate_parser.set_defaults(handler=cmd_generate)

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
    install_parser.add_argument(
        "-e",
        "--editable",
        action="store_true",
        help="Install local package directory in editable (zero-copy link) mode",
    )
    install_parser.add_argument(
        "--dev",
        action="store_true",
        help="Install development dependencies or record package in dev-dependencies",
    )
    install_parser.set_defaults(handler=cmd_install)

    update_parser = subparsers.add_parser("update", help="Update vendored dependencies to latest versions")
    update_parser.add_argument(
        "package",
        nargs="?",
        default=None,
        help="Optional package name to update individually",
    )
    update_parser.add_argument(
        "--git",
        action="store_true",
        help="Only update git repository dependencies",
    )
    update_parser.add_argument(
        "--pip",
        action="store_true",
        help="Only update PyPI dependencies",
    )
    update_parser.add_argument(
        "--dev",
        action="store_true",
        help="Include development dependencies when updating",
    )
    update_parser.add_argument(
        "--offline",
        action="store_true",
        help="Update strictly from local wheel cache without network calls",
    )
    update_parser.add_argument(
        "--find-links",
        type=str,
        default=None,
        help="Directory to search for local wheel archives",
    )
    update_parser.set_defaults(handler=cmd_update)


    uninstall_parser = subparsers.add_parser("uninstall", help="Uninstall a vendored package or clean project support")
    uninstall_parser.add_argument(
        "package",
        nargs="?",
        default=None,
        help="Package to remove (e.g. pygame-2.5.6). If omitted, completely removes VNMA support from this project.",
    )
    uninstall_parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Purge all VNMA vendor directories, lockfiles, and workspace integrations",
    )
    uninstall_parser.add_argument(
        "--keep-config",
        action="store_true",
        help="Preserve vnma.toml when performing a workspace purge",
    )
    uninstall_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Bypass interactive confirmation prompt",
    )
    uninstall_parser.add_argument(
        "-d",
        "--del",
        "--delete",
        dest="delete_from_toml",
        action="store_true",
        help="Remove package specification from vnma.toml",
    )
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

    link_parser = subparsers.add_parser(
        "link", help="Link a local directory in zero-copy live development mode"
    )
    link_parser.add_argument("path", help="Path to local package directory")
    link_parser.set_defaults(handler=cmd_link)

    unlink_parser = subparsers.add_parser("unlink", help="Unlink a local package directory")
    unlink_parser.add_argument("target", help="Package name or directory path to unlink")
    unlink_parser.set_defaults(handler=cmd_unlink)

    reload_parser = subparsers.add_parser(
        "reload", help="Verify links, reconcile dependencies, and prune orphans"
    )
    reload_parser.set_defaults(handler=cmd_reload)

    run_parser = subparsers.add_parser("run", help="Run a Python script with vendor environment active")
    run_parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="Path to script or directory (defaults to main.py)",
    )
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
    args_list = sys.argv[1:] if argv is None else list(argv)
    if len(args_list) > 1 and args_list[0] == "run":
        if args_list[1].startswith("-") and args_list[1] not in ("-h", "--help"):
            args_list.insert(1, "--")

    parser = build_parser()
    args = parser.parse_args(args_list)
    context = ProjectContext()
    return args.handler(args, context)


if __name__ == "__main__":
    sys.exit(main())
