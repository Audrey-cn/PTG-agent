"""File passthrough registry for remote terminal backends."""

from __future__ import annotations

import logging
import os
from contextvars import ContextVar
from pathlib import Path

from prometheus.cli.config import cfg_get

logger = logging.getLogger(__name__)

_registered_files_var: ContextVar[dict[str, str]] = ContextVar("_registered_files")


def _get_registered() -> dict[str, str]:
    try:
        return _registered_files_var.get()
    except LookupError:
        val: dict[str, str] = {}
        _registered_files_var.set(val)
        return val


_config_files: list[dict[str, str]] | None = None


def _resolve_prometheus_home() -> Path:
    from prometheus.constants_core import get_prometheus_home

    return get_prometheus_home()


def register_credential_file(
    relative_path: str,
    container_base: str = "/root/.prometheus",
) -> bool:
    prometheus_home = _resolve_prometheus_home()

    if os.path.isabs(relative_path):
        logger.warning(
            "credential_files: rejected absolute path %r (must be relative to PROMETHEUS_HOME)",
            relative_path,
        )
        return False

    host_path = prometheus_home / relative_path

    from prometheus.tools.security.path_security import validate_within_dir

    containment_error = validate_within_dir(host_path, prometheus_home)
    if containment_error:
        logger.warning(
            "credential_files: rejected path traversal %r (%s)",
            relative_path,
            containment_error,
        )
        return False

    resolved = host_path.resolve()
    if not resolved.is_file():
        logger.debug("credential_files: skipping %s (not found)", resolved)
        return False

    container_path = f"{container_base.rstrip('/')}/{relative_path}"
    _get_registered()[container_path] = str(resolved)
    logger.debug("credential_files: registered %s -> %s", resolved, container_path)
    return True


def register_credential_files(
    entries: list,
    container_base: str = "/root/.prometheus",
) -> list[str]:
    missing = []
    for entry in entries:
        if isinstance(entry, str):
            rel_path = entry.strip()
        elif isinstance(entry, dict):
            rel_path = (entry.get("path") or entry.get("name") or "").strip()
        else:
            continue
        if not rel_path:
            continue
        if not register_credential_file(rel_path, container_base):
            missing.append(rel_path)
    return missing


def _load_config_files() -> list[dict[str, str]]:
    global _config_files
    if _config_files is not None:
        return _config_files

    result: list[dict[str, str]] = []
    try:
        from prometheus.cli.config import read_raw_config

        prometheus_home = _resolve_prometheus_home()
        cfg = read_raw_config()
        cred_files = cfg_get(cfg, "terminal", "credential_files")
        if isinstance(cred_files, list):
            from prometheus.tools.security.path_security import validate_within_dir

            for item in cred_files:
                if isinstance(item, str) and item.strip():
                    rel = item.strip()
                    if os.path.isabs(rel):
                        logger.warning(
                            "credential_files: rejected absolute config path %r",
                            rel,
                        )
                        continue
                    host_path = prometheus_home / rel
                    containment_error = validate_within_dir(host_path, prometheus_home)
                    if containment_error:
                        logger.warning(
                            "credential_files: rejected config path traversal %r (%s)",
                            rel,
                            containment_error,
                        )
                        continue
                    resolved_path = host_path.resolve()
                    if resolved_path.is_file():
                        container_path = f"/root/.prometheus/{rel}"
                        result.append(
                            {
                                "host_path": str(resolved_path),
                                "container_path": container_path,
                            }
                        )
    except Exception as e:
        logger.warning("Could not read terminal.credential_files from config: %s", e)

    _config_files = result
    return _config_files


def get_credential_file_mounts() -> list[dict[str, str]]:
    mounts: dict[str, str] = {}

    for container_path, host_path in _get_registered().items():
        if Path(host_path).is_file():
            mounts[container_path] = host_path

    for entry in _load_config_files():
        cp = entry["container_path"]
        if cp not in mounts and Path(entry["host_path"]).is_file():
            mounts[cp] = entry["host_path"]

    return [{"host_path": hp, "container_path": cp} for cp, hp in mounts.items()]


