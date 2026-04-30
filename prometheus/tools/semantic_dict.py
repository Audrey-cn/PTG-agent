#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║   📖 普罗米修斯 · 语义字典工具 · Semantic Dictionary Tool    ║
║                                                              ║
║   设计哲学：字典随种子走，不随 Prometheus 走。               ║
║   本工具从种子文件中提取内嵌的语义字典，                     ║
║   提供查询、编解码、搜索、导出等操作。                       ║
║                                                              ║
║   用法：                                                      ║
║     python semantic_dict.py <seed.ttg> lookup "用户偏好"      ║
║     python semantic_dict.py <seed.ttg> decode @S001 @S002    ║
║     python semantic_dict.py <seed.ttg> search "压缩"          ║
║     python semantic_dict.py <seed.ttg> list                   ║
║     python semantic_dict.py <seed.ttg> export                 ║
║     python semantic_dict.py <seed.ttg> info                   ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import re
import argparse

# 将父目录加入路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codec.layer2 import SemanticDictionary, get_seed_dict
from codec.layer1 import decode_seed


def _load_seed_file(seed_path: str) -> dict:
    """加载种子文件（Markdown .ttg 或 JSON），不依赖 prometheus.py
    
    支持格式：
    1. Markdown 种子（内嵌 YAML 代码块）—— 主流格式
    2. JSON 种子 —— 简单格式
    3. 二进制 TTG（L1 压缩）—— 备用格式
    """
    import gzip
    
    path = os.path.expanduser(seed_path)
    if not os.path.exists(path):
        raise FileNotFoundError(f"种子文件不存在: {path}")
    
    with open(path, "rb") as f:
        raw = f.read()
    
    # 尝试 L1 解码（二进制 TTG 格式）
    if raw[:4] == b"TTG\x01":
        seed_data = decode_seed(raw)
        if seed_data:
            return seed_data
    
    # 尝试读取为文本（Markdown 或 JSON）
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = None
    
    if text:
        # 尝试 JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # 解析 Markdown 种子（内嵌 YAML 代码块）
        seed_data = _parse_markdown_seed(text)
        if seed_data:
            return seed_data
    
    # 尝试 gzip 解压
    try:
        decompressed = gzip.decompress(raw)
        return json.loads(decompressed)
    except Exception:
        pass
    
    raise ValueError(f"无法解析种子文件: {path}")


def _parse_markdown_seed(text: str) -> dict:
    """解析 Markdown 格式的种子文件
    
    Markdown 种子结构：
    ```yaml
    life_crest:      → 生命元数据
    skill_soul:      → 技能灵魂（含 dna_encoding）
    genealogy_codex: → 族谱密码（含 tag_lexicon 语义字典）
    ```
    """
    try:
        import yaml
    except ImportError:
        return None
    
    # 提取所有 YAML 代码块
    blocks = re.findall(r'```yaml(.*?)```', text, re.DOTALL)
    if not blocks:
        return None
    
    # 解析并合并所有 YAML 块
    merged = {}
    for block in blocks:
        try:
            data = yaml.safe_load(block.strip())
            if data and isinstance(data, dict):
                merged.update(data)
        except yaml.YAMLError:
            continue
    
    if not merged:
        return None
    
    # 提取语义字典：genealogy_codex.tag_lexicon
    codex = merged.get("genealogy_codex", {})
    tag_lexicon = codex.get("tag_lexicon", {})
    
    # 将 tag_lexicon 转为 SemanticDictionary 可用格式
    entries = {}
    for tag, info in tag_lexicon.items():
        if isinstance(info, dict):
            entries[tag] = {
                "text": info.get("desc", tag),
                "type": "concept",
                "desc": info.get("desc", ""),
                "tag": tag,
            }
    
    # 提取基因信息
    soul = merged.get("skill_soul", {})
    dna = soul.get("dna_encoding", {})
    
    # 构造种子数据
    seed_data = {
        "name": merged.get("life_crest", {}).get("sacred_name", "unknown"),
        "life_crest": merged.get("life_crest", {}),
        "skill_soul": soul,
        "genealogy_codex": codex,
        "semantic_decoder": {
            "entries": entries,
            "version": 1,
            "count": len(entries),
        },
    }
    
    return seed_data


