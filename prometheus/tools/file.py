"""
Prometheus 文件操作工具
读取、写入、搜索文件
"""
import os
import re
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from .registry import tool_result, tool_error

# 敏感路径黑名单
SENSITIVE_PATHS = ['/etc/', '/boot/', '/usr/lib/systemd/', '/var/', '/sys/']
BLOCKED_PATHS = ['/dev/', '/proc/', '/sys/']

# 最大读取字符数
MAX_READ_CHARS = 100000


def is_safe_path(path: str) -> bool:
    """检查路径是否安全"""
    expanded = os.path.expanduser(path)
    abs_path = os.path.abspath(expanded)
    
    # 检查敏感路径
    for blocked in SENSITIVE_PATHS + BLOCKED_PATHS:
        if abs_path.startswith(blocked):
            return False
    return True


def read_file(path: str, offset: int = 1, limit: int = 500) -> Dict[str, Any]:
    """
    读取文件
    
    Args:
        path: 文件路径
        offset: 起始行号（1-indexed）
        limit: 最大行数
    
    Returns:
        包含 content, lines, truncated 的字典
    """
    try:
        # 安全检查
        if not is_safe_path(path):
            return {"error": "禁止访问敏感路径"}
        
        expanded = os.path.expanduser(path)
        if not os.path.exists(expanded):
            return {"error": f"文件不存在: {path}"}
        
        if not os.path.isfile(expanded):
            return {"error": f"不是文件: {path}"}
        
        # 读取文件
        with open(expanded, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        
        total_lines = len(lines)
        
        # 分页
        start = max(0, offset - 1)
        end = min(start + limit, total_lines)
        
        selected_lines = lines[start:end]
        content = ''.join(selected_lines)
        
        # 截断检查
        truncated = end < total_lines
        
        return {
            "content": content,
            "lines": f"{start+1}-{end}",
            "total_lines": total_lines,
            "truncated": truncated,
            "path": path
        }
    
    except UnicodeDecodeError:
        return {"error": "无法解码文件（可能是二进制文件）"}
    except Exception as e:
        return {"error": f"读取失败: {str(e)}"}


def write_file(path: str, content: str) -> Dict[str, Any]:
    """
    写入文件
    
    Args:
        path: 文件路径
        content: 文件内容
    
    Returns:
        包含 success, path 的字典
    """
    try:
        # 安全检查
        if not is_safe_path(path):
            return {"error": "禁止写入敏感路径"}
        
        expanded = os.path.expanduser(path)
        
        # 创建父目录
        parent = os.path.dirname(expanded)
        if parent:
            os.makedirs(parent, exist_ok=True)
        
        # 写入文件
        with open(expanded, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return {
            "success": True,
            "path": path,
            "bytes": len(content.encode('utf-8'))
        }
    
    except Exception as e:
        return {"error": f"写入失败: {str(e)}"}


def patch_file(path: str, old_string: str, new_string: str) -> Dict[str, Any]:
    """
    补丁替换
    
    Args:
        path: 文件路径
        old_string: 要替换的文本
        new_string: 替换后的文本
    
    Returns:
        包含 success, changes 的字典
    """
    try:
        # 安全检查
        if not is_safe_path(path):
            return {"error": "禁止修改敏感路径"}
        
        expanded = os.path.expanduser(path)
        
        if not os.path.exists(expanded):
            return {"error": f"文件不存在: {path}"}
        
        # 读取文件
        with open(expanded, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        # 查找并替换
        if old_string not in content:
            return {"error": "未找到要替换的文本"}
        
        new_content = content.replace(old_string, new_string, 1)
        
        # 写入文件
        with open(expanded, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        return {
            "success": True,
            "path": path,
            "changes": 1
        }
    
    except Exception as e:
        return {"error": f"补丁失败: {str(e)}"}


def search_files(pattern: str, path: str = ".", glob: Optional[str] = None, 
                limit: int = 50) -> Dict[str, Any]:
    """
    搜索文件内容
    
    Args:
        pattern: 搜索模式（正则）
        path: 搜索路径
        glob: 文件过滤（如 *.py）
        limit: 最大结果数
    
    Returns:
        包含 matches, count 的字典
    """
    try:
        expanded = os.path.expanduser(path)
        
        if not os.path.exists(expanded):
            return {"error": f"路径不存在: {path}"}
        
        matches = []
        
        # 编译正则
        try:
            regex = re.compile(pattern)
        except re.error as e:
            return {"error": f"无效的正则表达式: {str(e)}"}
        
        # 遍历文件
        for root, dirs, files in os.walk(expanded):
            # 跳过隐藏目录
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for file in files:
                # 跳过隐藏文件和二进制
                if file.startswith('.'):
                    continue
                
                # glob 过滤
                if glob and not file.endswith(glob.replace('*', '')):
                    continue
                
                file_path = os.path.join(root, file)
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                        for i, line in enumerate(f, 1):
                            if regex.search(line):
                                rel_path = os.path.relpath(file_path, expanded)
                                matches.append({
                                    "file": rel_path,
                                    "line": i,
                                    "content": line.rstrip()
                                })
                                
                                if len(matches) >= limit:
                                    return {
                                        "matches": matches,
                                        "count": len(matches),
                                        "truncated": True
                                    }
                except (UnicodeDecodeError, PermissionError):
                    continue
        
        return {
            "matches": matches,
            "count": len(matches),
            "truncated": False
        }
    
    except Exception as e:
        return {"error": f"搜索失败: {str(e)}"}


def list_directory(path: str = ".") -> Dict[str, Any]:
    """
    列出目录内容
    
    Args:
        path: 目录路径
    
    Returns:
        包含 files, directories 的字典
    """
    try:
        expanded = os.path.expanduser(path)
        
        if not os.path.exists(expanded):
            return {"error": f"路径不存在: {path}"}
        
        if not os.path.isdir(expanded):
            return {"error": f"不是目录: {path}"}
        
        files = []
        directories = []
        
        for item in os.listdir(expanded):
            item_path = os.path.join(expanded, item)
            if os.path.isdir(item_path):
                directories.append(item)
            else:
                files.append(item)
        
        return {
            "path": path,
            "files": sorted(files),
            "directories": sorted(directories)
        }
    
    except Exception as e:
        return {"error": f"列出目录失败: {str(e)}"}


# 文件工具 schemas
READ_FILE_SCHEMA = {
    "name": "read_file",
    "description": "读取文件内容，支持分页",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "offset": {"type": "integer", "description": "起始行号（1-indexed）", "default": 1},
            "limit": {"type": "integer", "description": "最大行数", "default": 500}
        },
        "required": ["path"]
    }
}

WRITE_FILE_SCHEMA = {
    "name": "write_file",
    "description": "写入文件内容（覆盖）",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "content": {"type": "string", "description": "文件内容"}
        },
        "required": ["path", "content"]
    }
}

