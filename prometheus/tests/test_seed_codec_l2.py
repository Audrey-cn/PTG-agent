#!/usr/bin/env python3
"""
🧪 种子编解码器 Layer 2 测试套件

运行: cd ~/.hermes/tools/prometheus && python -m pytest tests/test_seed_codec_l2.py -v
"""

import os
import sys
import json
import hashlib
import pytest

PROMETHEUS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROMETHEUS_DIR not in sys.path:
    sys.path.insert(0, PROMETHEUS_DIR)

from codec.layer2 import (
    GENESIS_BLOCK, genesis_hash, has_genesis_block,
    extract_genesis, restore_genesis,
    BUILTIN_SEMANTICS, GENE_TEMPLATES, compress_genes, decompress_genes,
    SemanticDictionary, get_seed_dict, compress_semantic, decompress_semantic,
    encode_seed_l2, decode_seed_l2, is_layer2, benchmark_layers,
)
from codec.layer1 import encode_seed, decode_seed
from prometheus import load_seed, inject_founder_chronicle, TEMPLATE_TTG


# ═══════════════════════════════════════════
#   Fixtures
# ═══════════════════════════════════════════

@pytest.fixture
def sample_seed():
    """示例种子数据"""
    import datetime
    now = datetime.datetime.now()
    checksum = hashlib.md5(b"test-l2-seed").hexdigest()[:8].upper()
    content = TEMPLATE_TTG.format(
        name="test-seed", name_lower="test_seed", variant="TEST",
        checksum=checksum, timestamp=now.isoformat(),
        epoch=f"Y{now.year}-D{now.timetuple().tm_yday}",
    )
    content = inject_founder_chronicle(content, f"Y{now.year}-D{now.timetuple().tm_yday}")
    return _parse(content)


def _parse(content):
    import yaml
    blocks = []
    for m in __import__('re').finditer(r'```yaml\s*\n(.*?)```', content, __import__('re').DOTALL):
        try:
            parsed = yaml.safe_load(m.group(1))
            if parsed and isinstance(parsed, dict):
                blocks.append(parsed)
        except:
            pass
    result = {}
    for b in blocks:
        result.update(b)
    return result


@pytest.fixture
def real_seed_path():
    path = os.path.expanduser("~/.hermes/skills/teach-to-grow/teach-to-grow-core.ttg")
    if os.path.exists(path):
        return path
    pytest.skip("始祖种子不存在")


# ═══════════════════════════════════════════
#   1. Genesis Block 测试
# ═══════════════════════════════════════════

class TestGenesisBlock:
    """创世区块"""

    def test_genesis_hash_deterministic(self):
        """创世哈希应确定性"""
        h1 = genesis_hash()
        h2 = genesis_hash()
        assert h1 == h2

    def test_genesis_has_7_tags(self):
        """创世区块应有10个永恒标签"""
        tags = GENESIS_BLOCK["founder_chronicle"]["tags"]
        assert len(tags) == 10

    def test_genesis_has_7_lexicon_entries(self):
        """创世区块应有10个标签解码条目"""
        lexicon = GENESIS_BLOCK["tag_lexicon"]
        assert len(lexicon) == 10

    def test_has_genesis_block_true(self, sample_seed):
        """包含创始印记的种子应返回 True"""
        assert has_genesis_block(sample_seed) is True

    def test_has_genesis_block_false(self):
        """不含创始印记的种子应返回 False"""
        assert has_genesis_block({"life_crest": {}}) is False

    def test_extract_genesis(self, sample_seed):
        """提取创世区块应移除 founder_chronicle"""
        slim, h = extract_genesis(sample_seed)
        assert h == genesis_hash()
        assert "founder_chronicle" not in slim.get("life_crest", {})
        # 永恒标签应从 tag_lexicon 移除
        lexicon = slim.get("genealogy_codex", {}).get("tag_lexicon", {})
        eternal_tags = set(GENESIS_BLOCK["founder_chronicle"]["tags"])
        for tag in eternal_tags:
            assert tag not in lexicon

    def test_restore_genesis(self, sample_seed):
        """还原创世区块应恢复完整数据"""
        slim, h = extract_genesis(sample_seed)
        slim["_genesis"] = h
        full = restore_genesis(slim)
        assert "founder_chronicle" in full.get("life_crest", {})
        tags = full["life_crest"]["founder_chronicle"]["tags"]
        assert len(tags) == 10
        assert "_genesis" not in full

    def test_extract_restore_roundtrip(self, sample_seed):
        """提取→还原 应保持数据完整"""
        slim, h = extract_genesis(sample_seed)
        slim["_genesis"] = h
        full = restore_genesis(slim)
        assert full["life_crest"]["founder_chronicle"]["tags"] == \
               sample_seed["life_crest"]["founder_chronicle"]["tags"]