# ═══════════════════════════════════════════
#   核心工具类
# ═══════════════════════════════════════════

class SemanticDictTool:
    """语义字典工具——从种子中提取和使用语义字典。
    
    设计哲学：
      Prometheus 不存储字典，只提供读取算法。
      字典完全由种子携带，每代种子可以有自己的字典演化。
    """

    def __init__(self, seed_path: str = None, seed_data: dict = None):
        """
        Args:
            seed_path: 种子文件路径 (.ttg 或 .json)
            seed_data: 已加载的种子数据（优先于 seed_path）
        """
        if seed_data:
            self._seed_data = seed_data
        elif seed_path:
            self._seed_data = self._load_seed(seed_path)
        else:
            self._seed_data = None

        self._dict = None
        if self._seed_data:
            self._dict = get_seed_dict(self._seed_data)

    def _load_seed(self, seed_path: str) -> dict:
        """加载种子文件"""
        return _load_seed_file(seed_path)

    @property
    def dictionary(self) -> SemanticDictionary:
        """获取语义字典实例"""
        if self._dict is None:
            self._dict = SemanticDictionary.default()
        return self._dict

    @property
    def seed_name(self) -> str:
        """种子名称"""
        if self._seed_data:
            return self._seed_data.get("name", "unknown")
        return "default"

    # ── 查询操作 ──────────────────────────────

    def lookup(self, text: str) -> str:
        """文本 → 语义ID"""
        sem_id = self.dictionary.lookup(text)
        if sem_id:
            return f"@{sem_id}"
        return None

    def resolve(self, sem_id: str) -> dict:
        """语义ID → 完整条目"""
        if sem_id.startswith("@"):
            sem_id = sem_id[1:]
        return self.dictionary.get(sem_id)

    def search(self, query: str, entry_type: str = None) -> list:
        """搜索语义概念"""
        return self.dictionary.search(query, entry_type=entry_type)

    def list_all(self, entry_type: str = None) -> list:
        """列出所有概念"""
        return self.dictionary.list_all(entry_type=entry_type)

    # ── 编解码操作 ────────────────────────────

    def encode(self, texts: list) -> list:
        """文本列表 → 语义ID列表（压缩）"""
        result = []
        for text in texts:
            sem_id = self.dictionary.lookup(text)
            if sem_id:
                result.append(f"@{sem_id}")
            else:
                result.append(text)  # 未匹配，保留原文
        return result

    def decode(self, refs: list) -> list:
        """语义ID列表 → 文本列表（解压）"""
        result = []
        for ref in refs:
            if isinstance(ref, str) and ref.startswith("@"):
                sem_id = ref[1:]
                entry = self.dictionary.get(sem_id)
                if entry:
                    result.append(entry["text"])
                else:
                    result.append(ref)  # 无效引用，保留原样
            else:
                result.append(ref)
        return result

    # ── 导出操作 ──────────────────────────────

    def export_json(self) -> dict:
        """导出为 JSON 格式"""
        return {
            "seed_name": self.seed_name,
            "dictionary": self.dictionary.to_seed_data(),
        }

    def export_markdown(self) -> str:
        """导出为 Markdown 格式（人读层）"""
        entries = self.dictionary.list_all()
        
        lines = [
            f"# 语义字典 · {self.seed_name}",
            f"",
            f"_共 {len(entries)} 个概念_",
            f"",
        ]

        # 按 type 分组
        by_type = {}
        for e in entries:
            t = e.get("type", "unknown")
            by_type.setdefault(t, []).append(e)

        for type_name, items in sorted(by_type.items()):
            lines.append(f"## {type_name.title()} ({len(items)})")
            lines.append("")
            for item in items:
                sem_id = item.get("id", "?")
                text = item.get("text", "")
                desc = item.get("desc", "")
                lines.append(f"- **@{sem_id}**: {text}")
                if desc:
                    lines.append(f"  - {desc}")
            lines.append("")

        return "\n".join(lines)

    def info(self) -> dict:
        """获取字典概览信息"""
        entries = self.dictionary.list_all()
        by_type = {}
        for e in entries:
            t = e.get("type", "unknown")
            by_type.setdefault(t, 0)
            by_type[t] += 1

        return {
            "seed_name": self.seed_name,
            "total_entries": len(entries),
            "types": by_type,
            "has_semantic_decoder": bool(
                self._seed_data and self._seed_data.get("semantic_decoder")
            ) if self._seed_data else False,
        }


