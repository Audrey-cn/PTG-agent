"""Backup and import commands for prometheus CLI."""

import contextlib
import json
import logging
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from prometheus.constants_core import (
    display_prometheus_home,
    get_default_prometheus_root,
    get_prometheus_home,
)

logger = logging.getLogger(__name__)


_EXCLUDED_DIRS = {
    "prometheus-agent",
    "__pycache__",
    ".git",
    "node_modules",
    "backups",
    "checkpoints",
}

_EXCLUDED_SUFFIXES = (
    ".pyc",
    ".pyo",
    ".db-wal",
    ".db-shm",
    ".db-journal",
)

_EXCLUDED_NAMES = {
    "gateway.pid",
    "cron.pid",
}


def _should_exclude(rel_path: Path) -> bool:
    """Return True if *rel_path* (relative to prometheus root) should be skipped."""
    parts = rel_path.parts

    for part in parts:
        if part in _EXCLUDED_DIRS:
            return True

    name = rel_path.name

    if name in _EXCLUDED_NAMES:
        return True

    return bool(name.endswith(_EXCLUDED_SUFFIXES))


def _safe_copy_db(src: Path, dst: Path) -> bool:
    """Copy a SQLite database safely using the backup() API."""
    try:
        conn = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
        backup_conn = sqlite3.connect(str(dst))
        conn.backup(backup_conn)
        backup_conn.close()
        conn.close()
        return True
    except Exception as exc:
        logger.warning("SQLite safe copy failed for %s: %s", src, exc)
        try:
            shutil.copy2(src, dst)
            return True
        except Exception as exc2:
            logger.error("Raw copy also failed for %s: %s", src, exc2)
            return False


def _format_size(nbytes: int) -> str:
    """Human-readable file size."""
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}" if unit != "B" else f"{nbytes} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} TB"


def run_backup(args) -> None:
    """Create a zip backup of the Prometheus home directory."""
    prometheus_root = get_default_prometheus_root()

    if not prometheus_root.is_dir():
        print(f"Error: Prometheus home directory not found at {prometheus_root}")
        sys.exit(1)

    if args.output:
        out_path = Path(args.output).expanduser().resolve()
        if out_path.is_dir():
            stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
            out_path = out_path / f"prometheus-backup-{stamp}.zip"
    else:
        stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        out_path = Path.home() / f"prometheus-backup-{stamp}.zip"

    if out_path.suffix.lower() != ".zip":
        out_path = out_path.with_suffix(out_path.suffix + ".zip")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Scanning {display_prometheus_home()} ...")
    files_to_add: list[Tuple[Path, Path]] = []
    skipped_dirs = set()

    for dirpath, dirnames, filenames in os.walk(prometheus_root, followlinks=False):
        dp = Path(dirpath)
        rel_dir = dp.relative_to(prometheus_root)

        orig_dirnames = dirnames[:]
        dirnames[:] = [d for d in dirnames if d not in _EXCLUDED_DIRS]
        for removed in set(orig_dirnames) - set(dirnames):
            skipped_dirs.add(str(rel_dir / removed))

        for fname in filenames:
            fpath = dp / fname
            rel = fpath.relative_to(prometheus_root)

            if _should_exclude(rel):
                continue

            try:
                if fpath.resolve() == out_path.resolve():
                    continue
            except (OSError, ValueError):
                pass

            files_to_add.append((fpath, rel))

    if not files_to_add:
        print("No files to back up.")
        return

    file_count = len(files_to_add)
    print(f"Backing up {file_count} files ...")

    total_bytes = 0
    errors = []
    t0 = time.monotonic()

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for i, (abs_path, rel_path) in enumerate(files_to_add, 1):
            try:
                if abs_path.suffix == ".db":
                    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
                        tmp_db = Path(tmp.name)
                    if _safe_copy_db(abs_path, tmp_db):
                        zf.write(tmp_db, arcname=str(rel_path))
                        total_bytes += tmp_db.stat().st_size
                        tmp_db.unlink(missing_ok=True)
                    else:
                        tmp_db.unlink(missing_ok=True)
                        errors.append(f"  {rel_path}: SQLite safe copy failed")
                        continue
                else:
                    zf.write(abs_path, arcname=str(rel_path))
                    total_bytes += abs_path.stat().st_size
            except (PermissionError, OSError, ValueError) as exc:
                errors.append(f"  {rel_path}: {exc}")
                continue

            if i % 500 == 0:
                print(f"  {i}/{file_count} files ...")

    elapsed = time.monotonic() - t0
    zip_size = out_path.stat().st_size

    print()
    print(f"Backup complete: {out_path}")
    print(f"  Files:       {file_count}")
    print(f"  Original:    {_format_size(total_bytes)}")
    print(f"  Compressed:  {_format_size(zip_size)}")
    print(f"  Time:        {elapsed:.1f}s")

    if skipped_dirs:
        print("\n  Excluded directories:")
        for d in sorted(skipped_dirs):
            print(f"    {d}/")

    if errors:
        print(f"\n  Warnings ({len(errors)} files skipped):")
        for e in errors[:10]:
            print(e)
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")

    print(f"\nRestore with: prometheus import {out_path.name}")


