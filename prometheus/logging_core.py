from __future__ import annotations

"""Centralized logging setup for Prometheus Agent."""

import contextlib
import logging
import os
import threading
from collections.abc import Sequence
from logging.handlers import RotatingFileHandler
from pathlib import Path

from prometheus.constants_core import get_config_path, get_prometheus_home

_logging_initialized = False

_session_context = threading.local()

_LOG_FORMAT = "%(asctime)s %(levelname)s%(session_tag)s %(name)s: %(message)s"
_LOG_FORMAT_VERBOSE = "%(asctime)s - %(name)s - %(levelname)s%(session_tag)s - %(message)s"

_NOISY_LOGGERS = (
    "openai",
    "openai._base_client",
    "httpx",
    "httpcore",
    "asyncio",
    "hpack",
    "hpack.hpack",
    "grpc",
    "modal",
    "urllib3",
    "urllib3.connectionpool",
    "websockets",
    "charset_normalizer",
    "markdown_it",
)


def set_session_context(session_id: str) -> None:
    """Set the session ID for the current thread.

    All subsequent log records on this thread will include ``[session_id]``
    in the formatted output.  Call at the start of ``run_conversation()``.
    """
    _session_context.session_id = session_id


def clear_session_context() -> None:
    """Clear the session ID for the current thread."""
    _session_context.session_id = None


def _install_session_record_factory() -> None:
    """Replace the global LogRecord factory with one that adds ``session_tag``."""
    current_factory = logging.getLogRecordFactory()
    if getattr(current_factory, "_prometheus_session_injector", False):
        return

    def _session_record_factory(*args, **kwargs):
        record = current_factory(*args, **kwargs)
        sid = getattr(_session_context, "session_id", None)
        record.session_tag = f" [{sid}]" if sid else ""
        return record

    _session_record_factory._prometheus_session_injector = True
    logging.setLogRecordFactory(_session_record_factory)


_install_session_record_factory()


class _ComponentFilter(logging.Filter):
    """Only pass records whose logger name starts with one of *prefixes*."""

    def __init__(self, prefixes: Sequence[str]) -> None:
        super().__init__()
        self._prefixes = tuple(prefixes)

    def filter(self, record: logging.LogRecord) -> bool:
        return record.name.startswith(self._prefixes)


COMPONENT_PREFIXES = {
    "gateway": ("gateway",),
    "agent": ("agent", "run_agent", "model_tools", "batch_runner"),
    "tools": ("tools",),
    "cli": ("prometheus_cli", "cli"),
    "cron": ("cron",),
}


def setup_logging(
    *,
    prometheus_home: Path | None = None,
    log_level: str | None = None,
    max_size_mb: int | None = None,
    backup_count: int | None = None,
    mode: str | None = None,
    force: bool = False,
) -> Path:
    """Configure the Prometheus logging subsystem.

    Safe to call multiple times — the second call is a no-op unless
    *force* is ``True``.
    """
    global _logging_initialized
    home = prometheus_home or get_prometheus_home()
    log_dir = home / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    cfg_level, cfg_max_size, cfg_backup = _read_logging_config()

    level_name = (log_level or cfg_level or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    max_bytes = (max_size_mb or cfg_max_size or 5) * 1024 * 1024
    backups = backup_count or cfg_backup or 3

    try:
        from prometheus.redact import RedactingFormatter
    except ImportError:
        RedactingFormatter = logging.Formatter

    root = logging.getLogger()

    _add_rotating_handler(
        root,
        log_dir / "agent.log",
        level=level,
        max_bytes=max_bytes,
        backup_count=backups,
        formatter=RedactingFormatter(_LOG_FORMAT)
        if RedactingFormatter != logging.Formatter
        else logging.Formatter(_LOG_FORMAT),
    )

    _add_rotating_handler(
        root,
        log_dir / "errors.log",
        level=logging.WARNING,
        max_bytes=2 * 1024 * 1024,
        backup_count=2,
        formatter=RedactingFormatter(_LOG_FORMAT)
        if RedactingFormatter != logging.Formatter
        else logging.Formatter(_LOG_FORMAT),
    )

    if mode == "gateway":
        _add_rotating_handler(
            root,
            log_dir / "gateway.log",
            level=logging.INFO,
            max_bytes=5 * 1024 * 1024,
            backup_count=3,
            formatter=RedactingFormatter(_LOG_FORMAT)
            if RedactingFormatter != logging.Formatter
            else logging.Formatter(_LOG_FORMAT),
            log_filter=_ComponentFilter(COMPONENT_PREFIXES["gateway"]),
        )

    if _logging_initialized and not force:
        return log_dir

    if root.level == logging.NOTSET or root.level > level:
        root.setLevel(level)

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    _logging_initialized = True
    return log_dir


def setup_verbose_logging() -> None:
    """Enable DEBUG-level console logging for ``--verbose`` / ``-v`` mode."""
    try:
        from prometheus.redact import RedactingFormatter
    except ImportError:
        RedactingFormatter = logging.Formatter

    root = logging.getLogger()

    for h in root.handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler):
            if getattr(h, "_prometheus_verbose", False):
                return

    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter_cls = (
        RedactingFormatter if RedactingFormatter != logging.Formatter else logging.Formatter
    )
    handler.setFormatter(formatter_cls(_LOG_FORMAT_VERBOSE, datefmt="%H:%M:%S"))
    handler._prometheus_verbose = True
    root.addHandler(handler)

    if root.level > logging.DEBUG:
        root.setLevel(logging.DEBUG)

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


