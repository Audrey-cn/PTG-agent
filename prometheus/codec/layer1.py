#!/usr/bin/env python3
"""╔══════════════════════════════════════════════════════════════╗."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

# ═══════════════════════════════════════════
#   常量
# ═══════════════════════════════════════════

MAGIC = b"TTGC"  # TTG Compressed
VERSION = 1

# 压缩格式文件后缀
COMPACT_SUFFIX = ".compact"


# ═══════════════════════════════════════════
#   字符串字典编码器
# ═══════════════════════════════════════════


class StringDictEncoder:
    """字符串去重编码器。

    将所有字符串值提取到共享字典中，用整数索引替代。
    类似 DNA 的碱基编码——有限的符号集编码无限的语义。
    """

    def __init__(self):
        self.string_to_id: dict[str, int] = {}
        self.id_to_string: dict[int, str] = {}
        self._next_id = 0

    def encode_string(self, s: str) -> Any:
        """编码一个字符串。短字符串直接返回，长字符串用索引替代。"""
        if not isinstance(s, str):
            return s

        # 短字符串（<=8字符）直接存储，不值得做索引
        if len(s) <= 8:
            return s

        if s not in self.string_to_id:
            self.string_to_id[s] = self._next_id
            self.id_to_string[self._next_id] = s
            self._next_id += 1

        return f"${self.string_to_id[s]}"

    def decode_value(self, v: Any) -> Any:
        """解码一个值。"""
        if isinstance(v, str) and v.startswith("$") and v[1:].isdigit():
            idx = int(v[1:])
            return self.id_to_string.get(idx, v)
        return v

    def decode_recursive(self, data: Any) -> Any:
        """递归解码整个数据结构。"""
        if isinstance(data, dict):
            return {k: self.decode_recursive(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.decode_recursive(item) for item in data]
        else:
            return self.decode_value(data)

    def encode_recursive(self, data: Any) -> Any:
        """递归编码整个数据结构。"""
        if isinstance(data, dict):
            return {k: self.encode_recursive(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.encode_recursive(item) for item in data]
        else:
            return self.encode_string(data)

    def get_dict(self) -> list[str]:
        """获取编码字典（按 ID 排序）。"""
        return [self.id_to_string.get(i, "") for i in range(self._next_id)]

    def set_dict(self, dict_list: list[str]):
        """设置解码字典。"""
        self.id_to_string = {i: s for i, s in enumerate(dict_list)}
        self.string_to_id = {s: i for i, s in enumerate(dict_list)}
        self._next_id = len(dict_list)

    def stats(self) -> dict:
        """编码统计。"""
        return {
            "unique_strings": len(self.string_to_id),
            "total_chars_saved": sum(len(s) - 8 for s in self.string_to_id if len(s) > 8),
        }


# ═══════════════════════════════════════════
#   压缩格式
# ═══════════════════════════════════════════
#
# 文件格式：
#   [4字节魔数: TTGC]
#   [1字节版本号]
#   [4字节数据长度 N]
#   [N字节 JSON 数据]
#   [4字节校验和（前 N 字节的 MD5）]
#
# JSON 数据结构：
# {
#   "v": 1,                    // 版本
#   "dict": ["str1", ...],     // 共享字符串字典
#   "data": { ... },           // 压缩后的种子数据
#   "meta": {                  // 原始信息
#     "original_size": 85000,
#     "compressed_size": 8500,
#     "compression_ratio": 10.0,
#     "checksum": "abc123"
#   }
# }


def _checksum(data: bytes) -> bytes:
    """计算校验和"""
    return hashlib.md5(data).digest()[:4]


# ═══════════════════════════════════════════
#   编码器
# ═══════════════════════════════════════════


def encode_seed(seed_data: dict, original_size: int = 0) -> bytes:
    """将种子数据编码为紧凑二进制格式。

    Args:
        seed_data: load_seed() 返回的 dict
        original_size: 原始文件大小（用于统计）

    Returns:
        编码后的字节流
    """
    encoder = StringDictEncoder()

    # 递归编码（字符串去重）
    encoded_data = encoder.encode_recursive(seed_data)

    # 构建压缩包
    dict_list = encoder.get_dict()
    compact = {
        "v": VERSION,
        "dict": dict_list,
        "data": encoded_data,
        "meta": {
            "original_size": original_size,
            "checksum": hashlib.md5(
                json.dumps(seed_data, ensure_ascii=False, sort_keys=True).encode()
            ).hexdigest()[:16],
        },
    }

    # 序列化为紧凑 JSON（无缩进）
    json_bytes = json.dumps(compact, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    # 计算压缩后大小
    compact["meta"]["compressed_size"] = len(json_bytes)
    compact["meta"]["compression_ratio"] = (
        round(original_size / len(json_bytes), 1) if original_size > 0 else 0
    )

    # 重新序列化（因为 meta 变了）
    json_bytes = json.dumps(compact, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    # 构建二进制文件
    data_len = len(json_bytes).to_bytes(4, "big")
    cs = _checksum(json_bytes)

    return MAGIC + bytes([VERSION]) + data_len + json_bytes + cs


def decode_seed(raw: bytes) -> dict | None:
    """从紧凑二进制格式解码种子数据。

    Args:
        raw: encode_seed() 输出的字节流

    Returns:
        解码后的种子 dict（等同于 load_seed() 返回值），失败返回 None
    """
    if len(raw) < 13:  # 最小长度：4魔数 + 1版本 + 4长度 + 4校验
        return None

    # 验证魔数
    if raw[:4] != MAGIC:
        return None

    # 读取版本
    version = raw[4]
    if version > VERSION:
        return None

    # 读取数据长度
    data_len = int.from_bytes(raw[5:9], "big")

    if 9 + data_len + 4 > len(raw):
        return None

    # 读取 JSON 数据
    json_bytes = raw[9 : 9 + data_len]

    # 验证校验和
    expected_cs = raw[9 + data_len : 9 + data_len + 4]
    actual_cs = _checksum(json_bytes)
    if expected_cs != actual_cs:
        return None

    # 解析 JSON
    try:
        compact = json.loads(json_bytes)
    except json.JSONDecodeError:
        return None

    # 构建解码器
    decoder = StringDictEncoder()
    decoder.set_dict(compact.get("dict", []))

    # 递归解码
    seed_data = decoder.decode_recursive(compact.get("data", {}))

    return seed_data


# ═══════════════════════════════════════════
#   便捷函数
# ═══════════════════════════════════════════


def compress_file(input_path: str, output_path: str = None) -> dict:
    """压缩 .ttg 文件。

    Args:
        input_path: 原始 .ttg 文件路径
        output_path: 输出路径（默认 .ttg.compact）

    Returns:
        {success, input_size, output_size, ratio}
    """
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from prometheus import load_seed

    if not os.path.exists(input_path):
        return {"success": False, "error": f"文件不存在: {input_path}"}

    original_size = os.path.getsize(input_path)

    # 加载原始种子
    seed_data = load_seed(input_path)
    if not seed_data:
        return {"success": False, "error": "无法解析种子"}

    # 编码
    encoded = encode_seed(seed_data, original_size=original_size)

    # 输出路径
    if not output_path:
        output_path = input_path + COMPACT_SUFFIX

    with open(output_path, "wb") as f:
        f.write(encoded)

    output_size = len(encoded)
    ratio = round(original_size / output_size, 1) if output_size > 0 else 0

    return {
        "success": True,
        "input_path": input_path,
        "output_path": output_path,
        "input_size": original_size,
        "output_size": output_size,
        "ratio": ratio,
        "saved_pct": round((1 - output_size / original_size) * 100, 1) if original_size > 0 else 0,
    }


def decompress_file(input_path: str, output_path: str = None) -> dict:
    """解压 .ttg.compact 文件。"""
    if not os.path.exists(input_path):
        return {"success": False, "error": f"文件不存在: {input_path}"}

    with open(input_path, "rb") as f:
        raw = f.read()

    seed_data = decode_seed(raw)
    if not seed_data:
        return {"success": False, "error": "解码失败"}

    # 输出路径
    if not output_path:
        output_path = input_path.replace(COMPACT_SUFFIX, "")

    # 重新生成 YAML 格式
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    # 先写一个临时文件让 save_seed 处理
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".ttg", delete=False, mode="w", encoding="utf-8") as f:
        # 写入最简结构让 save_seed 能处理
        import yaml

        yaml_content = yaml.dump(
            seed_data, default_flow_style=False, allow_unicode=True, sort_keys=False
        )
        f.write(yaml_content)
        tmp_path = f.name

    # 复制到目标
    import shutil

    shutil.copy2(tmp_path, output_path)
    os.unlink(tmp_path)

    return {
        "success": True,
        "input_path": input_path,
        "output_path": output_path,
        "input_size": os.path.getsize(input_path),
        "output_size": os.path.getsize(output_path),
    }


def codec_info(path: str) -> dict:
    """查看文件的压缩信息。"""
    if not os.path.exists(path):
        return {"error": f"文件不存在: {path}"}

    size = os.path.getsize(path)

    if path.endswith(COMPACT_SUFFIX):
        with open(path, "rb") as f:
            raw = f.read(13)

        if raw[:4] == MAGIC:
            data_len = int.from_bytes(raw[5:9], "big")
            return {
                "format": "compressed",
                "size": size,
                "version": raw[4],
                "data_length": data_len,
                "overhead": size - data_len - 13,
            }

    return {
        "format": "plain_yaml",
        "size": size,
    }


def is_compressed(path: str) -> bool:
    """判断文件是否为压缩格式。"""
    if not os.path.exists(path):
        return False
    try:
        with open(path, "rb") as f:
            header = f.read(4)
        return header == MAGIC
    except:
        return False


# ═══════════════════════════════════════════
#   CLI 入口
# ═══════════════════════════════════════════


def main():
    import sys

    if len(sys.argv) < 2:
        print("""
