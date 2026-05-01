#!/usr/bin/env python3
"""╔══════════════════════════════════════════════════════════════╗."""

import datetime
import hashlib
import itertools
import json
import os
import re
import sys

# 确保可以导入同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PROMETHEUS_HOME = os.path.dirname(os.path.abspath(__file__))
GENE_LAB = os.path.expanduser("~/.hermes/gene-lab")
os.makedirs(GENE_LAB, exist_ok=True)

# =====================================================
# MutationSpace — 变异空间定义
# =====================================================


class MutationSpace:
    """定义变异实验的参数空间。

    变异维度：
    - genes: 可选基因ID列表，如 ["G100-writer", "G101-vision"]
    - combinations: "power_set"(所有子集) | "all"(仅全集) | "single"(逐个) | 自定义列表
    - ordering: 是否排列基因顺序（默认False）
    - max_variants: 最大变异体数（防爆炸，默认50）
    """

    def __init__(self, genes=None, combinations="power_set", ordering=False, max_variants=50):
        self.genes = genes or []
        self.combinations = combinations
        self.ordering = ordering
        self.max_variants = max_variants

    def expand(self):
        """展开变异空间为具体的基因组合列表。"""
        if not self.genes:
            return [[]]

        if self.combinations == "power_set":
            combos = []
            for r in range(len(self.genes) + 1):
                combos.extend([list(c) for c in itertools.combinations(self.genes, r)])
        elif self.combinations == "all":
            combos = [list(self.genes)]
        elif self.combinations == "single":
            combos = [[g] for g in self.genes] + [[]]
        elif isinstance(self.combinations, list):
            combos = self.combinations
        else:
            combos = [list(self.genes)]

        if self.ordering:
            permuted = []
            for combo in combos:
                if len(combo) <= 1:
                    permuted.append(combo)
                else:
                    permuted.extend([list(p) for p in itertools.permutations(combo)])
            combos = permuted

        if len(combos) > self.max_variants:
            print(
                f"⚠️ 变异体数量 ({len(combos)}) 超过上限 ({self.max_variants}), 截断至 {self.max_variants}"
            )
            combos = combos[: self.max_variants]

        return combos

    def describe(self):
        parts = []
        if self.genes:
            parts.append("基因池: [{}]".format(", ".join(self.genes)))
        parts.append(f"组合模式: {self.combinations}")
        if self.ordering:
            parts.append("排列: 开启")
        parts.append(f"上限: {self.max_variants}")
        return " | ".join(parts)


# =====================================================
# 锻造引擎内部函数
# =====================================================


def _load_content(path):
    with open(path) as f:
        return f.read()


def _generate_variant_id(parent_id, gen, variant_num):
    """TTG@L1-G3-V042-A3F7"""
    base = parent_id.split("-G")[0] if "-G" in parent_id else parent_id.rsplit("-", 1)[0]
    seed_str = f"{base}-G{gen}-V{variant_num:03d}"
    checksum = hashlib.md5(seed_str.encode()).hexdigest()[:4].upper()
    return f"TTG@L1-G{gen}-V{variant_num:03d}-{checksum}"


def _apply_gene_insertions(content, genes_to_add):
    """在种子内容中插入多个基因。"""
    if not genes_to_add:
        return content

    # 加载基因库（本地文件加载，避免复杂import）
    catalog_path = os.path.join(PROMETHEUS_HOME, "genes", "gene_catalog.json")
    with open(catalog_path) as f:
        catalog = json.load(f)

    def find_gene(gene_id):
        if gene_id in catalog.get("standard", {}):
            return catalog["standard"][gene_id]
        for opt in catalog.get("optional", []):
            if opt.get("gene_id") == gene_id:
                return opt
        return None

    for gene_id in genes_to_add:
        gene_def = find_gene(gene_id)
        if not gene_def:
            continue
        if 'locus: "' + gene_id + '"' in content:
            continue

        name = gene_def.get("name", gene_id)
        entry = f'    - locus: "{gene_id}"\n'
        entry += f'      name: "{name}"\n'
        entry += f'      default: "{gene_id}_v1"\n'
        entry += '      mutable_range: "configuration, behavior_params"\n'
        entry += '      immutable: "core_functionality"\n'
        entry += '      source: "gene_catalog"'

        lines = content.split("\n")
        loci_start = loci_end = None
        for i, line in enumerate(lines):
            if line.strip() == "gene_loci:":
                loci_start = i
            if loci_start is not None and line.strip() == "```" and i > loci_start + 5:
                loci_end = i
                break

        if loci_start is None or loci_end is None:
            continue

        new_lines = lines[:loci_end] + [entry] + lines[loci_end:]
        content = "\n".join(new_lines)

    return content


