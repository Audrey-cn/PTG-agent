#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║   🧪 基因筛 · Gene Sieve & 苗圃 · Nursery                   ║
║                                                              ║
║   「百花齐放，只取最艳；一粒入土，观其一生。」               ║
║                                                              ║
║   对应碳基生物学的自然选择机制：                            ║
║   - 基因筛(GeneSieve) → 自然选择筛选适应者                 ║
║   - 苗圃培育(Nursery) → 表型评估与适合度测试               ║
║   - 多维度评分 → 适合度(Fitness)评估                       ║
╚══════════════════════════════════════════════════════════════╝

碳基生物学对照：
- 自然选择(Natural Selection)：环境筛选适应者，淘汰不适应者
- 适合度(Fitness)：个体生存和繁殖能力的综合度量
- 表型评估(Phenotype Evaluation)：观察个体表现型特征
- 培育周期：对应个体发育过程，从种子到成熟个体
"""
import os, sys, re, json, datetime, hashlib, shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PROMETHEUS_HOME = os.path.dirname(os.path.abspath(__file__))
SEED_VAULT = os.path.expanduser("~/.hermes/seed-vault")
NURSERY_DIR = os.path.expanduser("~/.hermes/nursery")
os.makedirs(SEED_VAULT, exist_ok=True)
os.makedirs(NURSERY_DIR, exist_ok=True)


# =====================================================
# Part 1: Seed Loader (shared between Sieve & Nursery)
# =====================================================

def _load_seed_meta(path):
    """提取种子元数据，不完整解析，容忍格式问题。"""
    if not os.path.exists(path):
        return None
    with open(path, 'r') as f:
        content = f.read()

    meta = {"path": path, "size": len(content), "content": content}

    # life_id
    m = re.search(r'life_id:\s*"([^"]+)"', content)
    meta["life_id"] = m.group(1) if m else os.path.basename(path).replace('.ttg', '')

    # sacred_name
    m = re.search(r'sacred_name:\s*"([^"]+)"', content)
    meta["sacred_name"] = m.group(1) if m else "?"

    # generation
    m = re.search(r'generation:\s*(\d+)', content)
    meta["generation"] = int(m.group(1)) if m else 1

    # variant
    m = re.search(r'variant:\s*"([^"]+)"', content)
    meta["variant"] = m.group(1) if m else "?"

    # gene count
    genes = re.findall(r'locus:\s*"([^"]+)"', content)
    meta["gene_count"] = len(genes)
    meta["gene_ids"] = genes

    # carbon_bonded check
    meta["has_carbon"] = 'carbon_bonded: true' in content

    # forge_config
    m = re.search(r'forge_config:(.*?)(?=\n```|\n# 🔥|\Z)', content, re.DOTALL)
    if m:
        forge_raw = m.group(1)
        genes_added = re.search(r'genes_added:\s*(\[.*?\])', forge_raw)
        meta["forge_genes"] = json.loads(genes_added.group(1)) if genes_added else []
        parent = re.search(r'parent:\s*"([^"]+)"', forge_raw)
        meta["forge_parent"] = parent.group(1) if parent else None
    else:
        meta["forge_genes"] = []
        meta["forge_parent"] = None

    # checksum
    m = re.search(r'checksum:\s*"([^"]+)"', content)
    meta["checksum"] = m.group(1) if m else "?"

    return meta


# =====================================================
# Part 2: GeneSieve — 多维度筛选器
# =====================================================

class GeneSieve:
    """基因筛：从变异体批次中选出最优种子。"""

    DEFAULT_WEIGHTS = {
        "health": 0.30,       # 结构完整性
        "completeness": 0.20,  # 基因覆盖率
        "novelty": 0.25,      # 与亲代差异度
        "elegance": 0.15,     # 简洁性（奥卡姆剃刀）
        "stability": 0.10,    # 文件完整性
    }

    def __init__(self, weights=None):
        self.weights = weights or self.DEFAULT_WEIGHTS

    def screen_batch(self, lab_dir, parent_seed=None, top_k=5):
        """筛选一个锻造批次。

        Args:
            lab_dir: 锻造输出目录（含 .ttg 文件 + forge-manifest.json）
            parent_seed: 亲代种子路径（用于novelty计算）
            top_k: 返回前N名

        Returns:
            {batch_info, rankings: [...], top: [...], discard: [...]}
        """
        # 加载 manifest
        manifest_path = os.path.join(lab_dir, "forge-manifest.json")
        manifest = None
        if os.path.exists(manifest_path):
            with open(manifest_path) as f:
                manifest = json.load(f)

        # 加载所有变异体
        variants = []
        for fname in sorted(os.listdir(lab_dir)):
            if not fname.endswith('.ttg'):
                continue
            path = os.path.join(lab_dir, fname)
            meta = _load_seed_meta(path)
            if meta:
                variants.append(meta)

        if not variants:
            return {"error": "未找到变异体", "rankings": [], "top": [], "discard": []}

        # 加载亲代用于novelty计算
        parent_meta = None
        if parent_seed and os.path.exists(parent_seed):
            parent_meta = _load_seed_meta(parent_seed)

        # 计算每个变异体的分数
        scored = []
        for v in variants:
            scores = self._score_variant(v, parent_meta, variants)
            scored.append((scores["total"], scores, v))

        # 排序
        scored.sort(key=lambda x: x[0], reverse=True)

        # 分类
        cutoff = max(40, scored[0][0] * 0.5) if scored else 40
        top = [s for s in scored if s[0] >= 60][:top_k]
        discard = [s for s in scored if s[0] < cutoff]
        mid = [s for s in scored if cutoff <= s[0] < 60]

        return {
            "batch_id": manifest["batch_id"] if manifest else os.path.basename(lab_dir),
            "total": len(scored),
            "top_count": len(top),
            "discard_count": len(discard),
            "rankings": [
                {"rank": i+1, "id": s[2]["life_id"], "score": round(s[0], 1),
                 "detail": s[1], "path": s[2]["path"]}
                for i, s in enumerate(scored)
            ],
            "top": [
                {"rank": i+1, "id": s[2]["life_id"], "score": round(s[0], 1),
                 "detail": s[1], "path": s[2]["path"]}
                for i, s in enumerate(top)
            ],
            "discard": [
                {"id": s[2]["life_id"], "score": round(s[0], 1),
                 "reason": self._discard_reason(s[1])}
                for s in discard[:10]
            ],
        }

    def _score_variant(self, variant, parent, all_variants):
        """对单个变异体多维度打分，返回 {dim: score, total: weighted}"""
        w = self.weights

        health = self._score_health(variant)
        completeness = self._score_completeness(variant)
        novelty = self._score_novelty(variant, parent, all_variants)
        elegance = self._score_elegance(variant)
        stability = self._score_stability(variant)

        total = (health * w["health"] + completeness * w["completeness"] +
                 novelty * w["novelty"] + elegance * w["elegance"] +
                 stability * w["stability"])

        return {
            "health": round(health, 1),
            "completeness": round(completeness, 1),
            "novelty": round(novelty, 1),
            "elegance": round(elegance, 1),
            "stability": round(stability, 1),
            "total": round(total, 1),
        }

    def _score_health(self, v):
        """结构健康度：碳基存在 + 基因完整性"""
        score = 100
        if not v.get("has_carbon"):
            score -= 50  # 缺碳基是大问题
        if v.get("gene_count", 0) < 8:
            score -= 20
        # 检查是否有明显的YAML损坏
        if "error" in v.get("content", "").lower()[:500]:
            score -= 30
        return max(0, score)

    def _score_completeness(self, v):
        """基因完整性：必备基因是否存在"""
        required = ["G000", "G001", "G002", "G003", "G004", "G005", "G006", "G007", "G008"]
        genes = v.get("gene_ids", [])
        present = sum(1 for r in required if any(g.startswith(r) for g in genes))
        return (present / len(required)) * 100

    def _score_novelty(self, v, parent, all_variants):
        """新颖度：与亲代的基因差异程度"""
        if not parent:
            return 50  # 无亲代参考，中等分
        p_genes = set(parent.get("gene_ids", []))
        v_genes = set(v.get("gene_ids", []))
        if p_genes == v_genes:
            return 0   # 完全没变异
        added = v_genes - p_genes
        removed = p_genes - v_genes
        # 差异基因越多越新颖，但差异太大可能有问题
        diff_ratio = (len(added) + len(removed)) / max(len(p_genes), 1)
        return min(100, diff_ratio * 60 + 10)

    def _score_elegance(self, v):
        """简洁性：基因数适中（奥卡姆剃刀）"""
        count = v.get("gene_count", 9)
        base = 9
        if count == base:
            return 100
        elif count < base:
            return max(30, 100 - (base - count) * 15)
        else:
            return max(30, 100 - (count - base) * 8)

    def _score_stability(self, v):
        """文件稳定性：大小合理 + checksum有效"""
        size = v.get("size", 0)
        if size < 1000:
            return 10   # 太小，可能损坏
        if size > 500000:
            return 50   # 太大，可能冗余
        return 90

    def _discard_reason(self, scores):
        """解释为什么被淘汰"""
        reasons = []
        if scores["health"] < 40:
            reasons.append("健康度低")
        if scores["completeness"] < 60:
            reasons.append("基因残缺")
        if scores["novelty"] < 5:
            reasons.append("无变异（与亲代相同）")
        if scores["elegance"] < 40:
            reasons.append("基因冗余/过简")
        if scores["stability"] < 50:
            reasons.append("文件可能损坏")
        return ", ".join(reasons) if reasons else "总分偏低"

    # ── 操作 ──

    def promote(self, variant_path, name=None, to_vault=True):
        """将一个变异体提升为正式种子。"""
        if not os.path.exists(variant_path):
            return {"success": False, "message": "文件不存在"}

        meta = _load_seed_meta(variant_path)
        if not meta:
            return {"success": False, "message": "无法读取变异体"}

        # 命名
        new_name = name or meta.get("sacred_name", "unnamed")
        safe_name = re.sub(r'[^\w\-\.]', '_', new_name)
        fname = "{}.ttg".format(safe_name)

        if to_vault:
            dest = os.path.join(SEED_VAULT, fname)
            shutil.copy2(variant_path, dest)

            # 更新变异体的sacred_name并确保创始铭刻存在
            with open(dest, 'r') as f:
                content = f.read()
            content = re.sub(r'(sacred_name:\s*)"[^"]*"',
                             lambda m: m.group(1) + '"{}"'.format(new_name),
                             content)
            # 确保创始铭刻存在（安全网）
            from prometheus import inject_founder_chronicle
            import datetime
            epoch = "Y{}-D{}".format(datetime.datetime.now().year, datetime.datetime.now().timetuple().tm_yday)
            content = inject_founder_chronicle(content, epoch)
            with open(dest, 'w') as f:
                f.write(content)
        else:
            dest = variant_path

        return {
            "success": True,
            "message": "已提升: {} → {}".format(meta["life_id"], dest),
            "path": dest,
            "life_id": meta["life_id"],
            "name": new_name,
        }

    def discard_batch(self, lab_dir, keep_top=3):
        """清理批次，只保留前N个。"""
        result = self.screen_batch(lab_dir)
        if "error" in result:
            return result

        kept = []
        removed = []
        for i, r in enumerate(result["rankings"]):
            if i < keep_top:
                kept.append(r["id"])
            else:
                path = r["path"]
                if os.path.exists(path):
                    os.remove(path)
                    removed.append(r["id"])

        return {"kept": kept, "removed": removed, "message": "保留 {} 个，移除 {} 个".format(len(kept), len(removed))}


# =====================================================
# Part 3: Nursery — 苗圃沙箱
# =====================================================

class Nursery:
    """苗圃容器：在隔离环境中培育种子，模拟完整生命周期。

    培育周期：
    1. 入土 — 解析种子结构
    2. 发芽 — 逐个基因自检
    3. 生长 — 模拟三阶段生长评分
    4. 开花 — 综合健康报告
    """

    def __init__(self):
        self.pot_dir = os.path.join(NURSERY_DIR, "pots")
        os.makedirs(self.pot_dir, exist_ok=True)

    def plant(self, seed_path, pot_name=None):
        """将种子种入苗圃，开始培育。

        Returns: {pot_id, phases: {}}, report
        """
        if not os.path.exists(seed_path):
            return {"error": "种子文件不存在: {}".format(seed_path)}

        meta = _load_seed_meta(seed_path)
        pot_id = pot_name or "pot-{}".format(meta["life_id"][:20])
        pot_path = os.path.join(self.pot_dir, pot_id)

        # 阶段0：入土 — 校验结构
        phase_soil = self._phase_soil(seed_path, meta)

        # 阶段1：发芽 — 基因自检
        phase_sprout = self._phase_sprout(meta)

        # 阶段2：生长 — 模拟评分
        phase_grow = self._phase_grow(meta, phase_sprout)

        # 阶段3：开花 — 综合报告
        phase_bloom = self._phase_bloom(phase_soil, phase_sprout, phase_grow, meta)

        report = {
            "pot_id": pot_id,
            "seed": meta["life_id"],
            "sacred_name": meta["sacred_name"],
            "planted_at": datetime.datetime.now().isoformat(),
            "phases": {
                "soil": phase_soil,
                "sprout": phase_sprout,
                "grow": phase_grow,
                "bloom": phase_bloom,
            },
            "verdict": phase_bloom["verdict"],
            "overall_score": phase_bloom["overall_score"],
        }

        # 保存报告
        report_path = os.path.join(NURSERY_DIR, "{}-report.json".format(pot_id))
        with open(report_path, 'w') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        return report

    def _phase_soil(self, seed_path, meta):
        """入土阶段：结构完整性检查"""
        checks = []

        # 1. 文件可读
        checks.append({"check": "文件可读", "passed": True})

        # 2. YAML可解析
        content = meta.get("content", "")
        has_yaml = '```yaml' in content
        checks.append({"check": "YAML块存在", "passed": has_yaml})

        # 3. G000存在
        has_g000 = "G000" in str(meta.get("gene_ids", []))
        checks.append({"check": "G000创始印记", "passed": has_g000})

        # 4. 核心基因
        required = ["G001", "G002", "G003", "G004", "G005", "G006", "G007", "G008"]
        missing = [r for r in required if not any(g.startswith(r) for g in meta.get("gene_ids", []))]
        checks.append({
            "check": "核心基因 (8个)",
            "passed": len(missing) == 0,
            "detail": "缺失: {}".format(missing) if missing else "完整"
        })

        # 5. 碳基检查
        checks.append({"check": "碳基依赖标记", "passed": meta.get("has_carbon", False)})

        passed = sum(1 for c in checks if c["passed"])
        return {
            "name": "入土",
            "passed": passed,
            "total": len(checks),
            "checks": checks,
            "score": (passed / len(checks)) * 100,
        }

    def _phase_sprout(self, meta):
        """发芽阶段：逐个基因自检"""
        genes = meta.get("gene_ids", [])
        gene_checks = []

        for gid in genes:
            check = {"gene": gid, "passed": True, "issues": []}

            # 碳基基因：检查是否标记正确
            is_carbon = gid.startswith("G000")
            if is_carbon and not meta.get("has_carbon"):
                check["passed"] = False
                check["issues"].append("碳基基因未标记")

            # 检查基因名是否合理
            if len(gid) < 4:
                check["passed"] = False
                check["issues"].append("基因ID过短")

            gene_checks.append(check)

        passed = sum(1 for g in gene_checks if g["passed"])
        return {
            "name": "发芽",
            "passed": passed,
            "total": len(gene_checks),
            "gene_checks": gene_checks,
            "score": (passed / max(len(gene_checks), 1)) * 100,
        }

    def _phase_grow(self, meta, sprout):
        """生长阶段：模拟三阶段生长评分"""
        gene_count = meta.get("gene_count", 9)
        has_forge = bool(meta.get("forge_genes"))

        # 模拟生根分数：基础基因越多越稳
        root_score = min(100, gene_count * 8 + 20)

        # 模拟发芽分数：有forge标记说明经历过变异，生存力更强
        sprout_score = 70 if has_forge else 50

        # 模拟开花分数：基因种类多样性
        categories = set()
        for g in meta.get("gene_ids", []):
            if g.startswith("G0"):
                categories.add("foundation")
            elif g.startswith("G1"):
                categories.add("creative")
            elif g.startswith("G2"):
                categories.add("connectivity")
            elif g.startswith("G3"):
                categories.add("memory")
            elif g.startswith("G4"):
                categories.add("social")
        bloom_score = min(100, len(categories) * 25 + 25)

        return {
            "name": "生长",
            "phases": {
                "root": {"score": root_score, "label": "生根"},
                "sprout": {"score": sprout_score, "label": "发芽"},
                "bloom": {"score": bloom_score, "label": "开花"},
            },
            "score": (root_score + sprout_score + bloom_score) / 3,
        }

    def _phase_bloom(self, soil, sprout, grow, meta):
        """开花阶段：综合评估"""
        scores = [soil["score"], sprout["score"], grow["score"]]
        overall = sum(scores) / len(scores)

        if overall >= 80:
            verdict = "🌟 优质 — 可正式激活使用"
        elif overall >= 60:
            verdict = "🌿 良好 — 可用，建议微调后激活"
        elif overall >= 40:
            verdict = "🌱 一般 — 需要培育优化"
        else:
            verdict = "💀 不佳 — 建议淘汰或回炉重锻"

        return {
            "name": "开花",
            "verdict": verdict,
            "overall_score": round(overall, 1),
            "dimension_scores": {
                "结构完整性": round(soil["score"], 1),
                "基因健康度": round(sprout["score"], 1),
                "生长潜力": round(grow["score"], 1),
            },
            "gene_count": meta.get("gene_count", 0),
            "has_forge_history": bool(meta.get("forge_parent")),
        }


# =====================================================
# CLI
# =====================================================

def print_help():
    print("""
