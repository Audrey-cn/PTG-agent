"""
[Shared Module] 语义罗盘工具 - 统一的罗盘解析逻辑

此模块提供语义标签到 CID 的解析功能，消除 protocol 和 akashic 之间的代码重复。
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict


def load_index(index_path: str) -> Dict:
    """
    加载阿卡夏索引文件。
    
    Args:
        index_path: 索引文件路径
    
    Returns:
        索引数据字典
    """
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        return {}


def resolve_cid_by_name(name: str, index_data: Dict) -> Optional[str]:
    """
    通过语义标签解析对应的 CID。
    
    Args:
        name: 语义标签名称
        index_data: 索引数据
    
    Returns:
        CID 字符串，未找到返回 None
    """
    entries = index_data.get("entries", {})
    
    # 精确匹配
    if name in entries:
        return entries[name].get("cid")
    
    # 模糊匹配
    for key, value in entries.items():
        if name.lower() in key.lower() or key.lower() in name.lower():
            return value.get("cid")
    
    return None


def update_index(index_path: str, updates: Dict):
    """
    更新索引文件。
    
    Args:
        index_path: 索引文件路径
        updates: 更新的数据
    """
    existing = load_index(index_path)
    existing.update(updates)
    
    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)


def sync_index(local_path: str, remote_url: str) -> bool:
    """
    从远程同步索引文件。
    
    Args:
        local_path: 本地索引路径
        remote_url: 远程索引URL
    
    Returns:
        是否同步成功
    """
    try:
        from urllib import request
        with request.urlopen(remote_url, timeout=15) as response:
            content = response.read().decode('utf-8')
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except (IOError, OSError) as e:
        return False