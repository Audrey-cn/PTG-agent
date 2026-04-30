"""
Prometheus codec 包

提供种子数据的编码、压缩和解码功能：
- Layer1: 基础编码层
- Layer2: 语义压缩层
"""

from .layer1 import (
    StringDictEncoder,
    encode_seed,
    decode_seed,
    compress_file,
    decompress_file,
    codec_info,
    is_compressed,
)

from .layer2 import (
    SemanticDictionary,
    genesis_hash,
    has_genesis_block,
    extract_genesis,
    restore_genesis,
    compress_genes,
    decompress_genes,
    semantic_hash,
    get_seed_dict,
    get_semantic_dict,
    compress_semantic,
    decompress_semantic,
    encode_seed_l2,
    decode_seed_l2,
    is_layer2,
    benchmark_layers,
)

__all__ = [
    "StringDictEncoder",
    "encode_seed",
    "decode_seed",
    "compress_file",
    "decompress_file",
    "codec_info",
    "is_compressed",
    "SemanticDictionary",
    "genesis_hash",
    "has_genesis_block",
    "extract_genesis",
    "restore_genesis",
    "compress_genes",
    "decompress_genes",
    "semantic_hash",
    "get_seed_dict",
    "get_semantic_dict",
    "compress_semantic",
    "decompress_semantic",
    "encode_seed_l2",
    "decode_seed_l2",
    "is_layer2",
    "benchmark_layers",
]
