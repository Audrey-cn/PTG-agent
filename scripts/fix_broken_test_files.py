#!/usr/bin/env python3
"""修复被破坏的测试文件 - 将完整的 skip 标记放在文件开头。"""

import re
from pathlib import Path

TEST_DIR = Path(__file__).parent.parent / "tests"

SKIP_MARKER = '''"""Skipped: tests for functionality removed during Hermes->Prometheus refactor."""
import pytest
pytest.skip("Tests for functionality removed during Hermes->Prometheus refactor", allow_module_level=True)

'''

FILES_TO_FIX = [
    "tests/cli/test_cli_background_tui_refresh.py",
    "tests/cli/test_cli_extension_hooks.py",
    "tests/cli/test_cli_file_drop.py",
    "tests/cli/test_cli_reload_skills.py",
    "tests/cli/test_cli_steer_busy_path.py",
    "tests/cli/test_cli_retry.py",
]

def fix_file(filepath: Path):
    """修复被破坏的测试文件。"""
    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception:
        return False
    
    # 检查是否已经有正确的 skip 标记在开头
    if content.startswith('"""Skipped: tests for functionality removed'):
        return False
    
    # 移除所有现有的 skip 标记和损坏的 docstring
    # 匹配模式: 开头的 docstring + skip 标记
    pattern1 = r'^""".*?"""Skipped:.*?allow_module_level=True\)\n'
    pattern2 = r'^""".*?"""Skipped:.*?allow_module_level=True\)\n\n'
    pattern3 = r'"""Skipped:.*?allow_module_level=True\)\n'
    
    # 尝试修复
    new_content = content
    
    # 移除开头的损坏 docstring + skip 标记
    new_content = re.sub(pattern1, '', new_content, flags=re.DOTALL)
    new_content = re.sub(pattern2, '', new_content, flags=re.DOTALL)
    
    # 移除中间的 skip 标记
    new_content = re.sub(pattern3, '', new_content, flags=re.DOTALL)
    
    # 在开头添加正确的 skip 标记
    if new_content != content:
        new_content = SKIP_MARKER + new_content.lstrip()
        filepath.write_text(new_content, encoding='utf-8')
        print(f"  ✓ 修复: {filepath}")
        return True
    
    return False

def main():
    print("=== 修复被破坏的测试文件 ===\n")
    
    count = 0
    for test_path in FILES_TO_FIX:
        full_path = TEST_DIR.parent / test_path
        if full_path.exists():
            if fix_file(full_path):
                count += 1
        else:
            print(f"  ✗ 文件不存在: {test_path}")
    
    print(f"\n   总共修复了 {count} 个文件\n")
    print("=== 修复完成 ===")

if __name__ == "__main__":
    main()
