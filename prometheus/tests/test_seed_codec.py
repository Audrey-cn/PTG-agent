#!/usr/bin/env python3
"""
🧪 种子编解码器 测试套件

运行: cd ~/.hermes/tools/prometheus && python -m pytest tests/test_seed_codec.py -v
"""

import os
import sys
import json
import tempfile
import hashlib
import pytest

PROMETHEUS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROMETHEUS_DIR not in sys.path:
    sys.path.insert(0, PROMETHEUS_DIR)

from codec.layer1 import (
    StringDictEncoder, encode_seed, decode_seed,
    compress_file, decompress_file, codec_info, is_compressed,
    MAGIC, VERSION, COMPACT_SUFFIX,
)
from prometheus import load_seed, inject_founder_chronicle, TEMPLATE_TTG


# ═══════════════════════════════════════════
#   Fixtures
# ═══════════════════════════════════════════

@pytest.fixture
def sample_seed():
    """示例种子数据"""
    import datetime
    now = datetime.datetime.now()
    checksum = hashlib.md5(b"test-seed").hexdigest()[:8].upper()
    content = TEMPLATE_TTG.format(
        name="test-seed", name_lower="test_seed", variant="TEST",
        checksum=checksum, timestamp=now.isoformat(),
        epoch=f"Y{now.year}-D{now.timetuple().tm_yday}",
    )
    content = inject_founder_chronicle(content, f"Y{now.year}-D{now.timetuple().tm_yday}")
    return {"raw": content, "data": _parse(content)}


def _parse(content):
    """简化的 YAML 解析"""
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
def tmp_seed_file(tmp_path, sample_seed):
    """创建临时 .ttg 文件"""
    path = str(tmp_path / "test_seed.ttg")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(sample_seed["raw"])
    return path


@pytest.fixture
def real_seed_path():
    """真实始祖种子路径"""
    path = os.path.expanduser("~/.hermes/skills/teach-to-grow/teach-to-grow-core.ttg")
    if os.path.exists(path):
        return path
    pytest.skip("始祖种子不存在")


# ═══════════════════════════════════════════
#   1. 字符串字典编码器测试
# ═══════════════════════════════════════════

class TestStringDictEncoder:
    """字符串去重编码器"""

    def test_short_string_passthrough(self):
        """短字符串(<=8字符)应直接返回"""
        enc = StringDictEncoder()
        assert enc.encode_string("hello") == "hello"
        assert enc.encode_string("G001") == "G001"

    def test_long_string_indexed(self):
        """长字符串(>8字符)应被索引替代"""
        enc = StringDictEncoder()
        result = enc.encode_string("this is a long string that should be indexed")
        assert result == "$0"

    def test_deduplication(self):
        """重复字符串应返回相同索引"""
        enc = StringDictEncoder()
        s = "this is a repeated long string for testing"
        r1 = enc.encode_string(s)
        r2 = enc.encode_string(s)
        assert r1 == r2
        assert len(enc.get_dict()) == 1

    def test_decode_value(self):
        """解码应还原原始字符串"""
        enc = StringDictEncoder()
        original = "this is a long string for decode testing"
        encoded = enc.encode_string(original)
        decoded = enc.decode_value(encoded)
        assert decoded == original

    def test_decode_passthrough(self):
        """非索引值应直接返回"""
        enc = StringDictEncoder()
        assert enc.decode_value("short") == "short"
        assert enc.decode_value(42) == 42
        assert enc.decode_value(None) is None

    def test_recursive_encode_decode(self):
        """递归编码+解码应保持数据完整"""
        enc = StringDictEncoder()
        data = {
            "name": "short",
            "desc": "this is a long description that should be compressed",
            "list": ["item1", "this is another long string for testing purposes"],
            "nested": {"key": "deep long value that needs compression for testing"},
        }

        encoded = enc.encode_recursive(data)
        dict_list = enc.get_dict()

        # 解码
        dec = StringDictEncoder()
        dec.set_dict(dict_list)
        decoded = dec.decode_recursive(encoded)

        assert decoded == data

    def test_empty_data(self):
        """空数据应正常处理"""
        enc = StringDictEncoder()
        assert enc.encode_recursive({}) == {}
        assert enc.encode_recursive([]) == []
        assert enc.encode_recursive("") == ""
        assert enc.encode_recursive(None) is None

    def test_non_string_values(self):
        """非字符串值应保持不变"""
        enc = StringDictEncoder()
        assert enc.encode_recursive(42) == 42
        assert enc.encode_recursive(3.14) == 3.14
        assert enc.encode_recursive(True) is True