def get_skills_directory_mount(
    container_base: str = "/root/.prometheus",
) -> list[dict[str, str]]:
    mounts = []
    prometheus_home = _resolve_prometheus_home()
    skills_dir = prometheus_home / "skills"
    if skills_dir.is_dir():
        host_path = _safe_skills_path(skills_dir)
        mounts.append(
            {
                "host_path": host_path,
                "container_path": f"{container_base.rstrip('/')}/skills",
            }
        )

    try:
        from prometheus.agent.skill_utils import get_external_skills_dirs

        for idx, ext_dir in enumerate(get_external_skills_dirs()):
            if ext_dir.is_dir():
                host_path = _safe_skills_path(ext_dir)
                mounts.append(
                    {
                        "host_path": host_path,
                        "container_path": f"{container_base.rstrip('/')}/external_skills/{idx}",
                    }
                )
    except ImportError:
        pass

    return mounts


_safe_skills_tempdir: Optional[Path] = None


def _safe_skills_path(skills_dir: Path) -> str:
    global _safe_skills_tempdir

    symlinks = [p for p in skills_dir.rglob("*") if p.is_symlink()]
    if not symlinks:
        return str(skills_dir)

    for link in symlinks:
        logger.warning(
            "credential_files: skipping symlink in skills dir: %s -> %s", link, os.readlink(link)
        )

    import atexit
    import shutil
    import tempfile

    if _safe_skills_tempdir and _safe_skills_tempdir.is_dir():
        shutil.rmtree(_safe_skills_tempdir, ignore_errors=True)

    safe_dir = Path(tempfile.mkdtemp(prefix="prometheus-skills-safe-"))
    _safe_skills_tempdir = safe_dir

    for item in skills_dir.rglob("*"):
        if item.is_symlink():
            continue
        rel = item.relative_to(skills_dir)
        target = safe_dir / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif item.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(item), str(target))

    def _cleanup():
        if safe_dir.is_dir():
            shutil.rmtree(safe_dir, ignore_errors=True)

    atexit.register(_cleanup)
    logger.info("credential_files: created symlink-safe skills copy at %s", safe_dir)
    return str(safe_dir)


def iter_skills_files(
    container_base: str = "/root/.prometheus",
) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []

    prometheus_home = _resolve_prometheus_home()
    skills_dir = prometheus_home / "skills"
    if skills_dir.is_dir():
        container_root = f"{container_base.rstrip('/')}/skills"
        for item in skills_dir.rglob("*"):
            if item.is_symlink() or not item.is_file():
                continue
            rel = item.relative_to(skills_dir)
            result.append(
                {
                    "host_path": str(item),
                    "container_path": f"{container_root}/{rel}",
                }
            )

    try:
        from prometheus.agent.skill_utils import get_external_skills_dirs

        for idx, ext_dir in enumerate(get_external_skills_dirs()):
            if not ext_dir.is_dir():
                continue
            container_root = f"{container_base.rstrip('/')}/external_skills/{idx}"
            for item in ext_dir.rglob("*"):
                if item.is_symlink() or not item.is_file():
                    continue
                rel = item.relative_to(ext_dir)
                result.append(
                    {
                        "host_path": str(item),
                        "container_path": f"{container_root}/{rel}",
                    }
                )
    except ImportError:
        pass

    return result


_CACHE_DIRS: list[Tuple[str, str]] = [
    ("cache/documents", "document_cache"),
    ("cache/images", "image_cache"),
    ("cache/audio", "audio_cache"),
    ("cache/screenshots", "browser_screenshots"),
]


def get_cache_directory_mounts(
    container_base: str = "/root/.prometheus",
) -> list[dict[str, str]]:
    from prometheus.constants_core import get_prometheus_dir

    mounts: list[dict[str, str]] = []
    for new_subpath, old_name in _CACHE_DIRS:
        host_dir = get_prometheus_dir(new_subpath, old_name)
        if host_dir.is_dir():
            container_path = f"{container_base.rstrip('/')}/{new_subpath}"
            mounts.append(
                {
                    "host_path": str(host_dir),
                    "container_path": container_path,
                }
            )
    return mounts


def iter_cache_files(
    container_base: str = "/root/.prometheus",
) -> list[dict[str, str]]:
    from prometheus.constants_core import get_prometheus_dir

    result: list[dict[str, str]] = []
    for new_subpath, old_name in _CACHE_DIRS:
        host_dir = get_prometheus_dir(new_subpath, old_name)
        if not host_dir.is_dir():
            continue
        container_root = f"{container_base.rstrip('/')}/{new_subpath}"
        for item in host_dir.rglob("*"):
            if item.is_symlink() or not item.is_file():
                continue
            rel = item.relative_to(host_dir)
            result.append(
                {
                    "host_path": str(item),
                    "container_path": f"{container_root}/{rel}",
                }
            )
    return result


def clear_credential_files() -> None:
    _get_registered().clear()
