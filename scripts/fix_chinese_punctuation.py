#!/usr/bin/env python3
"""修复测试文件中的语法错误 - 将中文冒号替换为英文冒号。"""

import re
from pathlib import Path

TEST_DIR = Path(__file__).parent.parent / "tests"

def fix_chinese_punctuation(filepath: Path):
    """修复中文标点符号导致的语法错误。"""
    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception:
        return False
    
    # 替换中文冒号为英文冒号
    new_content = content.replace('：', ':')
    
    if new_content != content:
        filepath.write_text(new_content, encoding='utf-8')
        print(f"  ✓ 修复: {filepath}")
        return True
    
    return False

def main():
    print("=== 修复测试文件中的中文标点符号 ===\n")
    
    count = 0
    for py_file in sorted(TEST_DIR.rglob("*.py")):
        if "__pycache__" in str(py_file):
            continue
        
        if fix_chinese_punctuation(py_file):
            count += 1
    
    print(f"\n   总共修复了 {count} 个文件\n")
    print("=== 修复完成 ===")

if __name__ == "__main__":
    main()