def _forge_one(parent_path, parent_id, genes_to_add, gen, variant_num, output_dir):
    """锻造单个变异体。"""
    content = _load_content(parent_path)

    # 插入基因
    content = _apply_gene_insertions(content, genes_to_add)

    # 更新 generation
    content = re.sub(r"(generation:\s*)(\d+)", lambda m: m.group(1) + str(gen), content, count=1)

    # 更新 variant
    variant_code = f"V{variant_num:03d}"
    content = re.sub(
        r'(variant:\s*)"[^"]*"', lambda m: m.group(1) + f'"{variant_code}"', content, count=1
    )

    # 更新 variant_epithet
    gene_desc = "+".join([g.split("-")[0] for g in genes_to_add]) if genes_to_add else "pure"
    epithet = f"锻炉第{variant_num}号 · {gene_desc}"
    content = re.sub(
        r'(variant_epithet:\s*)"[^"]*"', lambda m: m.group(1) + f'"{epithet}"', content, count=1
    )

    # 更新 life_id
    new_id = _generate_variant_id(parent_id, gen, variant_num)
    content = re.sub(
        r'(life_id:\s*)"[^"]*"', lambda m: m.group(1) + f'"{new_id}"', content, count=1
    )

    # 更新 sacred_name（追加变异标记）
    content = re.sub(
        r'(sacred_name:\s*)"([^"]*)"',
        lambda m: m.group(1) + f'"{m.group(2)}·{variant_code}"',
        content,
        count=1,
    )

    # 注入 forge_config 标记
    forge_stamp = "\n# 🔥 基因锻炉 · 变异记录\nforge_config:\n"
    forge_stamp += f'  batch_id: "{parent_id}-G{gen}"\n'
    forge_stamp += f"  variant: {variant_num}\n"
    forge_stamp += f'  parent: "{parent_id}"\n'
    forge_stamp += f"  genes_added: {json.dumps(genes_to_add, ensure_ascii=False)}\n"
    forge_stamp += f'  forge_time: "{datetime.datetime.now().isoformat()}"\n'

    last_tick = content.rfind("```")
    if last_tick > 0:
        content = content[:last_tick] + forge_stamp + "\n" + content[last_tick:]

    # 更新 checksum
    new_checksum = hashlib.md5(content.encode()).hexdigest()[:8].upper()
    content = re.sub(r'checksum:\s*"[^"]*"', 'checksum: "' + new_checksum + '"', content)

    # 注入创始铭刻（普罗米修斯签名）
    from prometheus import inject_founder_chronicle

    epoch = f"Y{datetime.datetime.now().year}-D{datetime.datetime.now().timetuple().tm_yday}"
    content = inject_founder_chronicle(content, epoch)

    # 保存
    fname = f"{new_id}.ttg"
    fpath = os.path.join(output_dir, fname)
    with open(fpath, "w") as f:
        f.write(content)

    return fpath, new_id


# =====================================================
# 公共 API
# =====================================================