# ═══════════════════════════════════════════
#   2. 编码/解码往返测试
# ═══════════════════════════════════════════

class TestEncodeDecodeRoundtrip:
    """编码→解码往返一致性"""

    def test_roundtrip_preserves_data(self, sample_seed):
        """编码后解码应保持数据完整"""
        data = sample_seed["data"]
        encoded = encode_seed(data)
        decoded = decode_seed(encoded)

        assert decoded is not None
        assert decoded.get("life_crest", {}).get("sacred_name") == data.get("life_crest", {}).get("sacred_name")
        assert decoded.get("life_crest", {}).get("life_id") == data.get("life_crest", {}).get("life_id")

    def test_roundtrip_preserves_founder_tags(self, sample_seed):
        """创始印记标签应保持完整"""
        data = sample_seed["data"]
        encoded = encode_seed(data)
        decoded = decode_seed(encoded)

        original_tags = data.get("life_crest", {}).get("founder_chronicle", {}).get("tags", [])
        decoded_tags = decoded.get("life_crest", {}).get("founder_chronicle", {}).get("tags", [])
        assert set(original_tags) == set(decoded_tags)

    def test_roundtrip_preserves_tag_lexicon(self, sample_seed):
        """标签词典应保持完整"""
        data = sample_seed["data"]
        encoded = encode_seed(data)
        decoded = decode_seed(encoded)

        original_lexicon = data.get("genealogy_codex", {}).get("tag_lexicon", {})
        decoded_lexicon = decoded.get("genealogy_codex", {}).get("tag_lexicon", {})
        assert set(original_lexicon.keys()) == set(decoded_lexicon.keys())

    def test_roundtrip_preserves_gene_loci(self, sample_seed):
        """基因位点应保持完整"""
        data = sample_seed["data"]
        encoded = encode_seed(data)
        decoded = decode_seed(encoded)

        # 基因可能在顶层或 skill_soul 下
        original_genes = data.get("dna_encoding", {}).get("gene_loci", [])
        if not original_genes:
            original_genes = data.get("skill_soul", {}).get("dna_encoding", {}).get("gene_loci", [])

        decoded_genes = decoded.get("dna_encoding", {}).get("gene_loci", [])
        if not decoded_genes:
            decoded_genes = decoded.get("skill_soul", {}).get("dna_encoding", {}).get("gene_loci", [])

        assert len(original_genes) == len(decoded_genes)


# ═══════════════════════════════════════════
#   3. 真实种子压缩测试
# ═══════════════════════════════════════════

class TestRealSeedCompression:
    """始祖种子压缩"""

    def test_compression_ratio(self, real_seed_path):
        """压缩比应 > 3:1"""
        data = load_seed(real_seed_path)
        original_size = os.path.getsize(real_seed_path)
        encoded = encode_seed(data, original_size=original_size)
        ratio = original_size / len(encoded)
        assert ratio >= 3.0, f"压缩比过低: {ratio}"

    def test_compressed_smaller(self, real_seed_path):
        """压缩后应更小"""
        data = load_seed(real_seed_path)
        original_size = os.path.getsize(real_seed_path)
        encoded = encode_seed(data, original_size=original_size)
        assert len(encoded) < original_size

    def test_decode_preserves_checksum(self, real_seed_path):
        """解码后 checksum 应匹配"""
        data = load_seed(real_seed_path)
        original_size = os.path.getsize(real_seed_path)
        encoded = encode_seed(data, original_size=original_size)
        decoded = decode_seed(encoded)

        # 比较关键字段
        assert decoded.get("life_crest", {}).get("life_id") == \
               data.get("life_crest", {}).get("life_id")
        assert decoded.get("life_crest", {}).get("sacred_name") == \
               data.get("life_crest", {}).get("sacred_name")


# ═══════════════════════════════════════════
#   4. 文件压缩/解压测试
# ═══════════════════════════════════════════