🧪 基因筛 + 苗圃 · GeneSieve & Nursery

基因筛 (sieve):
    python nursery.py sieve <批次目录>             筛选变异体批次
    python nursery.py sieve <批次目录> --top 3      前3名
    python nursery.py promote <变异体路径> [名称]   提升为正式种子
    python nursery.py discard <批次目录>            清理批次

苗圃 (nursery):
    python nursery.py plant <种子路径>              种入苗圃培育
    python nursery.py plant <种子路径> --name <盆名>

示例:
    python nursery.py sieve ~/.hermes/gene-lab/batch-001/
    python nursery.py plant ~/.hermes/seed-vault/my-seed.ttg
""")

def main():
    if len(sys.argv) < 2:
        print_help()
        return

    action = sys.argv[1]
    sieve = GeneSieve()
    nursery = Nursery()

    if action == 'sieve' and len(sys.argv) > 2:
        lab_dir = os.path.expanduser(sys.argv[2])
        top_k = 5
        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == '--top' and i+1 < len(sys.argv):
                top_k = int(sys.argv[i+1]); i += 2
            elif sys.argv[i] == '--parent' and i+1 < len(sys.argv):
                parent = sys.argv[i+1]; i += 2
            else:
                i += 1

        parent = None
        # Try to find parent from manifest
        manifest_path = os.path.join(lab_dir, "forge-manifest.json")
        if os.path.exists(manifest_path):
            with open(manifest_path) as f:
                mf = json.load(f)
            parent = mf.get("parent_seed")

        result = sieve.screen_batch(lab_dir, parent_seed=parent, top_k=top_k)

        if "error" in result:
            print("❌ {}".format(result["error"]))
            return

        print("\n🧬 基因筛选 · {} · {}个变异体".format(result["batch_id"], result["total"]))
        print("═══════════════════════════════════════════")
        print()

        if result["top"]:
            print("🌟 优胜区 (Top {}):".format(len(result["top"])))
            for t in result["top"]:
                d = t["detail"]
                print("  #{:<2} {}  总分 {:.0f}".format(t["rank"], t["id"][:30], t["score"]))
                print("       健康:{:.0f} 完整:{:.0f} 新颖:{:.0f} 简洁:{:.0f} 稳定:{:.0f}".format(
                    d["health"], d["completeness"], d["novelty"], d["elegance"], d["stability"]))
            print()

        if result["discard"]:
            print("💀 淘汰区 ({}个):".format(len(result["discard"])))
            for d in result["discard"][:5]:
                print("  {}  总分 {:.0f}  ({})".format(d["id"][:30], d["score"], d.get("reason", "")))
            if len(result["discard"]) > 5:
                print("  ... 还有 {} 个".format(len(result["discard"]) - 5))

    elif action == 'promote' and len(sys.argv) > 2:
        path = os.path.expanduser(sys.argv[2])
        name = sys.argv[3] if len(sys.argv) > 3 else None
        result = sieve.promote(path, name=name)
        if result["success"]:
            print("✅ {}".format(result["message"]))
        else:
            print("❌ {}".format(result["message"]))

    elif action == 'discard' and len(sys.argv) > 2:
        lab_dir = os.path.expanduser(sys.argv[2])
        keep = int(sys.argv[3]) if len(sys.argv) > 3 else 3
        result = sieve.discard_batch(lab_dir, keep_top=keep)
        if "error" in result:
            print("❌ {}".format(result["error"]))
        else:
            print("✅ {}".format(result["message"]))

    elif action == 'plant' and len(sys.argv) > 2:
        seed_path = os.path.expanduser(sys.argv[2])
        pot_name = None
        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == '--name' and i+1 < len(sys.argv):
                pot_name = sys.argv[i+1]; i += 2
            else:
                i += 1

        print("🌱 种入苗圃...")
        report = nursery.plant(seed_path, pot_name=pot_name)

        if "error" in report:
            print("❌ {}".format(report["error"]))
            return

        phases = report["phases"]
        print("\n🧪 苗圃培育报告 · {}".format(report["sacred_name"]))
        print("═══════════════════════════════════════")
        print("  种子: {}".format(report["seed"]))
        print()
        print("  🌍 入土  结构完整性  {:.0f}/100".format(phases["soil"]["score"]))
        for c in phases["soil"]["checks"]:
            mark = "✅" if c["passed"] else "❌"
            detail = " ({})".format(c.get("detail", "")) if c.get("detail") else ""
            print("    {} {}{}".format(mark, c["check"], detail))

        print("\n  🌱 发芽  基因自检    {:.0f}/100  ({}/{})".format(
            phases["sprout"]["score"], phases["sprout"]["passed"], phases["sprout"]["total"]))
        failed = [g for g in phases["sprout"]["gene_checks"] if not g["passed"]]
        if failed:
            for f in failed:
                print("    ❌ {}: {}".format(f["gene"], ", ".join(f["issues"])))
        else:
            print("    ✅ 全部基因通过")

        print("\n  🌿 生长  模拟评分    {:.0f}/100".format(phases["grow"]["score"]))
        for k, v in phases["grow"]["phases"].items():
            print("    {}: {:.0f} ({})".format(k, v["score"], v["label"]))

        print("\n  🌸 开花  综合评估")
        print("    总分: {:.0f}/100".format(phases["bloom"]["overall_score"]))
        print("    判定: {}".format(phases["bloom"]["verdict"]))
        print("    基因数: {} | 锻造史: {}".format(
            phases["bloom"]["gene_count"],
            "有" if phases["bloom"]["has_forge_history"] else "无"))

    else:
        print_help()

if __name__ == "__main__":
    main()
