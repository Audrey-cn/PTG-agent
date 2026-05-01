"""Tirith pre-exec security scanning wrapper."""

import contextlib
import hashlib
import json
import logging
import os
import platform
import shutil
import stat
import subprocess
import tarfile
import tempfile
import threading
import time
import urllib.request

from prometheus.constants_core import get_prometheus_home

logger = logging.getLogger(__name__)

_REPO = "sheeki03/tirith"

_COSIGN_IDENTITY_REGEXP = (
    f"^https://github.com/{_REPO}/\\.github/workflows/release\\.yml@refs/tags/v"
)
_COSIGN_ISSUER = "https://token.actions.githubusercontent.com"


def _env_bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes")


def _env_int(key: str, default: int) -> int:
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def _load_security_config() -> dict:
    """Load security settings from config.yaml, with env var overrides."""
    defaults = {
        "tirith_enabled": True,
        "tirith_path": "tirith",
        "tirith_timeout": 5,
        "tirith_fail_open": True,
    }
    try:
        from prometheus.tools.config import get_config

        cfg_obj = get_config()
        cfg = cfg_obj.get("security", {}) or {}
    except Exception:
        cfg = {}

    return {
        "tirith_enabled": _env_bool(
            "TIRITH_ENABLED", cfg.get("tirith_enabled", defaults["tirith_enabled"])
        ),
        "tirith_path": os.getenv("TIRITH_BIN", cfg.get("tirith_path", defaults["tirith_path"])),
        "tirith_timeout": _env_int(
            "TIRITH_TIMEOUT", cfg.get("tirith_timeout", defaults["tirith_timeout"])
        ),
        "tirith_fail_open": _env_bool(
            "TIRITH_FAIL_OPEN", cfg.get("tirith_fail_open", defaults["tirith_fail_open"])
        ),
    }


_resolved_path: str | None | bool = None
_INSTALL_FAILED = False
_install_failure_reason: str = ""
_install_lock = threading.Lock()
_install_thread: threading.Thread | None = None
_MARKER_TTL = 86400


def _get_prometheus_home() -> str:
    """Return the Prometheus home directory, respecting PROMETHEUS_HOME env var."""
    return str(get_prometheus_home())


def _failure_marker_path() -> str:
    """Return the path to the install-failure marker file."""
    return os.path.join(_get_prometheus_home(), ".tirith-install-failed")


def _read_failure_reason() -> str | None:
    """Read the failure reason from the disk marker."""
    try:
        p = _failure_marker_path()
        mtime = os.path.getmtime(p)
        if (time.time() - mtime) >= _MARKER_TTL:
            return None
        with open(p) as f:
            return f.read().strip()
    except OSError:
        return None


def _is_install_failed_on_disk() -> bool:
    """Check if a recent install failure was persisted to disk."""
    reason = _read_failure_reason()
    if reason is None:
        return False
    if reason == "cosign_missing" and shutil.which("cosign"):
        _clear_install_failed()
        return False
    return True


def _mark_install_failed(reason: str = ""):
    """Persist install failure to disk to avoid retry on next process."""
    try:
        p = _failure_marker_path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(reason)
    except OSError:
        pass


def _clear_install_failed():
    """Remove the failure marker after successful install."""
    with contextlib.suppress(OSError):
        os.unlink(_failure_marker_path())


def _prometheus_bin_dir() -> str:
    """Return $PROMETHEUS_HOME/bin, creating it if needed."""
    d = os.path.join(_get_prometheus_home(), "bin")
    os.makedirs(d, exist_ok=True)
    return d


def _detect_target() -> str | None:
    """Return the Rust target triple for the current platform, or None."""
    system = platform.system()
    machine = platform.machine().lower()

    if system == "Darwin":
        plat = "apple-darwin"
    elif system in ("Linux", "Android"):
        plat = "unknown-linux-gnu"
    else:
        return None

    if machine in ("x86_64", "amd64"):
        arch = "x86_64"
    elif machine in ("aarch64", "arm64"):
        arch = "aarch64"
    else:
        return None

    return f"{arch}-{plat}"


def _download_file(url: str, dest: str, timeout: int = 10):
    """Download a URL to a local file."""
    req = urllib.request.Request(url)
    token = os.getenv("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"token {token}")
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest, "wb") as f:
        shutil.copyfileobj(resp, f)


