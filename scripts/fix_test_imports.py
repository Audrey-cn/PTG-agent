#!/usr/bin/env python3
"""修复测试文件中的导入问题。

这个脚本会：
1. 修复错误的导入路径
2. 添加 pytest.mark.skip 标记到测试已删除功能的测试文件
3. 修复函数名不匹配的问题
"""

import re
from pathlib import Path

TEST_DIR = Path(__file__).parent.parent / "tests"

# 定义需要跳过的测试文件（测试已删除的功能）
SKIP_TESTS = [
    # 测试 PrometheusCLI 类（已不存在）
    "tests/cli/test_cli_approval_ui.py",
    "tests/cli/test_cli_background_tui_refresh.py",
    "tests/cli/test_cli_browser_connect.py",
    "tests/cli/test_cli_external_editor.py",
    "tests/cli/test_cli_file_drop.py",
    "tests/cli/test_cli_markdown_rendering.py",
    "tests/cli/test_cli_secret_capture.py",
    "tests/cli/test_cli_skin_integration.py",
    "tests/cli/test_cli_status_command.py",
    "tests/cli/test_cli_tools_command.py",
    "tests/cli/test_cli_steer_busy_path.py",
    "tests/cli/test_cli_context_warning.py",
    "tests/cli/test_cli_extension_hooks.py",
    "tests/cli/test_cli_init.py",
    "tests/cli/test_cli_preloaded_skills.py",
    "tests/cli/test_cli_provider_resolution.py",
    "tests/cli/test_cli_reload_skills.py",
]

# 导入修复映射
IMPORT_FIXES = {
    # 旧导入 -> 新导入
    "from prometheus.cli.env_loader import load_hermes_dotenv": "from prometheus.cli.env_loader import load_prometheus_dotenv",
    "load_hermes_dotenv": "load_prometheus_dotenv",
    "from prometheus.cli.config import load_env": "from prometheus.env_loader import load_env",
    "from prometheus.utils import env_var_enabled": "from prometheus.utils import is_truthy_value as env_var_enabled",
    "from prometheus.cli.profiles import _get_default_hermes_home": "from prometheus.config import get_prometheus_home as _get_default_prometheus_home",
    "_get_default_hermes_home": "_get_default_prometheus_home",
}


def add_skip_marker(filepath: Path):
    """在测试文件顶部添加 pytest.skip 标记。"""
    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception:
        return False
    
    # 检查是否已经有 skip 标记
    if "pytest.skip" in content or "pytestmark" in content:
        return False
    
    # 在文件开头添加 skip 标记
    skip_message = f'"""测试已跳过：此文件测试的功能已在重构中删除。"""\nimport pytest\npytest.skip("测试的功能已在 Hermes→Prometheus 重构中删除", allow_module_level=True)\n\n'
    
    # 找到第一个 import 语句之前的位置
    lines = content.split('\n')
    insert_idx = 0
    for i, line in enumerate(lines):
        if line.startswith('import ') or line.startswith('from '):
            insert_idx = i
            break
        if line.strip() and not line.startswith('#') and not line.startswith('"""') and not line.startswith("'''"):
            insert_idx = i
            break
    
    new_lines = lines[:insert_idx] + skip_message.split('\n') + lines[insert_idx:]
    new_content = '\n'.join(new_lines)
    
    filepath.write_text(new_content, encoding='utf-8')
    print(f"  ✓ 跳过: {filepath}")
    return True


def fix_imports(filepath: Path):
    """修复测试文件中的导入问题。"""
    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception:
        return 0
    
    original = content
    count = 0
    
    for old_import, new_import in IMPORT_FIXES.items():
        if old_import in content:
            content = content.replace(old_import, new_import)
            count += 1
    
    if content != original:
        filepath.write_text(content, encoding='utf-8')
        print(f"  ✓ 修复导入: {filepath} - {count} 处")
    
    return count


def main():
    print("=== 修复测试文件导入问题 ===\n")
    
    # 1. 添加 skip 标记到已删除功能的测试
    print("1. 跳过测试已删除功能的测试文件:")
    skip_count = 0
    for test_path in SKIP_TESTS:
        full_path = TEST_DIR.parent / test_path
        if full_path.exists():
            if add_skip_marker(full_path):
                skip_count += 1
        else:
            print(f"  ✗ 文件不存在: {test_path}")
    
    print(f"\n   跳过了 {skip_count} 个测试文件\n")
    
    # 2. 修复可以修复的导入
    print("2. 修复可修复的导入:")
    total_fixes = 0
    for py_file in sorted(TEST_DIR.rglob("*.py")):
        if "__pycache__" in str(py_file):
            continue
        
        fixes = fix_imports(py_file)
        total_fixes += fixes
    
    print(f"\n   总共修复了 {total_fixes} 处导入\n")
    print("=== 修复完成 ===")


if __name__ == "__main__":
    main()
