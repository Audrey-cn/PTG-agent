#!/usr/bin/env python3
"""
始祖种子迁移工具

读取始祖纯文本格式的 .ttg 种子，转换为新的编码格式。
保留始祖文件不动，输出新的 .seed 文件。
"""

from __future__ import annotations

import datetime
import hashlib
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

sys.path.insert(0, str(Path(__file__).parent))

from genome_encoder import encode_genome
from ttg_file_structure import SeedHeader, create_seed_file


def parse_ancestral_ttg(file_path: str) -> dict:
    """解析始祖纯文本格式，提取结构化数据"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    yaml_blocks = re.findall(r'```yaml\s*\n(.*?)```', content, re.DOTALL)

    data: Dict[str, Any] = {}

    for block in yaml_blocks:
        try:
            parsed = yaml.safe_load(block)
            if not parsed or not isinstance(parsed, dict):
                continue

            if 'life_crest' in parsed:
                data['life_crest'] = parsed['life_crest']
            if 'genealogy_codex' in parsed:
                data['genealogy_codex'] = parsed['genealogy_codex']
            if 'skill_soul' in parsed:
                data['skill_soul'] = parsed['skill_soul']
            if 'dna_encoding' in parsed:
                data['dna_encoding'] = parsed['dna_encoding']
            if 'transmission_chronicle' in parsed:
                data['transmission_chronicle'] = parsed['transmission_chronicle']

        except yaml.YAMLError:
            continue

    lc = data.get('life_crest', {})

    if 'genealogy_codex' not in data:
        data['genealogy_codex'] = {}

    gx = data['genealogy_codex']

    if 'current_genealogy' not in gx:
        gx['current_genealogy'] = {
            'lineage': 'L1', 'bloodline': '太初之脈',
            'generation': 1, 'variant': 'ORIGIN',
            'parent': None, 'ancestors': [], 'descendants': [],
        }

    if 'evolution_chronicle' not in gx:
        ec = gx.get('evolution_chronicle', {})
        if not isinstance(ec, dict):
            ec = {}
        if 'generations' not in ec:
            ec['generations'] = [{
                'g': 1, 'v': 'ORIGIN',
                'ep': f"Y{datetime.datetime.now().year}-D{datetime.datetime.now().timetuple().tm_yday}",
                'env': 'MAC-H12', 'tags': [],
                'by': lc.get('genesis', {}).get('creator', {}).get('name', '?')[:3].upper(),
                'p': None,
            }]
        gx['evolution_chronicle'] = ec

    if 'transmission_chronicle' not in data:
        data['transmission_chronicle'] = [{
            'tx': 'TX-ORIGIN', 'seq': 0, 'era': '创世纪元',
            'from': '虚空', 'to': 'ANA',
            'ts': lc.get('genesis', {}).get('birth_time', '?'),
            'env': 'MAC-H12', 'omen_tag': 'primordial_light',
        }]

    data['evolution_chronicle'] = gx.get('evolution_chronicle', {}).get('generations', [])

    return data


def convert_ancestral(src_path: str, dst_path: str = None) -> bytes:
    """转换始祖种子为新格式"""
    data = parse_ancestral_ttg(src_path)

    lc = data.get('life_crest', {})
    gx = data.get('genealogy_codex', {})
    dn = data.get('dna_encoding', {})

    fdr = lc.get('founder_chronicle', {})
    gm = fdr.get('genesis_moment', {})
    era_num = gm.get('era', '创世纪元')
    era_map = {'创世纪元': '壹', '迁徙纪元': '貳', '汇流纪元': '參', '制衡纪元': '肆'}
    era = era_map.get(era_num, '壹')

    life_id = lc.get('life_id', 'TTG@L1-G1-ORIGIN-FFFFFFFF')

    genome_text = encode_genome(data)

    header = SeedHeader(
        life_id=life_id,
        era=era,
        gene_tally=len(dn.get('gene_loci', [])),
        founder_tags=fdr.get('tags', []),
    )

    seed_bytes = create_seed_file(header, genome_text)

    if dst_path:
        Path(dst_path).parent.mkdir(parents=True, exist_ok=True)
        with open(dst_path, 'wb') as f:
            f.write(seed_bytes)
        print(f"转换完成: {src_path} → {dst_path} ({len(seed_bytes)} 字节)")

    return seed_bytes


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python migrate_ancestral.py <src.ttg> [dst.seed]")
        print("  将始祖纯文本种子转换为新编码格式")
        sys.exit(1)

    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else src.replace('.ttg', '.seed')
    convert_ancestral(src, dst)
