#!/usr/bin/env python3
"""
TTG种子格式引擎 · 编码圣典物理层

不解读叙事。只负责物理文件的创建、解析、验证。
叙事解码由 genome_decoder 完成。
"""

from __future__ import annotations

import hashlib
import json
import logging
import struct
import zlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MAGIC = b"SEED"

PREFIX_TEMPLATES = {
    "壹": "龢 · 種\n壹 · 火\n",
    "貳": "龢 · 種\n貳 · 土\n",
    "參": "龢 · 種\n參 · 風\n",
    "肆": "龢 · 種\n肆 · 水\n",
    "伍": "龢 · 種\n伍 · 金\n",
}

# JSON 头字段代码表（压缩键 → 全称）
HEADER_KEY_MAP = {
    "m": "magic",
    "v": "version",
    "f": "format",
    "lid": "life_id",
    "era": "era",
    "cp": "compression",
    "cs": "checksum",
    "so": "size_original",
    "sz": "size_compressed",
    "cr": "compression_ratio",
    "ps": "protocol_stack",
    "dh": "decoder_hint",
    "sm": "section_map",
    "gt": "gene_tally",
    "ft": "founder_tags",
}

# 区块代码 → 全称
SECTION_CODES = {
    "LC": "life_crest",
    "GX": "genealogy_codex",
    "SL": "skill_soul",
    "DN": "dna_encoding",
    "TX": "transmission_chronicle",
    "EV": "evolution_chronicle",
}


@dataclass
class SeedHeader:
    """种子文件标准头"""
    magic: str = "SEED"
    version: int = 2
    format: str = "gm"
    life_id: str = ""
    era: str = "壹"
    compression: str = "df"
    checksum: str = ""
    size_original: int = 0
    size_compressed: int = 0
    compression_ratio: float = 1.0
    protocol_stack: List[str] = field(default_factory=lambda: ["st", "sm", "sg", "se"])
    decoder_hint: str = "std_v2"
    section_map: Dict[str, List[int]] = field(default_factory=dict)
    gene_tally: int = 0
    founder_tags: List[str] = field(default_factory=list)

    def to_compact_json(self) -> dict:
        """导出为压缩键 JSON 字典"""
        return {
            "m": self.magic,
            "v": self.version,
            "f": self.format,
            "lid": self.life_id,
            "era": self.era,
            "cp": self.compression,
            "cs": self.checksum,
            "so": self.size_original,
            "sz": self.size_compressed,
            "cr": self.compression_ratio,
            "ps": self.protocol_stack,
            "dh": self.decoder_hint,
            "sm": self.section_map,
            "gt": self.gene_tally,
            "ft": self.founder_tags,
        }

    @classmethod
    def from_compact_json(cls, d: dict) -> SeedHeader:
        """从压缩键 JSON 字典还原"""
        return cls(
            magic=d.get("m", "SEED"),
            version=d.get("v", 2),
            format=d.get("f", "gm"),
            life_id=d.get("lid", ""),
            era=d.get("era", "壹"),
            compression=d.get("cp", "df"),
            checksum=d.get("cs", ""),
            size_original=d.get("so", 0),
            size_compressed=d.get("sz", 0),
            compression_ratio=d.get("cr", 1.0),
            protocol_stack=d.get("ps", ["st", "sm", "sg", "se"]),
            decoder_hint=d.get("dh", "std_v2"),
            section_map=d.get("sm", {}),
            gene_tally=d.get("gt", 0),
            founder_tags=d.get("ft", []),
        )

    def expand_section_code(self, code: str) -> str:
        """将区块代码展开为全称"""
        return SECTION_CODES.get(code, code)