🧬 普罗米修斯 · 种子编解码器

用法:
  seed_codec.py compress <种子.ttg> [输出路径]     压缩种子
  seed_codec.py decompress <种子.ttg.compact> [输出路径]  解压种子
  seed_codec.py info <文件路径>                     查看压缩信息
  seed_codec.py benchmark <种子.ttg>               压缩比测试
""")
        return

    action = sys.argv[1]

    if action == "compress" and len(sys.argv) > 2:
        input_path = sys.argv[2]
        output_path = sys.argv[3] if len(sys.argv) > 3 else None
        result = compress_file(input_path, output_path)
        if result["success"]:
            print("✅ 压缩完成")
            print(f"   原始: {result['input_size']:,} bytes")
            print(f"   压缩: {result['output_size']:,} bytes")
            print(f"   比率: {result['ratio']}:1 (节省 {result['saved_pct']}%)")
            print(f"   输出: {result['output_path']}")
        else:
            print(f"❌ {result.get('error', '未知错误')}")

    elif action == "decompress" and len(sys.argv) > 2:
        input_path = sys.argv[2]
        output_path = sys.argv[3] if len(sys.argv) > 3 else None
        result = decompress_file(input_path, output_path)
        if result["success"]:
            print(f"✅ 解压完成 → {result['output_path']}")
        else:
            print(f"❌ {result.get('error', '未知错误')}")

    elif action == "info" and len(sys.argv) > 2:
        info = codec_info(sys.argv[2])
        print("\n📋 文件信息:")
        for k, v in info.items():
            print(f"  {k}: {v}")

    elif action == "benchmark" and len(sys.argv) > 2:
        path = sys.argv[2]
        original_size = os.path.getsize(path)

        import sys as _sys

        _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from prometheus import load_seed

        seed_data = load_seed(path)
        if not seed_data:
            print("❌ 无法加载种子")
            return

        encoded = encode_seed(seed_data, original_size=original_size)
        ratio = round(original_size / len(encoded), 1)

        # 计算理论极限（只看字符串字典的节省）
        encoder = StringDictEncoder()
        encoder.encode_recursive(seed_data)
        dict_stats = encoder.stats()

        print(f"\n🧬 压缩基准测试: {os.path.basename(path)}")
        print(f"   原始大小: {original_size:,} bytes")
        print(f"   压缩大小: {len(encoded):,} bytes")
        print(f"   压缩比:   {ratio}:1")
        print(f"   节省:     {round((1 - len(encoded) / original_size) * 100, 1)}%")
        print(f"   唯一字符串: {dict_stats['unique_strings']}")
        print(f"   字典节省:   {dict_stats['total_chars_saved']:,} chars")

    else:
        print(f"未知命令: {action}")


if __name__ == "__main__":
    main()
