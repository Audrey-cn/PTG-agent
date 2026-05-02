"""
CLI Chat 命令模块 - 处理 chat 相关的命令
"""

import sys
from typing import Optional


def cmd_chat(args) -> int:
    """处理 chat 命令"""
    from prometheus.prometheus_cli.modules.utility_functions import _require_tty
    
    # 确保在 TTY 中运行
    _require_tty("chat")
    
    # 解析会话参数
    session_id = None
    if args.session:
        from prometheus.prometheus_cli.modules.utility_functions import _resolve_session_by_name_or_id
        session_id = _resolve_session_by_name_or_id(args.session)
        if not session_id:
            print(f"Error: Session '{args.session}' not found")
            return 1
    
    # 解析工具集
    toolsets = []
    if args.toolsets:
        from prometheus.prometheus_cli.modules.utility_functions import _normalize_tui_toolsets
        toolsets = _normalize_tui_toolsets(args.toolsets)
    
    # 检查模型和提供商配置
    if not _has_any_provider_configured():
        print("No AI provider configured. Run 'prometheus setup' first.")
        return 1
    
    # 启动 TUI
    return _launch_tui(
        session_id=session_id,
        toolsets=toolsets,
        model=args.model,
        provider=args.provider,
        no_tools=args.no_tools
    )


def _has_any_provider_configured() -> bool:
    """检查是否有任何提供商已配置"""
    try:
        from prometheus.prometheus_cli.config import get_prometheus_home
        from prometheus.prometheus_cli.models import load_providers
        
        providers = load_providers()
        return len(providers) > 0
    except:
        return False


def _launch_tui(
    session_id: Optional[str] = None,
    toolsets: Optional[list] = None,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    no_tools: bool = False
) -> int:
    """启动 TUI"""
    try:
        from prometheus.prometheus_cli.modules.utility_functions import (
            _ensure_tui_node,
            _tui_need_npm_install,
            _tui_build_needed,
            _make_tui_argv
        )
        
        # 确保 Node.js 环境
        _ensure_tui_node()
        
        # 查找 TUI 目录
        from pathlib import Path
        tui_dir = Path(__file__).parent.parent.parent / "prometheus-web-ui"
        
        if not tui_dir.exists():
            print("Error: TUI directory not found")
            return 1
        
        # 检查是否需要 npm install
        if _tui_need_npm_install(tui_dir):
            print("Installing TUI dependencies...")
            import subprocess
            result = subprocess.run(["npm", "install"], cwd=tui_dir, capture_output=True)
            if result.returncode != 0:
                print("Error: Failed to install TUI dependencies")
                return 1
        
        # 检查是否需要构建
        if _tui_build_needed(tui_dir):
            print("Building TUI...")
            import subprocess
            result = subprocess.run(["npm", "run", "build"], cwd=tui_dir, capture_output=True)
            if result.returncode != 0:
                print("Error: Failed to build TUI")
                return 1
        
        # 准备环境变量
        env = os.environ.copy()
        
        if session_id:
            env["PROMETHEUS_SESSION_ID"] = session_id
        
        if toolsets:
            env["PROMETHEUS_TOOLSETS"] = ",".join(toolsets)
        
        if model:
            env["PROMETHEUS_MODEL"] = model
        
        if provider:
            env["PROMETHEUS_PROVIDER"] = provider
        
        if no_tools:
            env["PROMETHEUS_NO_TOOLS"] = "1"
        
        # 启动 TUI
        cmd, cwd = _make_tui_argv(tui_dir, tui_dev=False)
        
        print("Starting Prometheus TUI...")
        result = subprocess.run(cmd, cwd=cwd, env=env)
        
        return result.returncode
        
    except Exception as e:
        print(f"Error launching TUI: {e}")
        return 1