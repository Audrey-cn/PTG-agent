#!/usr/bin/env python3
"""╔══════════════════════════════════════════════════════════════╗."""

import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

GENES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "genes")
CATALOG_PATH = os.path.join(GENES_DIR, "gene_catalog.json")
VERSIONS_PATH = os.path.join(GENES_DIR, "_versions.json")
FUSIONS_PATH = os.path.join(GENES_DIR, "_fusions.json")

os.makedirs(GENES_DIR, exist_ok=True)

# =====================================================
# Catalog I/O
# =====================================================


def _load_catalog():
    if os.path.exists(CATALOG_PATH):
        with open(CATALOG_PATH) as f:
            return json.load(f)
    return {"standard": {}, "optional": []}


def _save_catalog(catalog):
    with open(CATALOG_PATH, "w") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)


def _load_versions():
    if os.path.exists(VERSIONS_PATH):
        with open(VERSIONS_PATH) as f:
            return json.load(f)
    return []


def _save_versions(versions):
    with open(VERSIONS_PATH, "w") as f:
        json.dump(versions, f, ensure_ascii=False, indent=2)


def _load_fusions():
    if os.path.exists(FUSIONS_PATH):
        with open(FUSIONS_PATH) as f:
            return json.load(f)
    return []


def _save_fusions(fusions):
    with open(FUSIONS_PATH, "w") as f:
        json.dump(fusions, f, ensure_ascii=False, indent=2)


def _find_gene(gene_id):
    """在标准基因和可选基因中查找。返回 (catalog, gene_def, section)"""
    catalog = _load_catalog()
    if gene_id in catalog.get("standard", {}):
        gdef = dict(catalog["standard"][gene_id])
        gdef.setdefault("gene_id", gene_id)  # 标准化：确保有 gene_id
        return catalog, gdef, "standard"
    for i, opt in enumerate(catalog.get("optional", [])):
        if opt.get("gene_id") == gene_id:
            return catalog, opt, ("optional", i)
    return catalog, None, None


# =====================================================
# GeneBank 核心操作
# =====================================================