# ═══════════════════════════════════════════
#   CLI 入口
# ═══════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="种子语义字典工具 —— 从种子中提取和使用编解码字典"
    )
    parser.add_argument("seed", help="种子文件路径 (.ttg 或 .json)")
    parser.add_argument("command", 
                       choices=["lookup", "resolve", "search", "list", 
                                "encode", "decode", "export", "info"],
                       help="操作命令")
    parser.add_argument("args", nargs="*", help="命令参数")
    parser.add_argument("--type", help="按类型过滤")
    parser.add_argument("--format", choices=["json", "md"], default="json",
                       help="导出格式")

    args = parser.parse_args()

    try:
        tool = SemanticDictTool(seed_path=args.seed)
    except FileNotFoundError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ 加载种子失败: {e}", file=sys.stderr)
        sys.exit(1)

    if args.command == "info":
        info = tool.info()
        print(f"📖 {info['seed_name']}")
        print(f"   概念数: {info['total_entries']}")
        print(f"   类型分布: {info['types']}")
        print(f"   内嵌字典: {'是' if info['has_semantic_decoder'] else '否（使用默认字典）'}")

    elif args.command == "lookup":
        if not args.args:
            print("❌ 需要提供要查找的文本", file=sys.stderr)
            sys.exit(1)
        for text in args.args:
            result = tool.lookup(text)
            if result:
                print(f"  {text} → {result}")
            else:
                print(f"  {text} → (未找到)")

    elif args.command == "resolve":
        if not args.args:
            print("❌ 需要提供语义ID (如 @S001)", file=sys.stderr)
            sys.exit(1)
        for ref in args.args:
            entry = tool.resolve(ref)
            if entry:
                print(f"  {ref}:")
                print(f"    文本: {entry.get('text', '')}")
                print(f"    类型: {entry.get('type', '')}")
                if entry.get('desc'):
                    print(f"    描述: {entry['desc']}")
            else:
                print(f"  {ref}: (未找到)")

    elif args.command == "search":
        if not args.args:
            print("❌ 需要提供搜索关键词", file=sys.stderr)
            sys.exit(1)
        query = " ".join(args.args)
        results = tool.search(query, entry_type=args.type)
        if results:
            for r in results:
                print(f"  @{r.get('id', '?')}: {r.get('text', '')} [{r.get('type', '')}]")
        else:
            print("  (无匹配结果)")

    elif args.command == "list":
        entries = tool.list_all(entry_type=args.type)
        for e in entries:
            print(f"  @{e.get('id', '?')}: {e.get('text', '')} [{e.get('type', '')}]")
        print(f"\n  共 {len(entries)} 个概念")

    elif args.command == "encode":
        if not args.args:
            print("❌ 需要提供要编码的文本", file=sys.stderr)
            sys.exit(1)
        results = tool.encode(args.args)
        for text, ref in zip(args.args, results):
            print(f"  {text} → {ref}")

    elif args.command == "decode":
        if not args.args:
            print("❌ 需要提供要解码的语义ID", file=sys.stderr)
            sys.exit(1)
        results = tool.decode(args.args)
        for ref, text in zip(args.args, results):
            print(f"  {ref} → {text}")

    elif args.command == "export":
        if args.format == "md":
            print(tool.export_markdown())
        else:
            print(json.dumps(tool.export_json(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
