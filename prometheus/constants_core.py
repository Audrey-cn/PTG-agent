"""Shared constants for Prometheus Agent."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def get_prometheus_home() -> Path:
    """Return the Prometheus home directory (default: ~/.prometheus).

    Reads PROMETHEUS_HOME env var, falls back to ~/.prometheus.
    This is the single source of truth — all other copies should import this.
    """
    val = os.environ.get("PROMETHEUS_HOME", "").strip()
    return Path(val) if val else Path.home() / ".prometheus"


def get_default_prometheus_root() -> Path:
    """Return the root Prometheus directory for profile-level operations.

    In standard deployments this is ``~/.prometheus``.

    In Docker or custom deployments where ``PROMETHEUS_HOME`` points outside
    ``~/.prometheus`` (e.g. ``/opt/data``), returns ``PROMETHEUS_HOME`` directly
    — that IS the root.

    In profile mode where ``PROMETHEUS_HOME`` is ``<root>/profiles/<name>``,
    returns ``<root>`` so that ``profile list`` can see all profiles.
    Works both for standard (``~/.prometheus/profiles/coder``) and Docker
    (``/opt/data/profiles/coder``) layouts.

    Import-safe — no dependencies beyond stdlib.
    """
    native_home = Path.home() / ".prometheus"
    env_home = os.environ.get("PROMETHEUS_HOME", "")
    if not env_home:
        return native_home
    env_path = Path(env_home)
    try:
        env_path.resolve().relative_to(native_home.resolve())
        return native_home
    except ValueError:
        pass

    if env_path.parent.name == "profiles":
        return env_path.parent.parent

    return env_path


def get_optional_skills_dir(default: Path | None = None) -> Path:
    """Return the optional-skills directory, honoring package-manager wrappers.

    Packaged installs may ship ``optional-skills`` outside the Python package
    tree and expose it via ``PROMETHEUS_OPTIONAL_SKILLS``.
    """
    override = os.getenv("PROMETHEUS_OPTIONAL_SKILLS", "").strip()
    if override:
        return Path(override)
    if default is not None:
        return default
    return get_prometheus_home() / "optional-skills"


def get_prometheus_dir(new_subpath: str, old_name: str) -> Path:
    """Resolve a Prometheus subdirectory with backward compatibility.

    New installs get the consolidated layout (e.g. ``cache/images``).
    Existing installs that already have the old path (e.g. ``image_cache``)
    keep using it — no migration required.

    Args:
        new_subpath: Preferred path relative to PROMETHEUS_HOME (e.g. ``"cache/images"``).
        old_name: Legacy path relative to PROMETHEUS_HOME (e.g. ``"image_cache"``).

    Returns:
        Absolute ``Path`` — old location if it exists on disk, otherwise the new one.
    """
    home = get_prometheus_home()
    old = home / old_name
    if old.exists():
        return old
    return home / new_subpath


def get_prometheus_home_display() -> str:
    """Return the Prometheus home directory as a display string."""
    return str(get_prometheus_home())


def display_prometheus_home() -> str:
    """Return a user-friendly display string for the current PROMETHEUS_HOME.

    Uses ``~/`` shorthand for readability::

        default:  ``~/.prometheus``
        profile:  ``~/.prometheus/profiles/coder``
        custom:   ``/opt/prometheus-custom``

    Use this in **user-facing** print/log messages instead of hardcoding
    ``~/.prometheus``.  For code that needs a real ``Path``, use
    :func:`get_prometheus_home` instead.
    """
    home = get_prometheus_home()
    try:
        return "~/" + str(home.relative_to(Path.home()))
    except ValueError:
        return str(home)


def get_subprocess_home() -> str | None:
    """Return a per-profile HOME directory for subprocesses, or None.

    When ``{PROMETHEUS_HOME}/home/`` exists on disk, subprocesses should use it
    as ``HOME`` so system tools (git, ssh, gh, npm …) write their configs
    inside the Prometheus data directory instead of the OS-level ``/root`` or
    ``~/``.  This provides:

    * **Docker persistence** — tool configs land inside the persistent volume.
    * **Profile isolation** — each profile gets its own git identity, SSH
      keys, gh tokens, etc.

    The Python process's own ``os.environ["HOME"]`` and ``Path.home()`` are
    **never** modified — only subprocess environments should inject this value.
    Activation is directory-based: if the ``home/`` subdirectory doesn't
    exist, returns ``None`` and behavior is unchanged.
    """
    prometheus_home = os.getenv("PROMETHEUS_HOME")
    if not prometheus_home:
        return None
    profile_home = os.path.join(prometheus_home, "home")
    if os.path.isdir(profile_home):
        return profile_home
    return None


VALID_REASONING_EFFORTS = ("minimal", "low", "medium", "high", "xhigh")


def parse_reasoning_effort(effort: str) -> dict[Any, Any] | None:
    """Parse a reasoning effort level into a config dict.

    Valid levels: "none", "minimal", "low", "medium", "high", "xhigh".
    Returns None when the input is empty or unrecognized (caller uses default).
    Returns {"enabled": False} for "none".
    Returns {"enabled": True, "effort": <level>} for valid effort levels.
    """
    if not effort or not effort.strip():
        return None
    effort = effort.strip().lower()
    if effort == "none":
        return {"enabled": False}
    if effort in VALID_REASONING_EFFORTS:
        return {"enabled": True, "effort": effort}
    return None


def is_termux() -> bool:
    """Return True when running inside a Termux (Android) environment.

    Checks ``TERMUX_VERSION`` (set by Termux) or the Termux-specific
    ``PREFIX`` path.  Import-safe — no heavy deps.
    """
    prefix = os.getenv("PREFIX", "")
    return bool(os.getenv("TERMUX_VERSION") or "com.termux/files/usr" in prefix)


_wsl_detected: bool | None = None


def is_wsl() -> bool:
    """Return True when running inside WSL (Windows Subsystem for Linux).

    Checks ``/proc/version`` for the ``microsoft`` marker that both WSL1
    and WSL2 inject.  Result is cached for the process lifetime.
    Import-safe — no heavy deps.
    """
    global _wsl_detected
    if _wsl_detected is not None:
        return _wsl_detected
    try:
        with open("/proc/version") as f:
            _wsl_detected = "microsoft" in f.read().lower()
    except Exception:
        _wsl_detected = False
    return _wsl_detected


_container_detected: bool | None = None


def is_container() -> bool:
    """Return True when running inside a Docker/Podman container.

    Checks ``/.dockerenv`` (Docker), ``/run/.containerenv`` (Podman),
    and ``/proc/1/cgroup`` for container runtime markers.  Result is
    cached for the process lifetime.  Import-safe — no heavy deps.
    """
    global _container_detected
    if _container_detected is not None:
        return _container_detected
    if os.path.exists("/.dockerenv"):
        _container_detected = True
        return True
    if os.path.exists("/run/.containerenv"):
        _container_detected = True
        return True
    try:
        with open("/proc/1/cgroup") as f:
            cgroup = f.read()
            if "docker" in cgroup or "podman" in cgroup or "/lxc/" in cgroup:
                _container_detected = True
                return True
    except OSError:
        pass
    _container_detected = False
    return False


def get_config_path() -> Path:
    """Return the path to ``config.yaml`` under PROMETHEUS_HOME.

    Replaces the ``get_prometheus_home() / "config.yaml"`` pattern repeated
    in 7+ files.
    """
    return get_prometheus_home() / "config.yaml"


def get_skills_dir() -> Path:
    """Return the path to the skills directory under PROMETHEUS_HOME."""
    return get_prometheus_home() / "skills"


def get_env_path() -> Path:
    """Return the path to the ``.env`` file under PROMETHEUS_HOME."""
    return get_prometheus_home() / ".env"


def apply_ipv4_preference(force: bool = False) -> None:
    """Monkey-patch ``socket.getaddrinfo`` to prefer IPv4 connections.

    On servers with broken or unreachable IPv6, Python tries AAAA records
    first and hangs for the full TCP timeout before falling back to IPv4.
    This affects httpx, requests, urllib, the OpenAI SDK — everything that
    uses ``socket.getaddrinfo``.

    When *force* is True, patches ``getaddrinfo`` so that calls with
    ``family=AF_UNSPEC`` (the default) resolve as ``AF_INET`` instead,
    skipping IPv6 entirely.  If no A record exists, falls back to the
    original unfiltered resolution so pure-IPv6 hosts still work.

    Safe to call multiple times — only patches once.
    Set ``network.force_ipv4: true`` in ``config.yaml`` to enable.
    """
    if not force:
        return

    import socket

    if getattr(socket.getaddrinfo, "_prometheus_ipv4_patched", False):
        return

    _original_getaddrinfo = socket.getaddrinfo

    def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        if family == 0:
            try:
                return _original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
            except socket.gaierror:
                return _original_getaddrinfo(host, port, family, type, proto, flags)
        return _original_getaddrinfo(host, port, family, type, proto, flags)

    _ipv4_getaddrinfo._prometheus_ipv4_patched = True
    socket.getaddrinfo = _ipv4_getaddrinfo


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_CODEX_BASE_URL = "https://chatgpt.com/backend-api/codex"
DEFAULT_QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
OPENROUTER_MODELS_URL = f"{OPENROUTER_BASE_URL}/models"

AI_GATEWAY_BASE_URL = "https://ai-gateway.vercel.sh/v1"


PROMETHEUS_VERSION = "0.8.0"
PROMETHEUS_CODENAME = "Prometheus"

PROMETHEUS_ENV_VARS = {
    "PROMETHEUS_HOME": "Prometheus 主目录路径",
    "PROMETHEUS_OPTIONAL_SKILLS": "可选技能目录覆盖",
    "PROMETHEUS_INFERENCE_PROVIDER": "默认推理提供者",
    "PROMETHEUS_NOUS_MIN_KEY_TTL_SECONDS": "Nous API 密钥最小 TTL（秒）",
    "PROMETHEUS_NOUS_TIMEOUT_SECONDS": "Nous API 超时（秒）",
    "OPENAI_API_KEY": "OpenAI API 密钥",
    "OPENROUTER_API_KEY": "OpenRouter API 密钥",
    "OPENAI_BASE_URL": "OpenAI API 基础 URL",
    "OPENROUTER_BASE_URL": "OpenRouter API 基础 URL",
    "CUSTOM_BASE_URL": "自定义 API 基础 URL",
    "AZURE_FOUNDRY_BASE_URL": "Azure Foundry 基础 URL",
    "AZURE_FOUNDRY_API_KEY": "Azure Foundry API 密钥",
    "AZURE_ANTHROPIC_KEY": "Azure Anthropic 密钥",
    "ANTHROPIC_API_KEY": "Anthropic API 密钥",
}
