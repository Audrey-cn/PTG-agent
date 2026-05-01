from __future__ import annotations


def cmd_gateway(args) -> None:
    action = getattr(args, "action", None)
    if action == "start":
        cmd_gateway_start(args)
    elif action == "stop":
        cmd_gateway_stop(args)
    elif action == "status":
        cmd_gateway_status(args)
    elif action == "logs":
        cmd_gateway_logs(args)
    elif action == "restart":
        cmd_gateway_restart(args)
    elif action == "serve":
        _run_gateway_server(args)
    else:
        _print_gateway_help()


def _print_gateway_help() -> None:
    print("\n🌐 Gateway 管理\n")
    print("  用法:")
    print("    ptg gateway start [--platform <平台>]  启动网关")
    print("    ptg gateway stop                       停止网关")
    print("    ptg gateway status                     查看状态")
    print("    ptg gateway logs [--lines N]           查看日志")
    print("    ptg gateway restart [--platform <平台>] 重启网关\n")


def cmd_gateway_start(args) -> None:
    from prometheus.gateway_manager import start_gateway

    platform = getattr(args, "platform", "cli")
    result = start_gateway(platform=platform)
    if result:
        print(f"\n✅ Gateway 已启动 (platform={platform})\n")
    else:
        print("\n⚠️  Gateway 已在运行或启动失败\n")


def cmd_gateway_stop(args) -> None:
    from prometheus.gateway_manager import stop_gateway

    result = stop_gateway()
    if result:
        print("\n✅ Gateway 已停止\n")
    else:
        print("\n⚠️  Gateway 未运行\n")


def cmd_gateway_status(args) -> None:
    from prometheus.gateway_manager import gateway_status

    status = gateway_status()
    print("\n🌐 Gateway 状态\n")
    if status.get("running"):
        print("  状态: 运行中")
        print(f"  PID: {status.get('pid')}")
        print(f"  日志: {status.get('log_file', 'N/A')}")
    else:
        print("  状态: 未运行")
    print()


def cmd_gateway_logs(args) -> None:
    from pathlib import Path

    lines = getattr(args, "lines", 50)
    log_file = Path.home() / ".prometheus" / "gateway.log"
    if not log_file.exists():
        print("\n⚠️  日志文件不存在\n")
        return
    print(f"\n📜 Gateway 日志 (最后 {lines} 行)\n")
    with open(log_file, encoding="utf-8", errors="ignore") as f:
        all_lines = f.readlines()
    for line in all_lines[-lines:]:
        print("  " + line.rstrip())
    print()


def cmd_gateway_restart(args) -> None:
    from prometheus.gateway_manager import start_gateway, stop_gateway

    platform = getattr(args, "platform", "cli")
    stop_gateway()
    result = start_gateway(platform=platform)
    if result:
        print(f"\n✅ Gateway 已重启 (platform={platform})\n")
    else:
        print("\n⚠️  Gateway 重启失败\n")


def _run_gateway_server(args) -> None:
    from prometheus.gateway.config import load_gateway_config
    from prometheus.gateway.run import GatewayRunner

    platform = getattr(args, "platform", "cli")
    print(f"\n🌐 启动 Gateway 服务 (platform={platform})\n")
    runner = GatewayRunner()
    config = load_gateway_config()
    runner.start(config)
    try:
        import time

        while runner.is_running():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止...")
        runner.stop()