def _validate_backup_zip(zf: zipfile.ZipFile) -> Tuple[bool, str]:
    """Check that a zip looks like a Prometheus backup."""
    names = zf.namelist()
    if not names:
        return False, "zip archive is empty"

    markers = {"config.yaml", ".env", "state.db"}
    found = set()
    for n in names:
        basename = Path(n).name
        if basename in markers:
            found.add(basename)

    if not found:
        return False, (
            "zip does not appear to be a Prometheus backup "
            "(no config.yaml, .env, or state databases found)"
        )

    return True, ""


def _detect_prefix(zf: zipfile.ZipFile) -> str:
    """Detect if the zip has a common directory prefix wrapping all entries."""
    names = [n for n in zf.namelist() if not n.endswith("/")]
    if not names:
        return ""

    parts_list = [Path(n).parts for n in names]

    first_parts = {p[0] for p in parts_list if len(p) > 1}
    if len(first_parts) == 1:
        prefix = first_parts.pop()
        if prefix in (".prometheus", "prometheus"):
            return prefix + "/"

    return ""


def run_import(args) -> None:
    """Restore a Prometheus backup from a zip file."""
    zip_path = Path(args.zipfile).expanduser().resolve()

    if not zip_path.is_file():
        print(f"Error: File not found: {zip_path}")
        sys.exit(1)

    if not zipfile.is_zipfile(zip_path):
        print(f"Error: Not a valid zip file: {zip_path}")
        sys.exit(1)

    prometheus_root = get_default_prometheus_root()

    with zipfile.ZipFile(zip_path, "r") as zf:
        ok, reason = _validate_backup_zip(zf)
        if not ok:
            print(f"Error: {reason}")
            sys.exit(1)

        prefix = _detect_prefix(zf)
        members = [n for n in zf.namelist() if not n.endswith("/")]
        file_count = len(members)

        print(f"Backup contains {file_count} files")
        print(f"Target: {display_prometheus_home()}")

        if prefix:
            print(f"Detected archive prefix: {prefix!r} (will be stripped)")

        has_config = (prometheus_root / "config.yaml").exists()
        has_env = (prometheus_root / ".env").exists()

        if (has_config or has_env) and not args.force:
            print()
            print("Warning: Target directory already has Prometheus configuration.")
            print("Importing will overwrite existing files with backup contents.")
            print()
            try:
                answer = input("Continue? [y/N] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nAborted.")
                sys.exit(1)
            if answer not in ("y", "yes"):
                print("Aborted.")
                return

        print(f"\nImporting {file_count} files ...")
        prometheus_root.mkdir(parents=True, exist_ok=True)

        errors = []
        restored = 0
        t0 = time.monotonic()

        for member in members:
            if prefix and member.startswith(prefix):
                rel = member[len(prefix) :]
            else:
                rel = member

            if not rel:
                continue

            target = prometheus_root / rel

            try:
                target.resolve().relative_to(prometheus_root.resolve())
            except ValueError:
                errors.append(f"  {rel}: path traversal blocked")
                continue

            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(target, "wb") as dst:
                    dst.write(src.read())
                restored += 1
            except (PermissionError, OSError) as exc:
                errors.append(f"  {rel}: {exc}")

            if restored % 500 == 0:
                print(f"  {restored}/{file_count} files ...")

        elapsed = time.monotonic() - t0

        print()
        print(f"Import complete: {restored} files restored in {elapsed:.1f}s")
        print(f"  Target: {display_prometheus_home()}")

        if errors:
            print(f"\n  Warnings ({len(errors)} files skipped):")
            for e in errors[:10]:
                print(e)
            if len(errors) > 10:
                print(f"  ... and {len(errors) - 10} more")

        profiles_dir = prometheus_root / "profiles"
        restored_profiles = []
        if profiles_dir.is_dir():
            try:
                from prometheus.cli.profiles import (
                    _get_wrapper_dir,
                    _is_wrapper_dir_in_path,
                    check_alias_collision,
                    create_wrapper_script,
                )

                for entry in sorted(profiles_dir.iterdir()):
                    if not entry.is_dir():
                        continue
                    profile_name = entry.name
                    if not (entry / "config.yaml").exists() and not (entry / ".env").exists():
                        continue
                    collision = check_alias_collision(profile_name)
                    if collision:
                        print(f"  Skipped alias '{profile_name}': {collision}")
                        restored_profiles.append((profile_name, False))
                    else:
                        wrapper = create_wrapper_script(profile_name)
                        restored_profiles.append((profile_name, wrapper is not None))

                if restored_profiles:
                    created = [n for n, ok in restored_profiles if ok]
                    skipped = [n for n, ok in restored_profiles if not ok]
                    if created:
                        print(f"\n  Profile aliases restored: {', '.join(created)}")
                    if skipped:
                        print(f"  Profile aliases skipped:  {', '.join(skipped)}")
                    if not _is_wrapper_dir_in_path():
                        print(f"\n  Note: {_get_wrapper_dir()} is not in your PATH.")
                        print("  Add to your shell config (~/.bashrc or ~/.zshrc):")
                        print('    export PATH="$HOME/.local/bin:$PATH"')
            except ImportError:
                if any(profiles_dir.iterdir()):
                    print("\n  Profiles detected but aliases could not be created.")
                    print("  Run: prometheus profile list  (after installing prometheus)")

        print()
        if not (prometheus_root / "prometheus-agent").is_dir():
            print("Note: The prometheus-agent codebase was not included in the backup.")
            print("  If this is a fresh install, run: prometheus update")

        if restored_profiles:
            gw_profiles = [n for n, _ in restored_profiles]
            print("\nTo re-enable gateway services for profiles:")
            for pname in gw_profiles:
                print(f"  prometheus -p {pname} gateway install")

        print("Done. Your Prometheus configuration has been restored.")


