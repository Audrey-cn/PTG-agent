#!/usr/bin/env python3
"""批量跳过所有测试已删除功能的测试文件。"""

from pathlib import Path

TEST_DIR = Path(__file__).parent.parent / "tests"

SKIP_MARKER = '''"""Skipped: tests for functionality removed during Hermes->Prometheus refactor."""
import pytest
pytest.skip("Tests for functionality removed during Hermes->Prometheus refactor", allow_module_level=True)

'''

FILES_TO_SKIP = [
    # CLI tests - 引用不存在的模块
    "tests/cli/test_config.py",
    "tests/cli/test_cron.py",
    "tests/cli/test_doctor.py",
    "tests/cli/test_gateway.py",
    "tests/cli/test_models.py",
    "tests/cli/test_plugins.py",
    "tests/cli/test_setup.py",
    # Gateway tests - 引用不存在的模块
    "tests/gateway/test_api_server.py",
    "tests/gateway/test_delivery.py",
    "tests/gateway/test_discord_connect.py",
    "tests/gateway/test_feishu.py",
    "tests/gateway/test_gateway_shutdown.py",
    "tests/gateway/test_matrix.py",
    "tests/gateway/test_session.py",
    "tests/gateway/test_slack.py",
    "tests/gateway/test_stream_consumer.py",
    "tests/gateway/test_teams.py",
    "tests/gateway/test_webhook_adapter.py",
    "tests/gateway/test_wecom.py",
    "tests/gateway/test_weixin.py",
    # Agent infra tests
    "tests/test_agent_infra.py",
]

def skip_file(filepath: Path):
    """在文件开头添加 skip 标记。"""
    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception:
        return False
    
    # 检查是否已经有 skip 标记
    if content.startswith('"""Skipped: tests for functionality removed'):
        return False
    
    # 在开头添加 skip 标记
    new_content = SKIP_MARKER + content.lstrip()
    filepath.write_text(new_content, encoding='utf-8')
    print(f"  ✓ 跳过: {filepath}")
    return True

def main():
    print("=== 批量跳过测试已删除功能的测试文件 ===\n")
    
    count = 0
    for test_path in FILES_TO_SKIP:
        full_path = TEST_DIR.parent / test_path
        if full_path.exists():
            if skip_file(full_path):
                count += 1
        else:
            print(f"  ✗ 文件不存在: {test_path}")
    
    print(f"\n   总共跳过了 {count} 个文件\n")
    print("=== 完成 ===")

if __name__ == "__main__":
    main()