class TestFileCompression:
    """文件级压缩"""

    def test_compress_creates_file(self, tmp_seed_file, tmp_path):
        """压缩应创建 .compact 文件"""
        output = str(tmp_path / "test.compact")
        result = compress_file(tmp_seed_file, output)
        assert result["success"] is True
        assert os.path.exists(output)

    def test_compress_ratio_positive(self, tmp_seed_file, tmp_path):
        """压缩比应为正数"""
        output = str(tmp_path / "test.compact")
        result = compress_file(tmp_seed_file, output)
        assert result["ratio"] > 1.0

    def test_compress_nonexistent_fails(self):
        """压缩不存在的文件应失败"""
        result = compress_file("/nonexistent/file.ttg")
        assert result["success"] is False

    def test_is_compressed_detect(self, tmp_seed_file, tmp_path):
        """应正确检测压缩/非压缩文件"""
        assert is_compressed(tmp_seed_file) is False

        output = str(tmp_path / "test.compact")
        compress_file(tmp_seed_file, output)
        assert is_compressed(output) is True

    def test_codec_info(self, tmp_seed_file, tmp_path):
        """codec_info 应返回文件信息"""
        info = codec_info(tmp_seed_file)
        assert info["format"] == "plain_yaml"
        assert info["size"] > 0

        output = str(tmp_path / "test.compact")
        compress_file(tmp_seed_file, output)
        info = codec_info(output)
        assert info["format"] == "compressed"


# ═══════════════════════════════════════════
#   5. 错误处理测试
# ═══════════════════════════════════════════

class TestErrorHandling:
    """错误处理"""

    def test_decode_invalid_magic(self):
        """无效魔数应返回 None"""
        result = decode_seed(b"NOTTG" + b"\x00" * 20)
        assert result is None

    def test_decode_too_short(self):
        """过短数据应返回 None"""
        result = decode_seed(b"TTGC")
        assert result is None

    def test_decode_corrupted(self):
        """损坏数据应返回 None"""
        raw = MAGIC + bytes([VERSION]) + b"\x00\x00\x00\x10" + b"corrupted_json_data" + b"\x00\x00\x00\x00"
        result = decode_seed(raw)
        assert result is None

    def test_decode_wrong_checksum(self):
        """错误校验和应返回 None"""
        json_data = json.dumps({"v": 1, "dict": [], "data": {}}).encode()
        data_len = len(json_data).to_bytes(4, 'big')
        raw = MAGIC + bytes([VERSION]) + data_len + json_data + b"\xff\xff\xff\xff"
        result = decode_seed(raw)
        assert result is None

    def test_decode_empty_dict(self):
        """空字典应正常解码"""
        data = {"simple": "data"}
        encoded = encode_seed(data)
        decoded = decode_seed(encoded)
        assert decoded is not None


# ═══════════════════════════════════════════
#   6. 压缩格式结构测试
# ═══════════════════════════════════════════

class TestCompressionFormat:
    """压缩格式结构"""

    def test_magic_bytes(self):
        """魔数应为 TTGC"""
        assert MAGIC == b"TTGC"

    def test_version_byte(self):
        """版本号应为 1"""
        assert VERSION == 1

    def test_file_structure(self, sample_seed):
        """文件结构应正确"""
        encoded = encode_seed(sample_seed["data"])

        # 魔数
        assert encoded[:4] == MAGIC
        # 版本
        assert encoded[4] == VERSION
        # 数据长度
        data_len = int.from_bytes(encoded[5:9], 'big')
        # 校验和
        assert len(encoded) == 9 + data_len + 4

    def test_compact_suffix(self):
        """压缩后缀应为 .compact"""
        assert COMPACT_SUFFIX == ".compact"


# ═══════════════════════════════════════════
#   7. 压缩比统计测试
# ═══════════════════════════════════════════

class TestCompressionStats:
    """压缩统计"""

    def test_encode_returns_bytes(self, sample_seed):
        """编码应返回字节"""
        result = encode_seed(sample_seed["data"])
        assert isinstance(result, bytes)

    def test_meta_includes_sizes(self, sample_seed):
        """元数据应包含大小信息"""
        import json as _json
        encoded = encode_seed(sample_seed["data"], original_size=50000)
        # 解析 JSON 部分
        data_len = int.from_bytes(encoded[5:9], 'big')
        json_data = encoded[9:9 + data_len]
        compact = _json.loads(json_data)

        assert "meta" in compact
        assert compact["meta"]["original_size"] == 50000
        assert compact["meta"]["compressed_size"] > 0
        assert compact["meta"]["compression_ratio"] > 1.0

    def test_dict_populated(self, sample_seed):
        """字典应被填充"""
        import json as _json
        encoded = encode_seed(sample_seed["data"])
        data_len = int.from_bytes(encoded[5:9], 'big')
        json_data = encoded[9:9 + data_len]
        compact = _json.loads(json_data)

        assert "dict" in compact
        assert len(compact["dict"]) > 0  # 应该有一些被索引的字符串


# ═══════════════════════════════════════════
#   入口
# ═══════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