class _ManagedRotatingFileHandler(RotatingFileHandler):
    """RotatingFileHandler that ensures group-writable perms in managed mode."""

    def __init__(self, *args, **kwargs):
        try:
            from prometheus.config import is_managed

            self._managed = is_managed()
        except ImportError:
            self._managed = False
        super().__init__(*args, **kwargs)

    def _chmod_if_managed(self):
        if self._managed:
            with contextlib.suppress(OSError):
                os.chmod(self.baseFilename, 0o660)

    def _open(self):
        stream = super()._open()
        self._chmod_if_managed()
        return stream

    def doRollover(self):
        super().doRollover()
        self._chmod_if_managed()


def _add_rotating_handler(
    logger: logging.Logger,
    path: Path,
    *,
    level: int,
    max_bytes: int,
    backup_count: int,
    formatter: logging.Formatter,
    log_filter: logging.Filter | None = None,
) -> None:
    """Add a ``RotatingFileHandler`` to *logger*, skipping if one already
    exists for the same resolved file path (idempotent).
    """
    resolved = path.resolve()
    for existing in logger.handlers:
        if (
            isinstance(existing, RotatingFileHandler)
            and Path(getattr(existing, "baseFilename", "")).resolve() == resolved
        ):
            return

    path.parent.mkdir(parents=True, exist_ok=True)
    handler = _ManagedRotatingFileHandler(
        str(path),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(formatter)
    if log_filter is not None:
        handler.addFilter(log_filter)
    logger.addHandler(handler)


def _read_logging_config():
    """Best-effort read of ``logging.*`` from config.yaml.

    Returns ``(level, max_size_mb, backup_count)`` — any may be ``None``.
    """
    try:
        import yaml

        config_path = get_config_path()
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            log_cfg = cfg.get("logging", {})
            if isinstance(log_cfg, dict):
                return (
                    log_cfg.get("level"),
                    log_cfg.get("max_size_mb"),
                    log_cfg.get("backup_count"),
                )
    except Exception:
        pass
    return (None, None, None)


def get_recent_logs(lines: int = 50, level: str | None = None) -> list[str]:
    """Get recent log messages.

    Args:
        lines: Maximum number of lines to return
        level: Optional log level filter (debug, info, warning, error)

    Returns:
        List of log message strings
    """
    logs = []
    log_file = os.environ.get("PROMETHEUS_LOG_FILE")

    level_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
    }
    filter_level = level_map.get(level.lower() if level else "") if level else None

    if log_file and Path(log_file).exists():
        try:
            with open(log_file, encoding="utf-8") as f:
                all_lines = f.readlines()
                for line in all_lines[-lines:]:
                    if filter_level:
                        try:
                            if "[DEBUG]" in line:
                                msg_level = logging.DEBUG
                            elif "[INFO]" in line:
                                msg_level = logging.INFO
                            elif "[WARNING]" in line:
                                msg_level = logging.WARNING
                            elif "[ERROR]" in line:
                                msg_level = logging.ERROR
                            else:
                                continue

                            if msg_level < filter_level:
                                continue
                        except Exception:
                            continue
                    logs.append(line.strip())
        except Exception:
            pass

    if not logs:
        root_logger = logging.getLogger()
        for h in root_logger.handlers:
            if isinstance(h, logging.StreamHandler) and hasattr(h, "stream"):
                try:
                    if hasattr(h.stream, "getvalue"):
                        content = h.stream.getvalue()
                        if content:
                            all_lines = content.split("\n")
                            for line in all_lines[-lines:]:
                                if line.strip():
                                    logs.append(line.strip())
                except Exception:
                    pass

    return logs[-lines:] if len(logs) > lines else logs