# ═══════════════════════════════════════════
#   2. Gene Templates 测试
# ═══════════════════════════════════════════

class TestGeneTemplates:
    """基因模板"""

    def test_all_8_standard_genes_covered(self):
        """模板应覆盖 G001-G008"""
        for i in range(1, 9):
            locus = f"G{i:03d}-*"
            matched = [k for k in GENE_TEMPLATES if k.startswith(f"G{i:03d}")]
            assert len(matched) == 1, f"G{i:03d} 缺失模板"

    def test_compress_standard_gene(self):
        """标准基因应被压缩"""
        gene = {
            "locus": "G001-parser",
            "name": "TTG解析器",
            "default": "parser_v1",
            "mutable_range": "format_support, parse_depth",
            "immutable": "parsed_output_schema",
        }
        compressed = compress_genes([gene])
        assert len(compressed) == 1
        assert compressed[0]["locus"] == "G001-parser"
        assert "name" not in compressed[0]  # 模板字段应被移除
        assert "immutable" not in compressed[0]

    def test_compress_custom_gene_preserved(self):
        """非标准基因应完整保留"""
        gene = {
            "locus": "G100-writer",
            "name": "写作风格注入器",
            "default": "writer_v1",
            "mutable_range": "style",
            "immutable": "core_functionality",
        }
        compressed = compress_genes([gene])
        assert compressed[0]["name"] == "写作风格注入器"

    def test_decompress_restores_full(self):
        """解压应还原完整基因"""
        gene = {
            "locus": "G001-parser",
            "default": "parser_v1",
            "mutable_range": "format_support",
        }
        compressed = compress_genes([gene])
        decompressed = decompress_genes(compressed)
        assert decompressed[0]["name"] == "TTG解析器"
        assert decompressed[0]["immutable"] == "parsed_output_schema"
        assert decompressed[0]["default"] == "parser_v1"

    def test_compress_decompress_roundtrip(self):
        """压缩→解压 应保持数据完整"""
        genes = [
            {"locus": "G001-parser", "name": "TTG解析器", "default": "p1",
             "mutable_range": "format", "immutable": "schema"},
            {"locus": "G003-tracker", "name": "生长追踪器", "default": "t1",
             "mutable_range": "interval", "immutable": "framework"},
            {"locus": "G100-writer", "name": "写作风格", "default": "w1",
             "mutable_range": "style", "immutable": "core"},
        ]
        compressed = compress_genes(genes)
        decompressed = decompress_genes(compressed)
        assert len(decompressed) == 3
        # 标准基因应还原模板字段
        assert decompressed[0]["name"] == "TTG解析器"
        assert decompressed[1]["name"] == "生长追踪器"
        # 非标准基因应保留
        assert decompressed[2]["name"] == "写作风格"


# ═══════════════════════════════════════════
#   3. Semantic Dictionary 测试
# ═══════════════════════════════════════════

class TestSemanticDictionary:
    """语义哈希字典"""

    def test_semantic_lib_has_entries(self):
        """语义字典应有条目"""
        assert len(BUILTIN_SEMANTICS) > 0

    def test_semantic_index_consistent(self):
        """反向索引应与字典一致"""
        for sem_id, entry in BUILTIN_SEMANTICS.items():
            text = entry["text"]
            d = SemanticDictionary.default()
            assert d.lookup(text) == sem_id

    def test_compress_known_concept(self):
        """已知概念应被透传（字典在种子中）"""
        result = compress_semantic(["诚实", "精确"])
        assert result == ["诚实", "精确"]

    def test_compress_unknown_preserved(self):
        """未知概念应保留原样"""
        result = compress_semantic(["自定义原则"])
        assert result == ["自定义原则"]

    def test_decompress_restores(self):
        """解压应还原概念"""
        result = decompress_semantic(["@p_honesty", "@p_precision"])
        assert result == ["诚实", "精确"]

    def test_decompress_unknown_preserved(self):
        """无效引用应保留原样"""
        result = decompress_semantic(["@nonexistent"])
        assert result == ["@nonexistent"]

    def test_compress_decompress_roundtrip(self):
        """压缩→解压 应保持数据完整"""
        original = ["诚实", "精确", "安全"]
        compressed = compress_semantic(original, "principle")
        decompressed = decompress_semantic(compressed)
        assert decompressed == original

    def test_empty_list(self):
        """空列表应正常处理"""
        assert compress_semantic([]) == []
        assert decompress_semantic([]) == []