def forge(
    parent_seed,
    mutation_space=None,
    output_dir=None,
    batch_name=None,
    genes=None,
    combinations="power_set",
    ordering=False,
    max_variants=50,
):
    """
    基因锻造主函数。

    Args:
        parent_seed: 亲代种子路径
        mutation_space: MutationSpace 实例（与 genes/combinations 二选一）
        output_dir: 输出目录
        batch_name: 批次名称
        genes, combinations, ordering, max_variants: 快捷参数

    Returns:
        manifest dict
    """
    parent_seed = os.path.expanduser(parent_seed)
    if not os.path.exists(parent_seed):
        return {"error": f"亲代种子不存在: {parent_seed}"}

    # 解析变异空间
    if mutation_space is None:
        mutation_space = MutationSpace(
            genes=genes, combinations=combinations, ordering=ordering, max_variants=max_variants
        )

    # 解析亲代信息
    parent_content = _load_content(parent_seed)
    m = re.search(r'life_id:\s*"([^"]+)"', parent_content)
    parent_id = m.group(1) if m else "UNKNOWN"
    m = re.search(r"generation:\s*(\d+)", parent_content)
    parent_gen = int(m.group(1)) if m else 1

    # 展开变异空间
    combos = mutation_space.expand()

    # 创建输出目录
    if not output_dir:
        now = datetime.datetime.now()
        bid = batch_name or "batch-{}".format(now.strftime("%Y%m%d-%H%M%S"))
        output_dir = os.path.join(GENE_LAB, bid)
    os.makedirs(output_dir, exist_ok=True)

    # 锻造
    new_gen = parent_gen + 1
    manifest = {
        "batch_id": os.path.basename(output_dir),
        "parent_seed": parent_seed,
        "parent_id": parent_id,
        "parent_generation": parent_gen,
        "mutation_space": {
            "genes": mutation_space.genes,
            "combinations": mutation_space.combinations,
            "ordering": mutation_space.ordering,
        },
        "forge_time": datetime.datetime.now().isoformat(),
        "variant_count": len(combos),
        "variants": [],
    }

    for i, combo in enumerate(combos):
        variant_num = i + 1
        fpath, new_id = _forge_one(parent_seed, parent_id, combo, new_gen, variant_num, output_dir)
        manifest["variants"].append(
            {"num": variant_num, "id": new_id, "genes": combo, "path": fpath}
        )

    # 保存 manifest
    manifest_path = os.path.join(output_dir, "forge-manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # 生成日志
    log_path = os.path.join(output_dir, "forge-log.md")
    _write_forge_log(manifest, log_path)

    return manifest


def _write_forge_log(manifest, log_path):
    ms = manifest["mutation_space"]
    lines = [
        "# 🔥 基因锻炉 · 锻造日志",
        "",
        "| 属性 | 值 |",
        "|------|----|",
        "| 批次 | {} |".format(manifest["batch_id"]),
        "| 亲代 | {} (G{}) |".format(manifest["parent_id"], manifest["parent_generation"]),
        "| 基因池 | {} |".format(", ".join(ms["genes"])),
        "| 组合模式 | {} |".format(ms["combinations"]),
        "| 顺序排列 | {} |".format("是" if ms["ordering"] else "否"),
        "| 产出 | {} 个变异体 |".format(manifest["variant_count"]),
        "| 时间 | {} |".format(manifest["forge_time"]),
        "",
        "## 变异体清单",
        "",
        "| # | ID | 基因 |",
        "|---|---|------|",
    ]
    for v in manifest["variants"]:
        gene_str = ", ".join(v["genes"]) if v["genes"] else "（纯亲代）"
        lines.append("| {} | {} | {} |".format(v["num"], v["id"], gene_str))

    with open(log_path, "w") as f:
        f.write("\n".join(lines))


# =====================================================
# CLI
# =====================================================


def print_help():
    print("""
🔥 基因锻炉 · GeneForge

用法:
    python geneforge.py forge <亲代种子> [选项]

选项:
    --genes G100,G101,G200    可选基因列表（逗号分隔）
    --mode power_set           组合模式：power_set|all|single
    --ordering                 开启基因顺序排列
    --max 50                   最大变异体数（默认50）
    --output <目录>            输出目录
    --name <名称>              批次名称

示例:
    python geneforge.py forge ~/.hermes/skills/teach-to-grow/teach-to-grow-core.ttg \\
        --genes G100-writer,G101-vision,G200-network \\
        --mode power_set --max 20
""")


def main():
    if len(sys.argv) < 2:
        print_help()
        return

    action = sys.argv[1]

    if action == "forge" and len(sys.argv) > 2:
        parent = sys.argv[2]
        genes_str = None
        mode = "power_set"
        ordering = False
        max_v = 50
        output_dir = None
        batch_name = None

        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == "--genes" and i + 1 < len(sys.argv):
                genes_str = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--mode" and i + 1 < len(sys.argv):
                mode = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--ordering":
                ordering = True
                i += 1
            elif sys.argv[i] == "--max" and i + 1 < len(sys.argv):
                max_v = int(sys.argv[i + 1])
                i += 2
            elif sys.argv[i] == "--output" and i + 1 < len(sys.argv):
                output_dir = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--name" and i + 1 < len(sys.argv):
                batch_name = sys.argv[i + 1]
                i += 2
            else:
                i += 1

        genes = genes_str.split(",") if genes_str else []

        print("🔥 基因锻炉启动")
        ms = MutationSpace(genes=genes, combinations=mode, ordering=ordering, max_variants=max_v)
        print(f"  变异空间: {ms.describe()}")

        combos = ms.expand()
        print(f"  展开为 {len(combos)} 个变异体")

        manifest = forge(parent, ms, output_dir=output_dir, batch_name=batch_name)

        if "error" in manifest:
            print("❌ {}".format(manifest["error"]))
            return

        print("\n✅ 锻造完成!")
        print("  批次: {}".format(manifest["batch_id"]))
        print("  产出: {} 个变异体".format(manifest["variant_count"]))
        print("  输出: ~/.hermes/gene-lab/{}/".format(manifest["batch_id"]))

        # 展示前5个
        for v in manifest["variants"][:5]:
            genes_label = ", ".join(v["genes"]) if v["genes"] else "纯亲代"
            print("    V{:03d}  {}  [{}]".format(v["num"], v["id"], genes_label))
        if len(manifest["variants"]) > 5:
            print("    ... 还有 {} 个".format(len(manifest["variants"]) - 5))

    else:
        print_help()


if __name__ == "__main__":
    main()