class GeneBank:
    """基因库管理器。"""

    # ── 增 ──

    def add(self, gene_def):
        """添加新基因模板。

        gene_def 必需字段：
            gene_id: str      — 如 "G500-synthesizer"
            name: str         — 如 "综合处理器"
            category: str     — eternal|foundation|growth|reproduction|memory|ecosystem|safety|creative|connectivity|social
            description: str  — 功能描述

        可选字段：
            carbon_bonded: bool
            compatible_with: [str]
            conflicts_with: [str]
            mutations_allowed: [str]
            safety_note: str

        Returns: {success, message, gene_id}
        """
        catalog = _load_catalog()
        gene_id = gene_def.get("gene_id")
        if not gene_id:
            return {"success": False, "message": "缺少 gene_id"}

        # 查重
        _, existing, section = _find_gene(gene_id)
        if existing:
            return {"success": False, "message": f"基因 {gene_id} 已存在 ({section})"}

        name = gene_def.get("name", gene_id)
        category = gene_def.get("category", "custom")

        # 构建标准条目
        entry = {
            "gene_id": gene_id,
            "name": name,
            "category": category,
            "description": gene_def.get("description", ""),
            "version": 1,
            "created": datetime.datetime.now().isoformat(),
            "updated": datetime.datetime.now().isoformat(),
        }

        if gene_def.get("carbon_bonded"):
            entry["carbon_bonded"] = True
        if gene_def.get("compatible_with"):
            entry["compatible_with"] = gene_def["compatible_with"]
        if gene_def.get("conflicts_with"):
            entry["conflicts_with"] = gene_def["conflicts_with"]
        if gene_def.get("mutations_allowed"):
            entry["mutations_allowed"] = gene_def["mutations_allowed"]
        if gene_def.get("safety_note"):
            entry["safety_note"] = gene_def["safety_note"]

        # 碳基基因 → standard，其他 → optional
        if entry.get("carbon_bonded"):
            catalog["standard"][gene_id] = entry
            _save_catalog(catalog)
        else:
            catalog.setdefault("optional", []).append(entry)
            _save_catalog(catalog)

        # 记录版本
        self._log_version(gene_id, "create", {"version": 1})

        # 同时写入独立基因文件
        self._write_gene_file(gene_id, entry)

        return {"success": True, "message": f"基因 {gene_id} ({name}) 已入库", "gene_id": gene_id}

    # ── 删 ──

    def remove(self, gene_id, force=False):
        """删除基因模板。

        碳基基因（standard）默认不可删除，需 force=True。
        删除前检查：是否有任何种子引用了这个基因。
        """
        _, gene_def, section = _find_gene(gene_id)
        if not gene_def:
            return {"success": False, "message": f"基因 {gene_id} 不存在"}

        if section == "standard" and not force:
            return {
                "success": False,
                "message": f"基因 {gene_id} 是碳基/标准基因，不可删除（--force 强制）",
            }

        catalog = _load_catalog()

        if section == "standard":
            del catalog["standard"][gene_id]
        else:
            idx = section[1]
            catalog["optional"].pop(idx)

        _save_catalog(catalog)
        self._log_version(gene_id, "remove", {})

        # 删除独立文件
        gene_file = os.path.join(GENES_DIR, "{}.json".format(gene_id.replace("-", "_")))
        if os.path.exists(gene_file):
            os.remove(gene_file)

        return {"success": True, "message": f"基因 {gene_id} 已从库中移除"}

    # ── 改 ──

    def edit(self, gene_id, updates):
        """编辑基因模板的字段。

        updates: dict — 要更新的字段（name, description, compatible_with, etc.）

        不可编辑字段：gene_id（改名需先删除再重建）, carbon_bonded（不可改变碳基状态）
        """
        catalog, gene_def, section = _find_gene(gene_id)
        if not gene_def:
            return {"success": False, "message": f"基因 {gene_id} 不存在"}

        forbidden = ["gene_id", "carbon_bonded", "version"]
        for key in forbidden:
            if key in updates:
                return {"success": False, "message": f"字段 '{key}' 不可直接编辑"}

        # 应用更新
        for key, value in updates.items():
            if value is None:
                gene_def.pop(key, None)
            else:
                gene_def[key] = value

        gene_def["version"] = gene_def.get("version", 1) + 1
        gene_def["updated"] = datetime.datetime.now().isoformat()

        _save_catalog(catalog)
        self._log_version(
            gene_id, "edit", {"version": gene_def["version"], "changes": list(updates.keys())}
        )
        self._write_gene_file(gene_id, gene_def)

        return {
            "success": True,
            "message": "基因 {} 已更新至 v{}".format(gene_id, gene_def["version"]),
            "gene_id": gene_id,
            "version": gene_def["version"],
        }

    # ── 融合 ──

    def fuse(self, gene_a, gene_b, new_gene_id=None, new_name=None, strategy="merge"):
        """融合两个基因 → 产生新基因。

        strategy:
            "merge"    — 合并兼容列表和突变允许范围
            "extend"   — B 作为 A 的扩展（A 为主）
            "synthesize" — 两者平等融合

        Returns: {success, message, new_gene_id, fusion_analysis}
        """
        _, def_a, _ = _find_gene(gene_a)
        _, def_b, _ = _find_gene(gene_b)

        if not def_a:
            return {"success": False, "message": f"基因 A ({gene_a}) 不存在"}
        if not def_b:
            return {"success": False, "message": f"基因 B ({gene_b}) 不存在"}

        # 冲突检测
        conflicts = []
        cat_a = def_a.get("category", "?")
        cat_b = def_b.get("category", "?")
        if cat_a != cat_b and cat_a != "eternal" and cat_b != "eternal":
            conflicts.append(f"类别不同: {cat_a} vs {cat_b}")

        if def_a.get("conflicts_with") and gene_b in def_a["conflicts_with"]:
            conflicts.append(f"{gene_a} 声明与 {gene_b} 冲突")
        if def_b.get("conflicts_with") and gene_a in def_b["conflicts_with"]:
            conflicts.append(f"{gene_b} 声明与 {gene_a} 冲突")

        # 兼容性分析
        compat_a = set(def_a.get("compatible_with", []))
        compat_b = set(def_b.get("compatible_with", []))
        shared = compat_a & compat_b
        unique_a = compat_a - compat_b
        unique_b = compat_b - compat_a

        # 构建新基因
        new_id = new_gene_id or "G{}-fusion".format(
            gene_a.split("-")[0] + gene_b.split("-")[0] if "-" in gene_a else gene_a
        )
        new_name_val = new_name or "{}·{}融合体".format(
            def_a.get("name", gene_a), def_b.get("name", gene_b)
        )

        merged_cat = cat_a if cat_a == cat_b else "synthesis"
        merged_desc = "[融合] {} + {}: {}".format(
            gene_a,
            gene_b,
            def_a.get("description", "")[:60] + " | " + def_b.get("description", "")[:60],
        )
        merged_compat = list(compat_a | compat_b)
        merged_mutations = list(
            set(def_a.get("mutations_allowed", []) + def_b.get("mutations_allowed", []))
        )

        new_gene = {
            "gene_id": new_id,
            "name": new_name_val,
            "category": merged_cat,
            "description": merged_desc,
            "compatible_with": merged_compat,
            "mutations_allowed": merged_mutations,
            "version": 1,
            "created": datetime.datetime.now().isoformat(),
            "fusion_of": [gene_a, gene_b],
            "fusion_strategy": strategy,
        }

        # 如果有冲突，标记但不阻止
        if conflicts:
            new_gene["fusion_conflicts"] = conflicts

        result = self.add(new_gene)
        if result["success"]:
            # 记录融合操作
            fusions = _load_fusions()
            fusions.append(
                {
                    "time": datetime.datetime.now().isoformat(),
                    "gene_a": gene_a,
                    "gene_b": gene_b,
                    "result": new_id,
                    "strategy": strategy,
                    "conflicts": conflicts,
                    "compatibility": {
                        "shared": list(shared),
                        "unique_to_a": list(unique_a),
                        "unique_to_b": list(unique_b),
                    },
                }
            )
            _save_fusions(fusions)
            result["fusion_analysis"] = {
                "conflicts": conflicts,
                "compatibility": {
                    "shared": list(shared),
                    "unique_to_a": list(unique_a),
                    "unique_to_b": list(unique_b),
                },
            }

        return result

    # ── 查 ──

    def list_all(self):
        """列出所有基因。"""
        catalog = _load_catalog()
        standard = []
        for gid, gdef in catalog.get("standard", {}).items():
            gdef = dict(gdef)
            gdef.setdefault("gene_id", gid)  # 标准化
            gdef["section"] = "standard"
            standard.append(gdef)
        optional = []
        for gdef in catalog.get("optional", []):
            gdef = dict(gdef)
            gdef["section"] = "optional"
            optional.append(gdef)
        return {"standard": standard, "optional": optional}

    def get(self, gene_id):
        """查看单个基因详情。"""
        _, gene_def, section = _find_gene(gene_id)
        if not gene_def:
            return None
        result = dict(gene_def)
        result["section"] = section if isinstance(section, str) else "optional"
        # 添加版本历史
        versions = _load_versions()
        result["version_history"] = [v for v in versions if v.get("gene_id") == gene_id]
        return result

    # ── 校验 ──

    def validate(self):
        """校验整个基因库的完整性。"""
        catalog = _load_catalog()
        issues = []
        all_ids = set()

        for gid in catalog.get("standard", {}):
            all_ids.add(gid)
        for gdef in catalog.get("optional", []):
            gid = gdef.get("gene_id", "")
            if gid:
                all_ids.add(gid)

        def _resolve(ref):
            """解析引用：支持 G001 → G001-parser 的简写"""
            if ref in all_ids:
                return True
            # 尝试前缀匹配
            return any(full_id.startswith(ref + "-") for full_id in all_ids)

        def _check(gdef, location):
            gid = gdef.get("gene_id", "?")
            for field in ["name", "category", "description"]:
                if not gdef.get(field):
                    issues.append(f"[{gid}] 缺少字段: {field}")
            for compat in gdef.get("compatible_with", []):
                if not _resolve(compat):
                    issues.append(f"[{gid}] compatible_with 指向不存在基因: {compat}")

        for gid, gdef in catalog.get("standard", {}).items():
            gdef = dict(gdef)
            gdef.setdefault("gene_id", gid)
            _check(gdef, "standard")
        for gdef in catalog.get("optional", []):
            _check(gdef, "optional")

        return {
            "total_genes": len(all_ids),
            "standard_count": len(catalog.get("standard", {})),
            "optional_count": len(catalog.get("optional", [])),
            "issues": issues,
            "healthy": len(issues) == 0,
        }

    # ── 版本历史 ──

    def _log_version(self, gene_id, action, detail):
        versions = _load_versions()
        versions.append(
            {
                "gene_id": gene_id,
                "action": action,
                "detail": detail,
                "time": datetime.datetime.now().isoformat(),
            }
        )
        _save_versions(versions)

    def version_history(self, gene_id=None):
        """查看版本历史。gene_id=None 返回全部。"""
        versions = _load_versions()
        if gene_id:
            versions = [v for v in versions if v.get("gene_id") == gene_id]
        return versions

    # ── 独立文件 ──

    def _write_gene_file(self, gene_id, gene_def):
        """将基因定义写入独立文件。"""
        fname = gene_id.replace("-", "_") + ".json"
        fpath = os.path.join(GENES_DIR, fname)
        with open(fpath, "w") as f:
            json.dump(gene_def, f, ensure_ascii=False, indent=2)

    # ── 快照 ──

    def snapshot(self, note=""):
        """保存基因库快照。"""
        snapshot_dir = os.path.join(GENES_DIR, "_snapshots")
        os.makedirs(snapshot_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        fname = f"catalog-{ts}.json"
        fpath = os.path.join(snapshot_dir, fname)

        catalog = _load_catalog()
        with open(fpath, "w") as f:
            json.dump(
                {"catalog": catalog, "note": note, "time": ts}, f, ensure_ascii=False, indent=2
            )
        return fpath


# =====================================================
# CLI
# =====================================================


def print_help():
    print("""
🏦 基因银行 · GeneBank

用法:
    python genebank.py list                       列出全部基因
    python genebank.py show <基因ID>              查看基因详情
    python genebank.py add <JSON定义>              添加基因
    python genebank.py edit <基因ID> <JSON更新>    编辑基因
    python genebank.py remove <基因ID> [--force]   删除基因
    python genebank.py fuse <A> <B> [--name <名称>] 融合基因
    python genebank.py validate                    校验基因库
    python genebank.py versions [<基因ID>]         版本历史
    python genebank.py snapshot [<备注>]           保存快照

示例:
    python genebank.py add '{"gene_id":"G500-test","name":"测试基因","category":"custom","description":"测试"}'
    python genebank.py edit G100-writer '{"description":"改进的写作注入器 v2"}'
    python genebank.py fuse G100-writer G101-vision --name "创意表达器"
""")


def main():
    if len(sys.argv) < 2:
        print_help()
        return

    bank = GeneBank()
    action = sys.argv[1]

    if action == "list":
        all_genes = bank.list_all()
        print("\n🏦 基因银行 · 库存总览\n")
        print("═══ 标准基因 ({}个) ═══".format(len(all_genes["standard"])))
        for g in all_genes["standard"]:
            carbon = " ◆碳基" if g.get("carbon_bonded") else ""
            gid = g.get("gene_id") or g.get("locus", "?")
            print("  {} · {} [{}]{}".format(gid, g["name"], g["category"], carbon))
        print("\n═══ 可选基因 ({}个) ═══".format(len(all_genes["optional"])))
        for g in all_genes["optional"]:
            gid = g.get("gene_id") or g.get("locus", "?")
            print("  {} · {} [{}] v{}".format(gid, g["name"], g["category"], g.get("version", 1)))

    elif action == "show" and len(sys.argv) > 2:
        gene = bank.get(sys.argv[2])
        if not gene:
            print(f"❌ 基因 {sys.argv[2]} 不存在")
            return
        print("\n🧬 {}".format(gene["gene_id"]))
        print("  名称: {}".format(gene["name"]))
        print("  类别: {}".format(gene.get("category", "?")))
        print("  区域: {}".format(gene.get("section", "?")))
        print("  版本: v{}".format(gene.get("version", 1)))
        print("  描述: {}".format(gene.get("description", "")))
        if gene.get("carbon_bonded"):
            print("  ⚠️ 碳基依赖级")
        if gene.get("compatible_with"):
            print("  兼容: {}".format(", ".join(gene["compatible_with"])))
        if gene.get("conflicts_with"):
            print("  冲突: {}".format(", ".join(gene["conflicts_with"])))
        if gene.get("mutations_allowed"):
            print("  可变: {}".format(", ".join(gene["mutations_allowed"])))
        if gene.get("safety_note"):
            print("  🛡️ {}".format(gene["safety_note"]))
        if gene.get("fusion_of"):
            print("  融合自: {} + {}".format(gene["fusion_of"][0], gene["fusion_of"][1]))
        if gene.get("version_history"):
            print("\n  📜 版本历史:")
            for v in gene["version_history"][-5:]:
                print(
                    "    {}  {}  v{}".format(
                        v["time"][:16], v["action"], v.get("detail", {}).get("version", "?")
                    )
                )

    elif action == "add" and len(sys.argv) > 2:
        gene_def = json.loads(sys.argv[2])
        result = bank.add(gene_def)
        if result["success"]:
            print("✅ {}".format(result["message"]))
        else:
            print("❌ {}".format(result["message"]))

    elif action == "edit" and len(sys.argv) > 3:
        gene_id = sys.argv[2]
        updates = json.loads(sys.argv[3])
        result = bank.edit(gene_id, updates)
        if result["success"]:
            print("✅ {}".format(result["message"]))
        else:
            print("❌ {}".format(result["message"]))

    elif action == "remove" and len(sys.argv) > 2:
        gene_id = sys.argv[2]
        force = "--force" in sys.argv
        result = bank.remove(gene_id, force)
        if result["success"]:
            print("✅ {}".format(result["message"]))
        else:
            print("❌ {}".format(result["message"]))

    elif action == "fuse" and len(sys.argv) > 3:
        gene_a = sys.argv[2]
        gene_b = sys.argv[3]
        new_name = None
        new_id = None
        i = 4
        while i < len(sys.argv):
            if sys.argv[i] == "--name" and i + 1 < len(sys.argv):
                new_name = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--id" and i + 1 < len(sys.argv):
                new_id = sys.argv[i + 1]
                i += 2
            else:
                i += 1

        result = bank.fuse(gene_a, gene_b, new_gene_id=new_id, new_name=new_name)
        if result["success"]:
            print("✅ {}".format(result["message"]))
            if result.get("fusion_analysis"):
                fa = result["fusion_analysis"]
                if fa["conflicts"]:
                    print("⚠️ 冲突: {}".format(", ".join(fa["conflicts"])))
                comp = fa["compatibility"]
                print("  共享兼容: {}".format(comp["shared"]))
                print("  A独有: {}  B独有: {}".format(comp["unique_to_a"], comp["unique_to_b"]))
        else:
            print("❌ {}".format(result["message"]))

    elif action == "validate":
        result = bank.validate()
        if result["healthy"]:
            print("✅ 基因库健康 ({}个基因, 0个问题)".format(result["total_genes"]))
        else:
            print("⚠️ 基因库有 {} 个问题:".format(len(result["issues"])))
            for issue in result["issues"]:
                print(f"  - {issue}")
        print(
            "  标准基因: {}, 可选基因: {}".format(
                result["standard_count"], result["optional_count"]
            )
        )

    elif action == "versions":
        gene_id = sys.argv[2] if len(sys.argv) > 2 else None
        versions = bank.version_history(gene_id)
        if not versions:
            print("暂无版本记录")
            return
        print(f"\n📜 版本历史 ({len(versions)}条):")
        for v in versions[-20:]:
            detail = v.get("detail", {})
            extra = ""
            if isinstance(detail, dict):
                extra = " v{}".format(detail.get("version", "?")) if detail.get("version") else ""
                if detail.get("changes"):
                    extra += " [{}]".format(", ".join(detail["changes"]))
            print("  {}  {} · {}{}".format(v["time"][:16], v["gene_id"], v["action"], extra))

    elif action == "snapshot":
        note = sys.argv[2] if len(sys.argv) > 2 else ""
        path = bank.snapshot(note)
        print(f"📸 快照已保存: {path}")

    else:
        print_help()


if __name__ == "__main__":
    main()
