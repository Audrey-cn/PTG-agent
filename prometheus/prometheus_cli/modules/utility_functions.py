"""
CLI 工具函数模块 - 从 main.py 中提取的通用工具函数
"""

import os
import sys
from pathlib import Path
from typing import Optional


def _relative_time(ts) -> str:
    """将时间戳转换为相对时间描述"""
    from datetime import datetime
    
    if not ts:
        return "never"
    
    now = datetime.now()
    delta = now - ts
    
    if delta.days > 0:
        return f"{delta.days}d ago"
    elif delta.seconds > 3600:
        return f"{delta.seconds // 3600}h ago"
    elif delta.seconds > 60:
        return f"{delta.seconds // 60}m ago"
    else:
        return "just now"


def _has_any_provider_configured() -> bool:
    """检查是否有任何提供商已配置"""
    try:
        from prometheus.prometheus_cli.config import get_prometheus_home
        from prometheus.prometheus_cli.models import load_providers
        
        providers = load_providers()
        return len(providers) > 0
    except:
        return False


def _resolve_last_session(source: str = "cli") -> Optional[str]:
    """解析最后一个会话"""
    try:
        from prometheus.prometheus_cli.config import get_prometheus_home
        
        home = get_prometheus_home()
        last_session_file = home / "last_session.txt"
        
        if last_session_file.exists():
            return last_session_file.read_text().strip()
    except:
        pass
    
    return None


def _probe_container(cmd: list, backend: str, via_sudo: bool = False) -> bool:
    """探测容器是否可用"""
    try:
        import subprocess
        
        if via_sudo:
            cmd = ["sudo"] + cmd
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        return result.returncode == 0
    except:
        return False


def _exec_in_container(container_info: dict, cli_args: list):
    """在容器中执行命令"""
    import subprocess
    
    cmd = [
        container_info["backend"],
        "exec",
        "-it",
        container_info["name"],
        "prometheus"
    ] + cli_args
    
    if container_info.get("via_sudo"):
        cmd = ["sudo"] + cmd
    
    os.execvp(cmd[0], cmd)


def _resolve_session_by_name_or_id(name_or_id: str) -> Optional[str]:
    """通过名称或ID解析会话"""
    try:
        from prometheus.prometheus_cli.config import get_prometheus_home
        
        home = get_prometheus_home()
        sessions_dir = home / "sessions"
        
        if not sessions_dir.exists():
            return None
        
        # 检查是否是有效的会话ID
        session_file = sessions_dir / f"{name_or_id}.json"
        if session_file.exists():
            return name_or_id
        
        # 检查是否是会话名称
        for session_file in sessions_dir.glob("*.json"):
            try:
                import json
                with open(session_file, 'r') as f:
                    session_data = json.load(f)
                
                if session_data.get("name") == name_or_id:
                    return session_file.stem
            except:
                continue
        
        return None
    except:
        return None


def _read_tui_active_session_file(path: Optional[str]) -> Optional[str]:
    """读取 TUI 活动会话文件"""
    if not path:
        return None
    
    try:
        with open(path, 'r') as f:
            return f.read().strip()
    except:
        return None


def _print_tui_exit_summary(session_id: Optional[str], active_session_file: Optional[str] = None) -> None:
    """打印 TUI 退出摘要"""
    if session_id:
        print(f"Session ID: {session_id}")
    
    if active_session_file:
        print(f"Active session file: {active_session_file}")


def _tui_need_npm_install(root: Path) -> bool:
    """检查是否需要 npm install"""
    node_modules = root / "node_modules"
    package_json = root / "package.json"
    
    if not node_modules.exists() or not package_json.exists():
        return True
    
    try:
        import json
        import time
        
        pkg_mtime = package_json.stat().st_mtime
        node_modules_mtime = node_modules.stat().st_mtime
        
        return pkg_mtime > node_modules_mtime
    except:
        return True


def _find_bundled_tui(tui_dir: Path) -> Optional[Path]:
    """查找捆绑的 TUI"""
    bundled_dir = tui_dir / "dist"
    
    if bundled_dir.exists():
        return bundled_dir
    
    return None


def _tui_build_needed(tui_dir: Path) -> bool:
    """检查是否需要构建 TUI"""
    package_json = tui_dir / "package.json"
    dist_dir = tui_dir / "dist"
    
    if not dist_dir.exists():
        return True
    
    try:
        import json
        import time
        
        pkg_mtime = package_json.stat().st_mtime
        dist_mtime = dist_dir.stat().st_mtime
        
        return pkg_mtime > dist_mtime
    except:
        return True


def _prometheus_ink_bundle_stale(tui_dir: Path) -> bool:
    """检查 Prometheus Ink 包是否过时"""
    try:
        from prometheus.prometheus_cli.config import get_prometheus_home
        
        home = get_prometheus_home()
        bundle_file = home / "prometheus_ink_bundle.json"
        
        if not bundle_file.exists():
            return True
        
        import json
        import time
        
        bundle_mtime = bundle_file.stat().st_mtime
        package_mtime = (tui_dir / "package.json").stat().st_mtime
        
        return package_mtime > bundle_mtime
    except:
        return True


def _ensure_tui_node() -> None:
    """确保 TUI Node 环境可用"""
    try:
        import subprocess
        
        # 检查 Node.js 是否可用
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        if result.returncode != 0:
            print("Error: Node.js is required for TUI but not found")
            sys.exit(1)
        
        # 检查 npm 是否可用
        result = subprocess.run(["npm", "--version"], capture_output=True, text=True)
        if result.returncode != 0:
            print("Error: npm is required for TUI but not found")
            sys.exit(1)
    except:
        print("Error: Failed to check Node.js/npm availability")
        sys.exit(1)


def _make_tui_argv(tui_dir: Path, tui_dev: bool) -> tuple[list[str], Path]:
    """创建 TUI 命令行参数"""
    if tui_dev:
        # 开发模式
        cmd = ["npm", "run", "dev"]
        cwd = tui_dir
    else:
        # 生产模式
        bundled = _find_bundled_tui(tui_dir)
        if not bundled:
            print("Error: TUI bundle not found")
            sys.exit(1)
        
        cmd = ["npx", "serve", "-s", "dist"]
        cwd = tui_dir
    
    return cmd, cwd


def _normalize_tui_toolsets(toolsets: object) -> list[str]:
    """标准化 TUI 工具集"""
    if toolsets is None:
        return []
    
    if isinstance(toolsets, str):
        return [ts.strip() for ts in toolsets.split(",") if ts.strip()]
    
    if isinstance(toolsets, list):
        return [str(ts) for ts in toolsets if ts]
    
    return []