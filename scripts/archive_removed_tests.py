#!/usr/bin/env python3
"""归档已删除功能的测试文件。"""

import os
import shutil
from pathlib import Path

# 要归档的测试文件列表（基于之前的分析）
FILES_TO_ARCHIVE = [
    # 核心模块测试（已删除的功能）
    "tests/test_agent_infra.py",
    "tests/test_vector_memory.py", 
    "tests/test_knowledge.py",
    "tests/test_agent_modules.py",
    "tests/test_reflection_correction.py",
    
    # CLI 测试（已删除的功能）
    "tests/cli/test_cli_skin_integration.py",
    "tests/cli/test_cli_steer_busy_path.py",
    "tests/cli/test_setup.py",
    "tests/cli/test_cli_markdown_rendering.py",
    "tests/cli/test_cli_preloaded_skills.py",
    "tests/cli/test_plugins.py",
    "tests/cli/test_cli_init.py",
    "tests/cli/test_cli_provider_resolution.py",
    "tests/cli/test_gateway.py",
    "tests/cli/test_cli_browser_connect.py",
    "tests/cli/test_cli_status_command.py",
    "tests/cli/test_doctor.py",
    "tests/cli/test_cli_extension_hooks.py",
    "tests/cli/test_cli_background_tui_refresh.py",
    "tests/cli/test_cli_tools_command.py",
    "tests/cli/test_cron.py",
    "tests/cli/test_cli_external_editor.py",
    "tests/cli/test_config.py",
    "tests/cli/test_cli_approval_ui.py",
    "tests/cli/test_cli_secret_capture.py",
    "tests/cli/test_models.py",
    "tests/cli/test_cli_retry.py",
    "tests/cli/test_cli_reload_skills.py",
    "tests/cli/test_cli_context_warning.py",
    "tests/cli/test_cli_file_drop.py",
    
    # Gateway 测试（已删除的功能）
    "tests/gateway/test_discord_connect.py",
    "tests/gateway/test_feishu.py",
    "tests/gateway/test_delivery.py",
    "tests/gateway/test_session.py",
    "tests/gateway/test_api_server.py",
    "tests/gateway/test_weixin.py",
    "tests/gateway/test_slack.py",
    "tests/gateway/test_wecom.py",
    "tests/gateway/test_stream_consumer.py",
    "tests/gateway/test_matrix.py",
    "tests/gateway/test_gateway_shutdown.py",
    "tests/gateway/test_webhook_adapter.py",
    "tests/gateway/test_teams.py",
]

ARCHIVE_DIR = Path("tests/archived")


def archive_files():
    """归档测试文件。"""
    print("=== 归档已删除功能的测试文件 ===\n")
    
    archived_count = 0
    skipped_count = 0
    
    for file_path in FILES_TO_ARCHIVE:
        source = Path(file_path)
        if not source.exists():
            print(f"  ⚠️ 跳过: {file_path} (文件不存在)")
            skipped_count += 1
            continue
            
        # 创建归档目录结构
        relative_dir = source.parent.relative_to("tests")
        archive_subdir = ARCHIVE_DIR / relative_dir
        archive_subdir.mkdir(parents=True, exist_ok=True)
        
        # 移动文件到归档目录
        destination = archive_subdir / source.name
        shutil.move(str(source), str(destination))
        print(f"  ✓ 归档: {file_path} -> {destination}")
        archived_count += 1
    
    print(f"\n   总共归档了 {archived_count} 个文件")
    print(f"   跳过了 {skipped_count} 个不存在的文件")
    
    # 创建归档说明文件
    readme_content = """# 归档测试文件说明

## 概述
此目录包含在 Hermes→Prometheus 重构过程中删除的功能的测试文件。

## 归档原因
- 这些测试文件引用的功能模块在重构过程中被删除
- 保留这些文件作为历史记录，便于未来参考
- 当前测试套件已跳过这些文件，不会影响测试运行

## 文件列表
- `core/`: 核心模块的测试文件（已删除的功能）
- `cli/`: CLI 相关的测试文件（已删除的功能）  
- `gateway/`: Gateway 相关的测试文件（已删除的功能）

## 注意事项
- 这些测试文件当前无法运行，因为对应的功能已不存在
- 如需恢复这些功能，需要同时恢复相应的实现模块
- 归档时间: 2026-05-02
"""
    
    (ARCHIVE_DIR / "README.md").write_text(readme_content, encoding='utf-8')
    print(f"  📝 创建归档说明: {ARCHIVE_DIR}/README.md")
    
    print("\n=== 完成 ===")


if __name__ == "__main__":
    archive_files()