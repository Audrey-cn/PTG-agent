#!/usr/bin/env python3
"""修复 prometheus/genes/ 目录下的导入路径。"""

import os
from pathlib import Path

GENES_DIR = Path("/Users/audrey/ptg-agent/prometheus/genes")

# 定义导入修复映射
IMPORT_FIXES = {
    "from genes.": "from prometheus.genes.",
    "from storage import": "from prometheus.storage import",
    "from knowledge import": "from prometheus.knowledge import",
    "from memory import": "from prometheus.memory import",
    "from compiler.": "from prometheus.compiler.",
    "from vector_memory import": "from prometheus.vector_memory import",
}


def fix_imports_in_file(filepath: Path) -> bool:
    """修复单个文件的导入。"""
    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception as e:
        print(f"  ✗ 读取失败: {filepath} - {e}")
        return False
    
    new_content = content
    for old_import, new_import in IMPORT_FIXES.items():
        new_content = new_content.replace(old_import, new_import)
    
    if new_content != content:
        filepath.write_text(new_content, encoding='utf-8')
        print(f"  ✓ 修复: {filepath}")
        return True
    
    return False


def main():
    """主函数。"""
    print("=== 修复 prometheus/genes/ 目录下的导入路径 ===\n")
    
    fixed_count = 0
    for filepath in GENES_DIR.glob("*.py"):
        if fix_imports_in_file(filepath):
            fixed_count += 1
    
    print(f"\n   总共修复了 {fixed_count} 个文件\n")
    print("=== 完成 ===")


if __name__ == "__main__":
    main()