def _verify_cosign(checksums_path: str, sig_path: str, cert_path: str) -> bool | None:
    """Verify cosign provenance signature on checksums.txt."""
    cosign = shutil.which("cosign")
    if not cosign:
        logger.info("cosign not found on PATH")
        return None

    try:
        result = subprocess.run(
            [
                cosign,
                "verify-blob",
                "--certificate",
                cert_path,
                "--signature",
                sig_path,
                "--certificate-identity-regexp",
                _COSIGN_IDENTITY_REGEXP,
                "--certificate-oidc-issuer",
                _COSIGN_ISSUER,
                checksums_path,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            logger.info("cosign provenance verification passed")
            return True
        else:
            logger.warning(
                "cosign verification failed (exit %d): %s", result.returncode, result.stderr.strip()
            )
            return False
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("cosign execution failed: %s", exc)
        return None


def _verify_checksum(archive_path: str, checksums_path: str, archive_name: str) -> bool:
    """Verify SHA-256 of the archive against checksums.txt."""
    expected = None
    with open(checksums_path) as f:
        for line in f:
            parts = line.strip().split("  ", 1)
            if len(parts) == 2 and parts[1] == archive_name:
                expected = parts[0]
                break
    if not expected:
        logger.warning("No checksum entry for %s", archive_name)
        return False

    sha = hashlib.sha256()
    with open(archive_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)
    actual = sha.hexdigest()
    if actual != expected:
        logger.warning("Checksum mismatch: expected %s, got %s", expected, actual)
        return False
    return True


def _install_tirith(*, log_failures: bool = True) -> Tuple[str | None, str]:
    """Download and install tirith to $PROMETHEUS_HOME/bin/tirith."""
    log = logger.warning if log_failures else logger.debug

    target = _detect_target()
    if not target:
        logger.info(
            "tirith auto-install: unsupported platform %s/%s", platform.system(), platform.machine()
        )
        return None, "unsupported_platform"

    archive_name = f"tirith-{target}.tar.gz"
    base_url = f"https://github.com/{_REPO}/releases/latest/download"

    tmpdir = tempfile.mkdtemp(prefix="tirith-install-")
    try:
        archive_path = os.path.join(tmpdir, archive_name)
        checksums_path = os.path.join(tmpdir, "checksums.txt")
        sig_path = os.path.join(tmpdir, "checksums.txt.sig")
        cert_path = os.path.join(tmpdir, "checksums.txt.pem")

        logger.info("tirith not found — downloading latest release for %s...", target)

        try:
            _download_file(f"{base_url}/{archive_name}", archive_path)
            _download_file(f"{base_url}/checksums.txt", checksums_path)
        except Exception as exc:
            log("tirith download failed: %s", exc)
            return None, "download_failed"

        cosign_verified = False
        if shutil.which("cosign"):
            try:
                _download_file(f"{base_url}/checksums.txt.sig", sig_path)
                _download_file(f"{base_url}/checksums.txt.pem", cert_path)
            except Exception as exc:
                logger.info("cosign artifacts unavailable (%s), proceeding with SHA-256 only", exc)
            else:
                cosign_result = _verify_cosign(checksums_path, sig_path, cert_path)
                if cosign_result is True:
                    cosign_verified = True
                elif cosign_result is False:
                    log("tirith install aborted: cosign provenance verification failed")
                    return None, "cosign_verification_failed"

        if not _verify_checksum(archive_path, checksums_path, archive_name):
            return None, "checksum_failed"

        with tarfile.open(archive_path, "r:gz") as tar:
            for member in tar.getmembers():
                if member.name == "tirith" or member.name.endswith("/tirith"):
                    if ".." in member.name:
                        continue
                    member.name = "tirith"
                    tar.extract(member, tmpdir)
                    break
            else:
                log("tirith binary not found in archive")
                return None, "binary_not_in_archive"

        src = os.path.join(tmpdir, "tirith")
        dest = os.path.join(_prometheus_bin_dir(), "tirith")
        try:
            shutil.move(src, dest)
        except OSError:
            try:
                shutil.copy(src, dest)
            except OSError:
                with contextlib.suppress(OSError):
                    os.unlink(dest)
                return None, "cross_device_copy_failed"
        os.chmod(dest, os.stat(dest).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        verification = "cosign + SHA-256" if cosign_verified else "SHA-256 only"
        logger.info("tirith installed to %s (%s)", dest, verification)
        return dest, ""

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _is_explicit_path(configured_path: str) -> bool:
    """Return True if the user explicitly configured a non-default tirith path."""
    return configured_path != "tirith"


def _resolve_tirith_path(configured_path: str) -> str:
    """Resolve the tirith binary path, auto-installing if necessary."""
    global _resolved_path, _install_failure_reason

    if _resolved_path is not None and _resolved_path is not _INSTALL_FAILED:
        return _resolved_path

    expanded = os.path.expanduser(configured_path)
    explicit = _is_explicit_path(configured_path)
    install_failed = _resolved_path is _INSTALL_FAILED

    if explicit:
        if os.path.isfile(expanded) and os.access(expanded, os.X_OK):
            _resolved_path = expanded
            return expanded
        found = shutil.which(expanded)
        if found:
            _resolved_path = found
            return found
        logger.warning("Configured tirith path %r not found; scanning disabled", configured_path)
        _resolved_path = _INSTALL_FAILED
        _install_failure_reason = "explicit_path_missing"
        return expanded

    found = shutil.which("tirith")
    if found:
        _resolved_path = found
        _install_failure_reason = ""
        _clear_install_failed()
        return found

    prometheus_bin = os.path.join(_prometheus_bin_dir(), "tirith")
    if os.path.isfile(prometheus_bin) and os.access(prometheus_bin, os.X_OK):
        _resolved_path = prometheus_bin
        _install_failure_reason = ""
        _clear_install_failed()
        return prometheus_bin

    if install_failed:
        if _install_failure_reason == "cosign_missing" and shutil.which("cosign"):
            _resolved_path = None
            _install_failure_reason = ""
            _clear_install_failed()
            install_failed = False
        else:
            return expanded

    if _install_thread is not None and _install_thread.is_alive():
        return expanded

    disk_reason = _read_failure_reason()
    if disk_reason is not None and _is_install_failed_on_disk():
        _resolved_path = _INSTALL_FAILED
        _install_failure_reason = disk_reason
        return expanded

    installed, reason = _install_tirith()
    if installed:
        _resolved_path = installed
        _install_failure_reason = ""
        _clear_install_failed()
        return installed

    _resolved_path = _INSTALL_FAILED
    _install_failure_reason = reason
    _mark_install_failed(reason)
    return expanded


def _background_install(*, log_failures: bool = True):
    """Background thread target: download and install tirith."""
    global _resolved_path, _install_failure_reason
    with _install_lock:
        if _resolved_path is not None:
            return

        found = shutil.which("tirith")
        if found:
            _resolved_path = found
            _install_failure_reason = ""
            return

        prometheus_bin = os.path.join(_prometheus_bin_dir(), "tirith")
        if os.path.isfile(prometheus_bin) and os.access(prometheus_bin, os.X_OK):
            _resolved_path = prometheus_bin
            _install_failure_reason = ""
            return

        installed, reason = _install_tirith(log_failures=log_failures)
        if installed:
            _resolved_path = installed
            _install_failure_reason = ""
            _clear_install_failed()
        else:
            _resolved_path = _INSTALL_FAILED
            _install_failure_reason = reason
            _mark_install_failed(reason)


def ensure_installed(*, log_failures: bool = True):
    """Ensure tirith is available, downloading in background if needed."""
    global _resolved_path, _install_thread, _install_failure_reason

    cfg = _load_security_config()
    if not cfg["tirith_enabled"]:
        return None

    if _resolved_path is not None and _resolved_path is not _INSTALL_FAILED:
        path = _resolved_path
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
        return None

    configured_path = cfg["tirith_path"]
    explicit = _is_explicit_path(configured_path)
    expanded = os.path.expanduser(configured_path)

    if explicit:
        if os.path.isfile(expanded) and os.access(expanded, os.X_OK):
            _resolved_path = expanded
            return expanded
        found = shutil.which(expanded)
        if found:
            _resolved_path = found
            return found
        _resolved_path = _INSTALL_FAILED
        _install_failure_reason = "explicit_path_missing"
        return None

    found = shutil.which("tirith")
    if found:
        _resolved_path = found
        _install_failure_reason = ""
        _clear_install_failed()
        return found

    prometheus_bin = os.path.join(_prometheus_bin_dir(), "tirith")
    if os.path.isfile(prometheus_bin) and os.access(prometheus_bin, os.X_OK):
        _resolved_path = prometheus_bin
        _install_failure_reason = ""
        _clear_install_failed()
        return prometheus_bin

    if _resolved_path is _INSTALL_FAILED:
        if _install_failure_reason == "cosign_missing" and shutil.which("cosign"):
            _resolved_path = None
            _install_failure_reason = ""
            _clear_install_failed()
        else:
            return None

    disk_reason = _read_failure_reason()
    if disk_reason is not None and _is_install_failed_on_disk():
        _resolved_path = _INSTALL_FAILED
        _install_failure_reason = disk_reason
        return None

    if _install_thread is None or not _install_thread.is_alive():
        _install_thread = threading.Thread(
            target=_background_install,
            kwargs={"log_failures": log_failures},
            daemon=True,
        )
        _install_thread.start()

    return None


_MAX_FINDINGS = 50
_MAX_SUMMARY_LEN = 500


def check_command_security(command: str) -> dict:
    """Run tirith security scan on a command.

    Exit code determines action (0=allow, 1=block, 2=warn). JSON enriches
    findings/summary. Spawn failures and timeouts respect fail_open config.
    Programming errors propagate.

    Returns:
        {"action": "allow"|"warn"|"block", "findings": [...], "summary": str}
    """
    cfg = _load_security_config()

    if not cfg["tirith_enabled"]:
        return {"action": "allow", "findings": [], "summary": ""}

    tirith_path = _resolve_tirith_path(cfg["tirith_path"])
    timeout = cfg["tirith_timeout"]
    fail_open = cfg["tirith_fail_open"]

    if tirith_path is None:
        logger.warning("tirith path resolved to None; scanning disabled")
        if fail_open:
            return {"action": "allow", "findings": [], "summary": "tirith path unavailable"}
        return {
            "action": "block",
            "findings": [],
            "summary": "tirith path unavailable (fail-closed)",
        }

    try:
        result = subprocess.run(
            [
                tirith_path,
                "check",
                "--json",
                "--non-interactive",
                "--shell",
                "posix",
                "--",
                command,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except OSError as exc:
        logger.warning("tirith spawn failed: %s", exc)
        if fail_open:
            return {"action": "allow", "findings": [], "summary": f"tirith unavailable: {exc}"}
        return {
            "action": "block",
            "findings": [],
            "summary": f"tirith spawn failed (fail-closed): {exc}",
        }
    except subprocess.TimeoutExpired:
        logger.warning("tirith timed out after %ds", timeout)
        if fail_open:
            return {"action": "allow", "findings": [], "summary": f"tirith timed out ({timeout}s)"}
        return {"action": "block", "findings": [], "summary": "tirith timed out (fail-closed)"}

    exit_code = result.returncode
    if exit_code == 0:
        action = "allow"
    elif exit_code == 1:
        action = "block"
    elif exit_code == 2:
        action = "warn"
    else:
        logger.warning("tirith returned unexpected exit code %d", exit_code)
        if fail_open:
            return {
                "action": "allow",
                "findings": [],
                "summary": f"tirith exit code {exit_code} (fail-open)",
            }
        return {
            "action": "block",
            "findings": [],
            "summary": f"tirith exit code {exit_code} (fail-closed)",
        }

    findings = []
    summary = ""
    try:
        data = json.loads(result.stdout) if result.stdout.strip() else {}
        raw_findings = data.get("findings", [])
        findings = raw_findings[:_MAX_FINDINGS]
        summary = (data.get("summary", "") or "")[:_MAX_SUMMARY_LEN]
    except (json.JSONDecodeError, AttributeError):
        logger.debug("tirith JSON parse failed, using exit code only")
        if action == "block":
            summary = "security issue detected (details unavailable)"
        elif action == "warn":
            summary = "security warning detected (details unavailable)"

    return {"action": action, "findings": findings, "summary": summary}