_QUICK_STATE_FILES = (
    "state.db",
    "config.yaml",
    ".env",
    "auth.json",
    "cron/jobs.json",
    "gateway_state.json",
    "channel_directory.json",
    "processes.json",
    "pairing",
    "platforms/pairing",
    "feishu_comment_pairing.json",
)

_QUICK_SNAPSHOTS_DIR = "state-snapshots"
_QUICK_DEFAULT_KEEP = 20


def _quick_snapshot_root(prometheus_home: Path | None = None) -> Path:
    home = prometheus_home or get_prometheus_home()
    return home / _QUICK_SNAPSHOTS_DIR


def create_quick_snapshot(
    label: str | None = None,
    prometheus_home: Path | None = None,
) -> str | None:
    """Create a quick state snapshot of critical files."""
    home = prometheus_home or get_prometheus_home()
    root = _quick_snapshot_root(home)

    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    snap_id = f"{ts}-{label}" if label else ts
    snap_dir = root / snap_id
    snap_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, int] = {}

    for rel in _QUICK_STATE_FILES:
        src = home / rel
        if not src.exists():
            continue

        if src.is_dir():
            for sub in src.rglob("*"):
                if not sub.is_file():
                    continue
                sub_rel = sub.relative_to(home).as_posix()
                dst = snap_dir / sub_rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(sub, dst)
                    manifest[sub_rel] = dst.stat().st_size
                except (OSError, PermissionError) as exc:
                    logger.warning("Could not snapshot %s: %s", sub_rel, exc)
            continue

        if not src.is_file():
            continue

        dst = snap_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)

        try:
            if src.suffix == ".db":
                if not _safe_copy_db(src, dst):
                    continue
            else:
                shutil.copy2(src, dst)
            manifest[rel] = dst.stat().st_size
        except (OSError, PermissionError) as exc:
            logger.warning("Could not snapshot %s: %s", rel, exc)

    if not manifest:
        shutil.rmtree(snap_dir, ignore_errors=True)
        return None

    meta = {
        "id": snap_id,
        "timestamp": ts,
        "label": label,
        "file_count": len(manifest),
        "total_size": sum(manifest.values()),
        "files": manifest,
    }
    with open(snap_dir / "manifest.json", "w") as f:
        json.dump(meta, f, indent=2)

    _prune_quick_snapshots(root, keep=_QUICK_DEFAULT_KEEP)

    logger.info("State snapshot created: %s (%d files)", snap_id, len(manifest))
    return snap_id