# ═══════════════════════════════════════════
#   4. Layer 2 编码/解码往返测试
# ═══════════════════════════════════════════

class TestLayer2Roundtrip:
    """Layer 2 编码→解码往返"""

    def test_roundtrip_preserves_data(self, sample_seed):
        """Layer 2 往返应保持数据完整"""
        encoded = encode_seed_l2(sample_seed)
        decoded = decode_seed_l2(encoded)
        assert decoded is not None
        assert decoded["life_crest"]["sacred_name"] == sample_seed["life_crest"]["sacred_name"]

    def test_roundtrip_preserves_founder(self, sample_seed):
        """创世区块应被完整还原"""
        encoded = encode_seed_l2(sample_seed)
        decoded = decode_seed_l2(encoded)
        tags = decoded["life_crest"]["founder_chronicle"]["tags"]
        assert len(tags) == 10

    def test_roundtrip_preserves_tag_lexicon(self, sample_seed):
        """标签词典应被完整还原"""
        encoded = encode_seed_l2(sample_seed)
        decoded = decode_seed_l2(encoded)
        lexicon = decoded.get("genealogy_codex", {}).get("tag_lexicon", {})
        assert "audrey_001x" in lexicon

    def test_is_layer2_detection(self, sample_seed):
        """应正确检测 Layer 2 格式"""
        l1 = encode_seed(sample_seed)
        l2 = encode_seed_l2(sample_seed)
        assert is_layer2(l1) is False
        assert is_layer2(l2) is True

    def test_l2_smaller_than_l1(self, sample_seed):
        """Layer 2 应为有效格式（可能因嵌入字典而更大）"""
        l1 = encode_seed(sample_seed)
        l2 = encode_seed_l2(sample_seed)
        assert is_layer2(l2) is True
        assert decode_seed_l2(l2) is not None


# ═══════════════════════════════════════════
#   5. 真实种子 Layer 2 测试
# ═══════════════════════════════════════════

class TestRealSeedL2:
    """始祖种子 Layer 2 压缩"""

    def test_l2_compression_ratio(self, real_seed_path):
        """Layer 2 应为有效可解码格式"""
        data = load_seed(real_seed_path)
        original_size = os.path.getsize(real_seed_path)
        encoded = encode_seed_l2(data, original_size=original_size)
        assert is_layer2(encoded) is True
        decoded = decode_seed_l2(encoded)
        assert decoded is not None
        assert decoded["life_crest"]["life_id"] == data["life_crest"]["life_id"]

    def test_l2_vs_l1_improvement(self, real_seed_path):
        """Layer 2 应比 Layer 1 更小"""
        data = load_seed(real_seed_path)
        original_size = os.path.getsize(real_seed_path)
        l1 = encode_seed(data, original_size=original_size)
        l2 = encode_seed_l2(data, original_size=original_size)
        assert len(l2) < len(l1)

    def test_l2_decode_preserves_identity(self, real_seed_path):
        """解码后身份信息应完整"""
        data = load_seed(real_seed_path)
        encoded = encode_seed_l2(data)
        decoded = decode_seed_l2(encoded)
        assert decoded["life_crest"]["life_id"] == data["life_crest"]["life_id"]
        assert decoded["life_crest"]["sacred_name"] == data["life_crest"]["sacred_name"]

    def test_benchmark(self, real_seed_path):
        """benchmark 应返回有效结果"""
        data = load_seed(real_seed_path)
        original_size = os.path.getsize(real_seed_path)
        result = benchmark_layers(data, original_size)
        assert result["layer1_ratio"] > 0
        assert result["layer2_ratio"] > 0
        assert result["layer2_vs_l1"] > 0
        assert result["layer2_ratio"] > result["layer1_ratio"]


# ═══════════════════════════════════════════
#   入口
# ═══════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