PATCH_SCHEMA = {
    "name": "patch",
    "description": "查找并替换文件中的文本",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "old_string": {"type": "string", "description": "要替换的文本"},
            "new_string": {"type": "string", "description": "替换后的文本"}
        },
        "required": ["path", "old_string", "new_string"]
    }
}

SEARCH_SCHEMA = {
    "name": "search_files",
    "description": "搜索文件内容",
    "parameters": {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "正则表达式模式"},
            "path": {"type": "string", "description": "搜索路径", "default": "."},
            "glob": {"type": "string", "description": "文件过滤（如 *.py）"},
            "limit": {"type": "integer", "description": "最大结果数", "default": 50}
        },
        "required": ["pattern"]
    }
}

LIST_DIR_SCHEMA = {
    "name": "list_directory",
    "description": "列出目录内容",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "目录路径", "default": "."}
        }
    }
}


def handle_read_file(args: Dict[str, Any], **kwargs) -> str:
    path = args.get("path", "")
    offset = args.get("offset", 1)
    limit = args.get("limit", 500)
    
    result = read_file(path, offset, limit)
    
    if "error" in result:
        return tool_error(result["error"])
    
    return tool_result(result)


def handle_write_file(args: Dict[str, Any], **kwargs) -> str:
    path = args.get("path", "")
    content = args.get("content", "")
    
    result = write_file(path, content)
    
    if "error" in result:
        return tool_error(result["error"])
    
    return tool_result(result)


def handle_patch(args: Dict[str, Any], **kwargs) -> str:
    path = args.get("path", "")
    old_string = args.get("old_string", "")
    new_string = args.get("new_string", "")
    
    result = patch_file(path, old_string, new_string)
    
    if "error" in result:
        return tool_error(result["error"])
    
    return tool_result(result)


def handle_search_files(args: Dict[str, Any], **kwargs) -> str:
    pattern = args.get("pattern", "")
    path = args.get("path", ".")
    glob = args.get("glob")
    limit = args.get("limit", 50)
    
    result = search_files(pattern, path, glob, limit)
    
    if "error" in result:
        return tool_error(result["error"])
    
    return tool_result(result)


def handle_list_directory(args: Dict[str, Any], **kwargs) -> str:
    path = args.get("path", ".")
    
    result = list_directory(path)
    
    if "error" in result:
        return tool_error(result["error"])
    
    return tool_result(result)


# 注册工具
from .registry import registry

registry.register(
    name="read_file",
    toolset="core",
    schema=READ_FILE_SCHEMA,
    handler=handle_read_file,
    description="读取文件内容",
    emoji="📖"
)

registry.register(
    name="write_file",
    toolset="core",
    schema=WRITE_FILE_SCHEMA,
    handler=handle_write_file,
    description="写入文件内容",
    emoji="✍️"
)

registry.register(
    name="patch",
    toolset="core",
    schema=PATCH_SCHEMA,
    handler=handle_patch,
    description="查找并替换文件文本",
    emoji="🔧"
)

registry.register(
    name="search_files",
    toolset="core",
    schema=SEARCH_SCHEMA,
    handler=handle_search_files,
    description="搜索文件内容",
    emoji="🔎"
)

registry.register(
    name="list_directory",
    toolset="core",
    schema=LIST_DIR_SCHEMA,
    handler=handle_list_directory,
    description="列出目录内容",
    emoji="📁"
)