def list_quick_snapshots(
    limit: int = 20,
    prometheus_home: Path | None = None,
) -> list[dict[str, Any]]:
    """List existing quick state snapshots, most recent first."""
    root = _quick_snapshot_root(prometheus_home)
    if not root.exists():
        return []

    results = []
    for d in sorted(root.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        manifest_path = d / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path) as f:
                    results.append(json.load(f))
            except (json.JSONDecodeError, OSError):
                results.append({"id": d.name, "file_count": 0, "total_size": 0})
        if len(results) >= limit:
            break

    return results


def restore_quick_snapshot(
    snapshot_id: str,
    prometheus_home: Path | None = None,
) -> bool:
    """Restore state from a quick snapshot."""
    home = prometheus_home or get_prometheus_home()
    root = _quick_snapshot_root(home)
    snap_dir = root / snapshot_id

    if not snap_dir.is_dir():
        return False

    manifest_path = snap_dir / "manifest.json"
    if not manifest_path.exists():
        return False

    with open(manifest_path) as f:
        meta = json.load(f)

    restored = 0
    for rel in meta.get("files", {}):
        src = snap_dir / rel
        if not src.exists():
            continue

        dst = home / rel
        dst.parent.mkdir(parents=True, exist_ok=True)

        try:
            if dst.suffix == ".db":
                tmp = dst.parent / f".{dst.name}.snap_restore"
                shutil.copy2(src, tmp)
                dst.unlink(missing_ok=True)
                shutil.move(str(tmp), str(dst))
            else:
                shutil.copy2(src, dst)
            restored += 1
        except (OSError, PermissionError) as exc:
            logger.error("Failed to restore %s: %s", rel, exc)

    logger.info("Restored %d files from snapshot %s", restored, snapshot_id)
    return restored > 0


def _prune_quick_snapshots(root: Path, keep: int = _QUICK_DEFAULT_KEEP) -> int:
    """Remove oldest quick snapshots beyond the keep limit. Returns count deleted."""
    if not root.exists():
        return 0

    dirs = sorted(
        (d for d in root.iterdir() if d.is_dir()),
        key=lambda d: d.name,
        reverse=True,
    )

    deleted = 0
    for d in dirs[keep:]:
        try:
            shutil.rmtree(d)
            deleted += 1
        except OSError as exc:
            logger.warning("Failed to prune snapshot %s: %s", d.name, exc)

    return deleted


def prune_quick_snapshots(
    keep: int = _QUICK_DEFAULT_KEEP,
    prometheus_home: Path | None = None,
) -> int:
    """Manually prune quick snapshots. Returns count deleted."""
    return _prune_quick_snapshots(_quick_snapshot_root(prometheus_home), keep=keep)


def run_quick_backup(args) -> None:
    """CLI entry point for prometheus backup --quick."""
    label = getattr(args, "label", None)
    snap_id = create_quick_snapshot(label=label)
    if snap_id:
        print(f"State snapshot created: {snap_id}")
        snaps = list_quick_snapshots()
        print(f"  {len(snaps)} snapshot(s) stored in {display_prometheus_home()}/state-snapshots/")
        print(f"  Restore with: /snapshot restore {snap_id}")
    else:
        print("No state files found to snapshot.")


def _write_full_zip_backup(out_path: Path, prometheus_root: Path) -> Path | None:
    """Write a full zip snapshot of ``prometheus_root`` to ``out_path``."""
    files_to_add: list[Tuple[Path, Path]] = []
    try:
        for dirpath, dirnames, filenames in os.walk(prometheus_root, followlinks=False):
            dp = Path(dirpath)
            dirnames[:] = [d for d in dirnames if d not in _EXCLUDED_DIRS]

            for fname in filenames:
                fpath = dp / fname
                try:
                    rel = fpath.relative_to(prometheus_root)
                except ValueError:
                    continue

                if _should_exclude(rel):
                    continue

                try:
                    if fpath.resolve() == out_path.resolve():
                        continue
                except (OSError, ValueError):
                    pass

                files_to_add.append((fpath, rel))
    except OSError as exc:
        logger.warning("Full-zip backup: walk failed: %s", exc)
        return None

    if not files_to_add:
        return None

    try:
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for abs_path, rel_path in files_to_add:
                try:
                    if abs_path.suffix == ".db":
                        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
                            tmp_db = Path(tmp.name)
                        try:
                            if _safe_copy_db(abs_path, tmp_db):
                                zf.write(tmp_db, arcname=str(rel_path))
                        finally:
                            tmp_db.unlink(missing_ok=True)
                    else:
                        zf.write(abs_path, arcname=str(rel_path))
                except (PermissionError, OSError, ValueError) as exc:
                    logger.debug("Skipping %s in zip backup: %s", rel_path, exc)
                    continue
    except OSError as exc:
        logger.warning("Full-zip backup: zip write failed: %s", exc)
        with contextlib.suppress(OSError):
            out_path.unlink(missing_ok=True)
        return None

    return out_path


