from __future__ import annotations

import json
import logging
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime

logger = logging.getLogger("prometheus.debug")

_REDACT_KEYS = {
    "key",
    "api_key",
    "token",
    "secret",
    "password",
    "app_secret",
    "app_key",
    "bot_token",
}


def _redact(obj: object, depth: int = 0) -> object:
    if depth > 10:
        return "..."
    if isinstance(obj, dict):
        return {
            k: "***REDACTED***" if k.lower() in _REDACT_KEYS else _redact(v, depth + 1)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_redact(item, depth + 1) for item in obj]
    return obj


def _get_installed_packages() -> List[str]:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            packages = json.loads(result.stdout)
            return [f"{p['name']}=={p['version']}" for p in packages]
    except Exception:
        pass
    return []


def _get_recent_errors(lines: int = 50) -> List[str]:
    try:
        from prometheus.logs import read_recent_logs

        log_entries = read_recent_logs(lines=lines)
        return [e for e in log_entries if "ERROR" in e or "CRITICAL" in e]
    except Exception:
        return []


def _get_agent_state() -> dict:
    state: dict = {}
    try:
        from prometheus.agents.manager import get_agent_manager

        mgr = get_agent_manager()
        agents = mgr.list_all()
        state["active_agents"] = len(agents)
        state["agents"] = [{"name": a.name, "state": a.state} for a in agents[:10]]
    except Exception:
        state["active_agents"] = 0
        state["agents"] = []
    return state


def generate_debug_report() -> dict:
    report: dict = {
        "timestamp": datetime.now(UTC).isoformat(),
        "system": {
            "python_version": sys.version,
            "python_executable": sys.executable,
            "platform": platform.platform(),
            "os_name": os.name,
            "architecture": platform.architecture(),
            "hostname": platform.node(),
        },
    }

    try:
        from prometheus.constants_core import PROMETHEUS_VERSION

        report["prometheus_version"] = PROMETHEUS_VERSION
    except Exception:
        report["prometheus_version"] = "unknown"

    try:
        from prometheus.config import Config as PrometheusConfig

        cfg = PrometheusConfig.load()
        config_dict = cfg.to_dict()
        report["config"] = _redact(config_dict)
    except Exception as e:
        report["config"] = {"error": str(e)}

    report["installed_packages"] = _get_installed_packages()

    try:
        from prometheus.config import get_prometheus_home

        home = get_prometheus_home()
        report["prometheus_home"] = str(home)
        report["prometheus_home_exists"] = home.exists()
    except Exception:
        report["prometheus_home"] = "unknown"

    report["recent_errors"] = _get_recent_errors()
    report["agent_state"] = _get_agent_state()

    try:
        from prometheus.plugins import get_plugin_manager

        pm = get_plugin_manager()
        report["plugins"] = pm.list_plugins()
    except Exception:
        report["plugins"] = []

    return report


def upload_debug_report(report: dict) -> str:
    try:
        from prometheus.config import get_prometheus_home

        debug_dir = get_prometheus_home() / "debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"debug_report_{ts}.json"
        filepath = debug_dir / filename
        filepath.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
        )
        return str(filepath)
    except Exception as e:
        logger.error("Failed to save debug report: %s", e)
        return f"保存失败: {e}"


def format_debug_report(report: dict) -> str:
    lines: List[str] = []
    lines.append("=" * 60)
    lines.append("  Prometheus Debug Report")
    lines.append("=" * 60)
    lines.append("")

    lines.append(f"时间: {report.get('timestamp', 'unknown')}")
    lines.append(f"版本: {report.get('prometheus_version', 'unknown')}")
    lines.append("")

    sys_info = report.get("system", {})
    lines.append("--- System ---")
    lines.append(f"  Python: {sys_info.get('python_version', 'unknown')}")
    lines.append(f"  Platform: {sys_info.get('platform', 'unknown')}")
    lines.append(f"  Architecture: {sys_info.get('architecture', 'unknown')}")
    lines.append(f"  Hostname: {sys_info.get('hostname', 'unknown')}")
    lines.append("")

    lines.append("--- Config (redacted) ---")
    config = report.get("config", {})
    if isinstance(config, dict):
        for section, values in config.items():
            if isinstance(values, dict):
                lines.append(f"  [{section}]")
                for k, v in values.items():
                    lines.append(f"    {k}: {v}")
            else:
                lines.append(f"  {section}: {values}")
    lines.append("")

    lines.append(f"--- Installed Packages ({len(report.get('installed_packages', []))}) ---")
    for pkg in report.get("installed_packages", [])[:30]:
        lines.append(f"  {pkg}")
    remaining = len(report.get("installed_packages", [])) - 30
    if remaining > 0:
        lines.append(f"  ... and {remaining} more")
    lines.append("")

    errors = report.get("recent_errors", [])
    lines.append(f"--- Recent Errors ({len(errors)}) ---")
    for err in errors[:20]:
        lines.append(f"  {err.strip()}")
    lines.append("")

    agent_state = report.get("agent_state", {})
    lines.append("--- Agent State ---")
    lines.append(f"  Active agents: {agent_state.get('active_agents', 0)}")
    for a in agent_state.get("agents", []):
        lines.append(f"  · {a.get('name', '?')} [{a.get('state', '?')}]")
    lines.append("")

    plugins = report.get("plugins", [])
    lines.append(f"--- Plugins ({len(plugins)}) ---")
    for p in plugins:
        lines.append(
            f"  · {p.get('name', '?')} v{p.get('version', '?')} {'loaded' if p.get('loaded') else 'not loaded'}"
        )
    lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)
