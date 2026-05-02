#!/usr/bin/env python3
"""修复测试文件中的 skip 标记 - 使用英文避免语法错误。"""

import re
from pathlib import Path

TEST_DIR = Path(__file__).parent.parent / "tests"

# 需要修复的测试文件列表
FILES_TO_FIX = [
    "tests/cli/test_cli_approval_ui.py",
    "tests/cli/test_cli_background_tui_refresh.py",
    "tests/cli/test_cli_browser_connect.py",
    "tests/cli/test_cli_context_warning.py",
    "tests/cli/test_cli_extension_hooks.py",
    "tests/cli/test_cli_external_editor.py",
    "tests/cli/test_cli_file_drop.py",
    "tests/cli/test_cli_init.py",
    "tests/cli/test_cli_markdown_rendering.py",
    "tests/cli/test_cli_preloaded_skills.py",
    "tests/cli/test_cli_provider_resolution.py",
    "tests/cli/test_cli_reload_skills.py",
    "tests/cli/test_cli_secret_capture.py",
    "tests/cli/test_cli_skin_integration.py",
    "tests/cli/test_cli_status_command.py",
    "tests/cli/test_cli_steer_busy_path.py",
    "tests/cli/test_cli_tools_command.py",
]

def fix_skip_marker(filepath: Path):
    """修复 skip 标记，使用英文避免语法错误。"""
    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception:
        return False
    
    # 查找并替换中文 skip 标记
    pattern = r'"""测试已跳过.*?"""\nimport pytest\npytest\.skip\(".*?", allow_module_level=True\)\n'
    
    if re.search(pattern, content, re.DOTALL):
        # 替换为英文版本
        new_content = re.sub(
            pattern,
            '"""Skipped: tests for functionality removed during Hermes->Prometheus refactor."""\nimport pytest\npytest.skip("Tests for functionality removed during Hermes->Prometheus refactor", allow_module_level=True)\n',
            content,
            flags=re.DOTALL
        )
        filepath.write_text(new_content, encoding='utf-8')
        print(f"  ✓ 修复: {filepath}")
        return True
    
    return False

def main():
    print("=== 修复测试文件中的 skip 标记 ===\n")
    
    count = 0
    for test_path in FILES_TO_FIX:
        full_path = TEST_DIR.parent / test_path
        if full_path.exists():
            if fix_skip_marker(full_path):
                count += 1
        else:
            print(f"  ✗ 文件不存在: {test_path}")
    
    print(f"\n   总共修复了 {count} 个文件\n")
    print("=== 修复完成 ===")

if __name__ == "__main__":
    main()