_PRE_UPDATE_BACKUPS_DIR = "backups"
_PRE_UPDATE_PREFIX = "pre-update-"
_PRE_UPDATE_DEFAULT_KEEP = 5


def _pre_update_backup_dir(prometheus_home: Path | None = None) -> Path:
    home = prometheus_home or get_prometheus_home()
    return home / _PRE_UPDATE_BACKUPS_DIR


def _prune_pre_update_backups(backup_dir: Path, keep: int) -> int:
    """Remove oldest pre-update backups beyond the keep limit."""
    if keep < 0:
        keep = 0
    if not backup_dir.exists():
        return 0

    backups = sorted(
        (
            p
            for p in backup_dir.iterdir()
            if p.is_file() and p.name.startswith(_PRE_UPDATE_PREFIX) and p.suffix.lower() == ".zip"
        ),
        key=lambda p: p.name,
        reverse=True,
    )

    deleted = 0
    for p in backups[keep:]:
        try:
            p.unlink()
            deleted += 1
        except OSError as exc:
            logger.warning("Failed to prune backup %s: %s", p.name, exc)

    return deleted


def create_pre_update_backup(
    prometheus_home: Path | None = None,
    keep: int = _PRE_UPDATE_DEFAULT_KEEP,
) -> Path | None:
    """Create a full zip backup of PROMETHEUS_HOME under ``backups/``."""
    prometheus_root = prometheus_home or get_default_prometheus_root()
    if not prometheus_root.is_dir():
        return None

    backup_dir = _pre_update_backup_dir(prometheus_root)
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("Could not create pre-update backup dir %s: %s", backup_dir, exc)
        return None

    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    out_path = backup_dir / f"{_PRE_UPDATE_PREFIX}{stamp}.zip"

    result = _write_full_zip_backup(out_path, prometheus_root)
    if result is None:
        return None

    _prune_pre_update_backups(backup_dir, keep=keep)
    return out_path


_PRE_MIGRATION_PREFIX = "pre-migration-"
_PRE_MIGRATION_DEFAULT_KEEP = 5


def _prune_pre_migration_backups(backup_dir: Path, keep: int) -> int:
    """Remove oldest pre-migration backups beyond the keep limit."""
    if keep < 0:
        keep = 0
    if not backup_dir.exists():
        return 0

    backups = sorted(
        (
            p
            for p in backup_dir.iterdir()
            if p.is_file()
            and p.name.startswith(_PRE_MIGRATION_PREFIX)
            and p.suffix.lower() == ".zip"
        ),
        key=lambda p: p.name,
        reverse=True,
    )

    deleted = 0
    for p in backups[keep:]:
        try:
            p.unlink()
            deleted += 1
        except OSError as exc:
            logger.warning("Failed to prune pre-migration backup %s: %s", p.name, exc)

    return deleted


def create_pre_migration_backup(
    prometheus_home: Path | None = None,
    keep: int = _PRE_MIGRATION_DEFAULT_KEEP,
) -> Path | None:
    """Create a full zip backup of PROMETHEUS_HOME under ``backups/`` before a migration."""
    prometheus_root = prometheus_home or get_default_prometheus_root()
    if not prometheus_root.is_dir():
        return None

    backup_dir = _pre_update_backup_dir(prometheus_root)
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("Could not create pre-migration backup dir %s: %s", backup_dir, exc)
        return None

    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    out_path = backup_dir / f"{_PRE_MIGRATION_PREFIX}{stamp}.zip"

    result = _write_full_zip_backup(out_path, prometheus_root)
    if result is None:
        return None

    _prune_pre_migration_backups(backup_dir, keep=keep)
    return out_path