class TTGFileStructure:
    """TTG种子格式引擎 · 物理层"""

    @staticmethod
    def create(header: SeedHeader, encoded_body: bytes) -> bytes:
        """
        创建完整的种子文件

        Args:
            header: 种子文件头
            encoded_body: 压缩后的基因组字节

        Returns:
            完整的种子文件字节
        """
        logger.info("开始组装种子文件")

        era_key = header.era if header.era in PREFIX_TEMPLATES else "壹"
        prefix_bytes = PREFIX_TEMPLATES[era_key].encode("utf-8")

        compact = header.to_compact_json()

        compact["cs"] = hashlib.sha256(encoded_body).hexdigest()[:16]
        compact["sz"] = len(encoded_body)
        if compact["so"] > 0 and compact["sz"] > 0:
            compact["cr"] = round(compact["so"] / compact["sz"], 2)

        header_json = json.dumps(compact, ensure_ascii=False)
        header_bytes = header_json.encode("utf-8")
        header_len = struct.pack(">I", len(header_bytes))

        seed_data = prefix_bytes + MAGIC + header_len + header_bytes + encoded_body

        logger.info(f"种子文件组装完成，总大小: {len(seed_data)} 字节")
        return seed_data

    @staticmethod
    def parse(seed_data: bytes) -> Tuple[SeedHeader, bytes]:
        """
        解析种子文件

        Args:
            seed_data: 种子文件字节

        Returns:
            (SeedHeader, 压缩基因组字节)

        Raises:
            ValueError: 格式无效
        """
        logger.info("开始解析种子文件")

        if len(seed_data) < 16:
            raise ValueError("种子文件过小，格式无效")

        pos = 0

        prefix_end = seed_data.find(MAGIC)
        if prefix_end == -1:
            prefix_end = seed_data.find(b"\n\n")
            if prefix_end == -1:
                raise ValueError("找不到加密前缀结束标记或魔数")
            pos = prefix_end + 2
        else:
            pos = prefix_end + len(MAGIC)

        if pos + 4 > len(seed_data):
            raise ValueError("文件头长度信息不完整")
        header_len = struct.unpack(">I", seed_data[pos:pos + 4])[0]
        pos += 4

        if pos + header_len > len(seed_data):
            raise ValueError("文件头数据不完整")
        header_json = seed_data[pos:pos + header_len].decode("utf-8")
        compact = json.loads(header_json)
        header = SeedHeader.from_compact_json(compact)
        pos += header_len

        body = seed_data[pos:]

        expected_cs = hashlib.sha256(body).hexdigest()[:16]
        stored_cs = compact.get("cs", "")
        if stored_cs and expected_cs != stored_cs:
            raise ValueError(
                f"校验和不匹配 (期望: {expected_cs}, 存储: {stored_cs})"
            )

        header.checksum = expected_cs
        header.size_compressed = len(body)
        header.section_map = compact.get("sm", {})

        logger.info(
            f"种子文件解析完成，头: {header_len}B, 体: {len(body)}B, "
            f"life_id: {header.life_id[:24]}..."
        )
        return header, body

    @staticmethod
    def get_header_only(seed_data: bytes) -> SeedHeader:
        """仅解析文件头，不解压解码基因组"""
        header, _ = TTGFileStructure.parse(seed_data)
        return header

    @staticmethod
    def decompress_body(body: bytes) -> bytes:
        """解压基因组体"""
        try:
            return zlib.decompress(body)
        except zlib.error:
            return body

    @staticmethod
    def compress_body(text: bytes) -> bytes:
        """压缩基因组体"""
        return zlib.compress(text)

    @staticmethod
    def validate(seed_data: bytes) -> Tuple[bool, Optional[str]]:
        """三步验证：魔数 → 结构 → 校验和"""
        try:
            if MAGIC not in seed_data:
                prefix_end = seed_data.find(b"\n\n")
                if prefix_end == -1:
                    return False, "魔数未找到"

            header, body = TTGFileStructure.parse(seed_data)

            if header.magic != "SEED":
                return False, "魔数不匹配"
            if header.version < 1 or header.version > 99:
                return False, f"版本号异常: {header.version}"
            if header.life_id and not header.life_id.startswith("TTG@"):
                return False, f"life_id 格式异常: {header.life_id[:20]}"

            return True, None

        except Exception as e:
            return False, f"验证异常: {e}"

    @staticmethod
    def extract_prefix(seed_data: bytes) -> str:
        """提取加密前缀"""
        magic_pos = seed_data.find(MAGIC)
        if magic_pos == -1:
            end = seed_data.find(b"\n\n")
            if end == -1:
                end = min(200, len(seed_data))
        else:
            end = magic_pos
        return seed_data[:end].decode("utf-8", errors="ignore").strip()


def create_seed_file(header: SeedHeader, genome_text: str) -> bytes:
    """便捷函数：从基因组文本创建种子文件"""
    body = TTGFileStructure.compress_body(genome_text.encode("utf-8"))
    header.size_original = len(genome_text.encode("utf-8"))
    return TTGFileStructure.create(header, body)


def read_seed_file(seed_data: bytes) -> Tuple[SeedHeader, str]:
    """便捷函数：读取种子文件，返回(头, 解压后的基因组文本)"""
    header, body = TTGFileStructure.parse(seed_data)
    genome_text = TTGFileStructure.decompress_body(body).decode("utf-8")
    return header, genome_text


if __name__ == "__main__":
    header = SeedHeader(
        life_id="TTG@L1-G1-ORIGIN-FB1F3A11",
        era="壹",
        gene_tally=8,
        founder_tags=["a001x", "emk"],
    )

    test_genome = "§LC\n  ID:TTG@L1-G1-TEST-ABCD1234\n  SNAME:測試之種␟\n␟\n"

    seed_data = create_seed_file(header, test_genome)
    print(f"创建种子: {len(seed_data)} 字节")

    prefix = TTGFileStructure.extract_prefix(seed_data)
    print(f"前缀:\n{prefix}")

    valid, err = TTGFileStructure.validate(seed_data)
    print(f"验证: {'通过' if valid else f'失败 - {err}'}")

    h, genome = read_seed_file(seed_data)
    print(f"解析: life_id={h.life_id}, era={h.era}, genome_len={len(genome)}")
    print("测试通过")
