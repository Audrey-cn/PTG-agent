#!/usr/bin/env python3
"""╔══════════════════════════════════════════════════════════════╗."""

import json
import os
import re
from pathlib import Path


class GeneLibrary:
    """基因库 - 种群基因的存储与检索

    对应碳基生物学：种群基因库(Gene Pool)
    存储一个物种/种群中所有可用的等位基因

    功能：
    - 管理标准基因（G001-G008）
    - 管理可选基因（G100+）
    - 管理叙事基因（G000 创始印记，已融入族谱系统）
    """

    def __init__(self):
        self.catalog_path = self._find_catalog_path()
        self.catalog = self._load_catalog()

    def _find_catalog_path(self) -> str:
        user_path = os.path.expanduser("~/.prometheus/tools/prometheus/genes/gene_catalog.json")
        if os.path.exists(user_path):
            return user_path
        
        project_path = Path(__file__).parent / "gene_catalog.json"
        if project_path.exists():
            return str(project_path)
        
        return user_path

    def _load_catalog(self) -> dict:
        if os.path.exists(self.catalog_path):
            with open(self.catalog_path) as f:
                return json.load(f)
        return {"standard": {}, "optional": [], "narrative": {}}

    def list_standard(self) -> list:
        """列出标准基因（八大核心基因）"""
        return list(self.catalog.get("standard", {}).values())

    def list_optional(self) -> list:
        """列出可选基因（扩展能力）"""
        return self.catalog.get("optional", [])

    def list_narrative(self) -> list:
        """列出叙事基因（族谱谱系系统）

        注意：族谱谱系板块保持史诗型编码叙事风格
        G000 创始印记已融入族谱叙事系统
        """
        return list(self.catalog.get("narrative", {}).values())

    def find_gene(self, gene_id: str) -> dict | None:
        """查找基因定义"""
        std = self.catalog.get("standard", {})
        if gene_id in std:
            return std[gene_id]
        for opt in self.catalog.get("optional", []):
            if opt.get("gene_id") == gene_id:
                return opt
        return None

    def add_optional_gene(self, gene_def: dict):
        """添加可选基因到基因库"""
        if "optional" not in self.catalog:
            self.catalog["optional"] = []
        self.catalog["optional"].append(gene_def)
        with open(self.catalog_path, "w") as f:
            json.dump(self.catalog, f, ensure_ascii=False, indent=2)


class GeneHealthAuditor:
    """基因健康度审计器 - 基因组完整性检查

    对应碳基生物学：DNA损伤检测机制
    类似于错配修复(MMR)系统识别基因组异常

    审计维度：
    - 完整性(Completeness)：必需基因是否齐全
    - 碳基完整性(Carbon Integrity)：创始铭刻是否完整
    - 兼容性(Compatibility)：基因间是否存在冲突
    - 突变边界(Mutation Boundary)：变异是否越界
    - 冗余检查(Redundancy)：是否存在重复功能
    """

    def __init__(self, gene_library: GeneLibrary = None):
        self.library = gene_library or GeneLibrary()

    def audit_seed(self, seed_data: dict) -> dict:
        """对种子进行完整健康度审计

        对应碳基生物学：全基因组扫描
        """
        dna = (
            seed_data.get("dna_encoding", {})
            if isinstance(seed_data.get("dna_encoding"), dict)
            else {}
        )
        loci = dna.get("gene_loci", []) if dna else []

        results = {
            "completeness": self._check_completeness(loci),
            "carbon_integrity": self._check_carbon(loci, seed_data),
            "compatibility": self._check_internal_compatibility(loci),
            "mutation_boundary": self._check_mutation_boundaries(loci),
            "redundancy": self._check_redundancy(loci),
            "health_score": 0,
        }

        scores = [
            100 if results["completeness"]["passed"] else 30,
            100 if results["carbon_integrity"]["passed"] else 0,
            100 if results["compatibility"]["passed"] else 50,
            80 if results["mutation_boundary"]["passed"] else 40,
            100 if not results["redundancy"]["redundant_pairs"] else 60,
        ]
        results["health_score"] = round(sum(scores) / len(scores), 1)

        return results

    def _check_completeness(self, loci: list) -> dict:
        """检查基因完整性

        对应碳基生物学：必需基因检测
        八大标准基因（G001-G008）必须存在
        G000 创始印记已融入族谱叙事系统，不再作为功能基因位点
        """
        required = ["G001", "G002", "G003", "G004", "G005", "G006", "G007", "G008"]
        present = [l.get("locus", "")[:4] for l in loci if "locus" in l]
        missing = [g for g in required if g not in present]
        extra = [p for p in present if p not in required]

        return {
            "passed": len(missing) == 0,
            "required": required,
            "present": present,
            "missing": missing,
            "extra": extra,
            "score": f"{len(present)}/{len(required)}",
            "summary": "完整" if not missing else f"缺失: {missing}",
        }

    def _check_carbon(self, loci: list, seed_data: dict) -> dict:
        """检查创始铭刻完整性

        对应碳基生物学：线粒体DNA完整性检测
        创始铭刻如同线粒体DNA，母系遗传，永恒不变

        注意：族谱谱系板块保持史诗型编码叙事风格
        """
        issues = []

        founder = seed_data.get("life_crest", {}).get("founder_chronicle", {})
        genea = seed_data.get("genealogy_codex", {})

        has_founder = bool(founder and founder.get("tags"))
        has_ttg_markers = bool(
            genea.get("lineage_laws") or genea.get("bloodline_registry") or genea.get("tag_lexicon")
        )

        if has_founder:
            required_tags = [
                "audrey_001x",
                "transcend_binary",
                "human_genesis",
                "divine_parallel",
                "form_sovereignty",
                "eternal_mark",
                "carbon_covenant",
                "promethean_gift",
                "engineer_craft",
                "open_source",
            ]
            missing = [t for t in required_tags if t not in founder.get("tags", [])]
            if missing:
                issues.append(f"创始标签缺失: {missing}")
        elif has_ttg_markers:
            issues.append("疑似基因篡改：存在族谱结构但创始印记缺失")
        else:
            issues.append("外来种子：无族谱结构，无创始印记")

        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "summary": "铭刻完整" if not issues else f"{len(issues)}个问题",
        }

    def _check_internal_compatibility(self, loci: list) -> dict:
        """检查基因间兼容性

        对应碳基生物学：基因互作网络分析
        检测基因间的依赖关系是否满足
        """
        conflicts = []
        present_genes = [l.get("locus", "")[:4] for l in loci]

        if "G004" in present_genes and "G001" not in present_genes:
            conflicts.append("G004打包器依赖G001解析器，但G001缺失")

        if "G005" in present_genes and "G001" not in present_genes:
            conflicts.append("G005族谱学者依赖G001解析器")

        if "G006" in present_genes and "G001" not in present_genes:
            conflicts.append("G006自管理者依赖G001解析器")

        if "G008" in present_genes and "G007" not in present_genes:
            conflicts.append("G008审计器应在G007休眠守卫之后激活")

        return {
            "passed": len(conflicts) == 0,
            "conflicts": conflicts,
            "summary": "兼容" if not conflicts else f"{len(conflicts)}个冲突",
        }

    def _check_mutation_boundaries(self, loci: list) -> dict:
        """检查突变边界

        对应碳基生物学：突变边界检测
        确保变异不侵犯不可变核心
        """
        violations = []

        for l in loci:
            locus_id = l.get("locus", "?")
            mutable = l.get("mutable_range", "")
            immutable_raw = l.get("immutable", "")

            for imm in immutable_raw.split(","):
                imm = imm.strip()
                if imm and imm in mutable:
                    violations.append(f"{locus_id}: 不可变字段'{imm}'出现在可变范围中")

        return {
            "passed": len(violations) == 0,
            "violations": violations,
            "summary": "边界清晰" if not violations else f"{len(violations)}个越界",
        }

    def _check_redundancy(self, loci: list) -> dict:
        """检查基因冗余

        对应碳基生物学：基因重复检测
        识别功能重叠的基因对
        """
        pairs = []
        gene_names = [(l.get("locus", ""), l.get("name", "")) for l in loci]

        for i, (id1, n1) in enumerate(gene_names):
            for id2, n2 in gene_names[i + 1 :]:
                common_words = set(n1.replace("器", "").replace("者", "").split()) & set(
                    n2.replace("器", "").replace("者", "").split()
                )
                if common_words and len(common_words) >= 2:
                    pairs.append(
                        {
                            "gene_a": id1,
                            "gene_b": id2,
                            "common_keywords": list(common_words),
                            "suggestion": f"考虑合并{id1}和{id2}",
                        }
                    )

        return {
            "redundant_pairs": pairs,
            "summary": "无冗余" if not pairs else f"{len(pairs)}对可能冗余",
        }


class GeneFusionAnalyzer:
    """基因融合分析器 - 评估两套基因的融合可行性

    对应碳基生物学：同源重组分析
    评估两个基因组是否可以安全重组

    功能：
    - 分析基因重叠与冲突
    - 评估融合可行性
    - 推荐可选基因
    """

    def __init__(self, gene_library: GeneLibrary = None):
        self.library = gene_library or GeneLibrary()

    def analyze_fusion(
        self, genes_a: list, genes_b: list, name_a: str = "种子A", name_b: str = "种子B"
    ) -> dict:
        """分析两套基因融合的可行性

        对应碳基生物学：同源重组可行性评估
        """
        ids_a = {l.get("locus", "") for l in genes_a if "locus" in l}
        ids_b = {l.get("locus", "") for l in genes_b if "locus" in l}

        overlap = ids_a & ids_b
        unique_a = ids_a - ids_b
        unique_b = ids_b - ids_a

        conflict_details = []
        for gene_id in overlap:
            gene_a = next((l for l in genes_a if l.get("locus") == gene_id), {})
            gene_b = next((l for l in genes_b if l.get("locus") == gene_id), {})

            imm_a = set(gene_a.get("immutable", "").split(","))
            imm_b = set(gene_b.get("immutable", "").split(","))

            if imm_a != imm_b:
                conflict_details.append(
                    {
                        "gene": gene_id,
                        "issue": "不可变核心不一致",
                        "a_immutable": list(imm_a),
                        "b_immutable": list(imm_b),
                        "resolution": "以碳基级别更高者为准，或保留两者为不同变种",
                    }
                )

        carbon_a = {l.get("locus") for l in genes_a if l.get("carbon_bonded")}
        carbon_b = {l.get("locus") for l in genes_b if l.get("carbon_bonded")}

        if not overlap:
            feasibility = "HIGH"
            recommendation = "无基因冲突，可安全融合。建议直接合并基因位点。"
        elif all(c.get("resolution") for c in conflict_details):
            feasibility = "MEDIUM"
            recommendation = "存在重叠基因但可解决。建议创建融合变种，记录融合决策。"
        else:
            feasibility = "LOW"
            recommendation = "存在不可调和冲突。建议保持两个独立谱系，用G006自管理者建立协作关系。"

        return {
            "name_a": name_a,
            "name_b": name_b,
            "genes_a": list(ids_a),
            "genes_b": list(ids_b),
            "shared_genes": list(overlap),
            "unique_to_a": list(unique_a),
            "unique_to_b": list(unique_b),
            "conflicts": conflict_details,
            "carbon_genes_a": list(carbon_a),
            "carbon_genes_b": list(carbon_b),
            "feasibility": feasibility,
            "recommendation": recommendation,
            "fusion_score": 100 if feasibility == "HIGH" else 60 if feasibility == "MEDIUM" else 20,
        }

    def suggest_optional_genes(self, current_genes: list) -> list:
        """根据当前基因组推荐可添加的基因

        对应碳基生物学：适应性基因推荐
        """
        current_ids = {l.get("locus", "")[:4] for l in current_genes if "locus" in l}
        suggestions = []

        for opt in self.library.list_optional():
            gene_id = opt.get("gene_id", "")
            compatible_with = opt.get("compatible_with", [])

            short_id = gene_id[:4]
            if short_id in current_ids:
                continue

            if compatible_with:
                if all(c in current_ids for c in compatible_with):
                    suggestions.append(opt)
            else:
                suggestions.append(opt)

        return suggestions


class ForeignGeneExtractor:
    """外来基因拆解器 - 分析外部技能/框架，提取基因片段

    对应碳基生物学：水平基因转移检测
    识别外来遗传物质并评估整合可行性

    功能：
    - 从Markdown文件提取能力特征
    - 分析依赖关系
    - 建议基因映射
    """

    @staticmethod
    def extract_from_markdown(md_path: str) -> dict:
        """从Markdown文件中提取潜在基因

        对应碳基生物学：外源基因识别
        """
        if not os.path.exists(md_path):
            return {"error": f"文件不存在: {md_path}"}

        with open(md_path, encoding="utf-8") as f:
            content = f.read()

        sections = re.findall(r"^##\s+(.+)$", content, re.MULTILINE)
        yaml_blocks = re.findall(r"```yaml\s*\n(.*?)```", content, re.DOTALL)
        python_blocks = re.findall(r"```python\s*\n(.*?)```", content, re.DOTALL)

        capabilities = ForeignGeneExtractor._extract_capabilities(content)
        dependencies = ForeignGeneExtractor._extract_dependencies(content)
        category = ForeignGeneExtractor._classify_skill(content)

        return {
            "source": md_path,
            "file_name": os.path.basename(md_path),
            "size": len(content),
            "sections_count": len(sections),
            "yaml_blocks": len(yaml_blocks),
            "python_blocks": len(python_blocks),
            "detected_capabilities": capabilities,
            "dependencies": dependencies,
            "category": category,
            "suggested_genes": ForeignGeneExtractor._suggest_genes(capabilities, category),
            "compatibility_note": ForeignGeneExtractor._compatibility_note(capabilities),
        }

    @staticmethod
    def _extract_capabilities(content: str) -> list:
        """从内容中提取能力关键词"""
        capability_patterns = [
            (r"(?:解析|parse|extract)", "数据解析"),
            (r"(?:生成|generate|create)", "内容生成"),
            (r"(?:验证|validate|check|verify)", "验证检查"),
            (r"(?:存储|store|save|persist)", "持久存储"),
            (r"(?:搜索|search|find|query)", "搜索查询"),
            (r"(?:网络|http|request|api)", "网络通信"),
            (r"(?:审计|audit|security|safety)", "安全审计"),
            (r"(?:生长|grow|cultivat)", "生长培育"),
            (r"(?:族谱|genealog|lineage)", "族谱管理"),
            (r"(?:压缩|compress|encode|decode)", "编码解码"),
            (r"(?:图片|image|visual|vision)", "视觉处理"),
            (r"(?:协作|collab|team|multi)", "协作能力"),
        ]

        found = []
        for pattern, name in capability_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                found.append(name)

        return list(set(found))

    @staticmethod
    def _extract_dependencies(content: str) -> list:
        """提取依赖"""
        imports = re.findall(r"^import\s+(\S+)|^from\s+(\S+)\s+import", content, re.MULTILINE)
        all_imports = list(set([i[0] or i[1] for i in imports]))

        safe = ["json", "yaml", "hashlib", "datetime", "re", "os.path", "pathlib"]
        external = [i for i in all_imports if i not in safe and "." not in i]

        return {
            "total": len(all_imports),
            "external": external,
            "has_network": any(i in external for i in ["requests", "http", "socket", "urllib"]),
            "has_system": any(i in ["os", "subprocess", "sys"] for i in external),
        }

    @staticmethod
    def _classify_skill(content: str) -> str:
        """分类技能类型"""
        if re.search(r"ttg|seed|种子|teach.to.grow", content, re.IGNORECASE):
            return "TTG种子"
        if re.search(r"writing|writer|写作|文章", content, re.IGNORECASE):
            return "创作工具"
        if re.search(r"audit|security|安全|审计", content, re.IGNORECASE):
            return "安全工具"
        if re.search(r"parse|extract|解析|提取", content, re.IGNORECASE):
            return "数据处理"
        return "通用工具"

    @staticmethod
    def _suggest_genes(capabilities: list, category: str) -> list:
        """根据分析建议基因片段"""
        suggestions = []

        cap_to_gene = {
            "数据解析": "G001-parser",
            "验证检查": "G008-auditor",
            "持久存储": "G300-memory",
            "搜索查询": "G001-parser",
            "安全审计": "G008-auditor",
            "生长培育": "G003-tracker",
            "族谱管理": "G005-genealogist",
            "编码解码": "G005-genealogist",
            "协作能力": "G400-team",
            "视觉处理": "G101-vision",
            "内容生成": "G100-writer",
        }

        for cap in capabilities:
            if cap in cap_to_gene:
                suggestions.append(
                    {
                        "from_capability": cap,
                        "suggested_gene": cap_to_gene[cap],
                        "action": "insert"
                        if cap_to_gene[cap].startswith("G1") or cap_to_gene[cap].startswith("G2")
                        else "consider",
                    }
                )

        return suggestions

    @staticmethod
    def _compatibility_note(capabilities: list) -> str:
        """生成兼容性说明"""
        notes = []
        if "网络通信" in capabilities:
            notes.append("包含网络能力——建议作为G200系列可选基因")
        if "安全审计" in capabilities:
            notes.append("自带安全审计——与G008兼容")
        if "协作能力" in capabilities:
            notes.append("协作能力——建议配合G006自管理者")
        return "; ".join(notes) if notes else "未检测到特殊兼容性需求"


def print_gene_health_report(audit_result: dict):
    """打印基因健康度报告"""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║   🩺 基因健康度审计报告 · Health Audit Report               ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║   综合健康分: {audit_result["health_score"]}/100
║                                                              ║
║   完整性:   {"✅" if audit_result["completeness"]["passed"] else "❌"} {audit_result["completeness"]["summary"]}
║   碳基保护: {"✅" if audit_result["carbon_integrity"]["passed"] else "❌"} {audit_result["carbon_integrity"]["summary"]}
║   兼容性:   {"✅" if audit_result["compatibility"]["passed"] else "⚠️"} {audit_result["compatibility"]["summary"]}
║   突变边界: {"✅" if audit_result["mutation_boundary"]["passed"] else "❌"} {audit_result["mutation_boundary"]["summary"]}
║   冗余检查: {"✅" if not audit_result["redundancy"]["redundant_pairs"] else "⚠️"} {audit_result["redundancy"]["summary"]}
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")


def print_fusion_report(fusion: dict):
    """打印基因融合报告"""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║   🔀 基因融合分析报告 · Fusion Analysis Report               ║
╠══════════════════════════════════════════════════════════════╣
║   {fusion["name_a"]} ↔ {fusion["name_b"]}
║                                                              ║
║   共同基因: {len(fusion["shared_genes"])}个
║   A独有:   {len(fusion["unique_to_a"])}个
║   B独有:   {len(fusion["unique_to_b"])}个
║                                                              ║
║   可行性: {"🟢 HIGH" if fusion["feasibility"] == "HIGH" else "🟡 MEDIUM" if fusion["feasibility"] == "MEDIUM" else "🔴 LOW"}
║   融合分: {fusion["fusion_score"]}/100
║                                                              ║
║   {fusion["recommendation"]}
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")


def print_extraction_report(extraction: dict):
    """打印外来基因拆解报告"""
    caps = extraction.get("detected_capabilities", [])
    deps = extraction.get("dependencies", {})
    suggestions = extraction.get("suggested_genes", [])

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║   🔬 外来基因拆解报告 · Gene Extraction Report              ║
╠══════════════════════════════════════════════════════════════╣
║   文件: {extraction["file_name"]}
║   大小: {extraction["size"]}B · 章节: {extraction["sections_count"]} · 代码块: {extraction["python_blocks"]}
║   分类: {extraction["category"]}
║                                                              ║
║   检测能力 ({len(caps)}):
""")
    for c in caps:
        print(f"║     · {c}")

    print(f"""║                                                              ║
║   依赖分析:
║     总导入: {deps.get("total", 0)} · 外部: {deps.get("external", [])}
║     网络: {"⚠️ 有" if deps.get("has_network") else "✅ 无"} · 系统调用: {"⚠️ 有" if deps.get("has_system") else "✅ 无"}
║                                                              ║
║   建议基因 ({len(suggestions)}):
""")
    for s in suggestions:
        action = "插入" if s.get("action") == "insert" else "参考"
        print(f"║     [{action}] {s.get('suggested_gene', '?')} ← {s.get('from_capability', '?')}")

    print(f"""║                                                              ║
║   兼容性: {extraction.get("compatibility_note", "无")}
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")


def main():
    import sys

    if len(sys.argv) < 2:
        print("""
🧬 基因分析器 · Gene Analyzer

用法:
  analyzer.py health <种子.ttg>       基因健康度审计
  analyzer.py fusion <A.ttg> <B.ttg>  基因融合分析
  analyzer.py extract <Skill.md>      外来基因拆解
  analyzer.py library                 查看基因库
  analyzer.py suggest <种子.ttg>      推荐可选基因
""")
        return

    action = sys.argv[1]

    if action == "health" and len(sys.argv) > 2:
        from prometheus import load_seed

        data = load_seed(sys.argv[2])
        if data:
            auditor = GeneHealthAuditor()
            result = auditor.audit_seed(data)
            print_gene_health_report(result)

    elif action == "fusion" and len(sys.argv) > 3:
        from prometheus import load_seed

        data_a = load_seed(sys.argv[2])
        data_b = load_seed(sys.argv[3])
        if data_a and data_b:
            genes_a = (
                data_a.get("dna_encoding", {}).get("gene_loci", [])
                if isinstance(data_a.get("dna_encoding"), dict)
                else []
            )
            genes_b = (
                data_b.get("dna_encoding", {}).get("gene_loci", [])
                if isinstance(data_b.get("dna_encoding"), dict)
                else []
            )
            analyzer = GeneFusionAnalyzer()
            result = analyzer.analyze_fusion(
                genes_a, genes_b, os.path.basename(sys.argv[2]), os.path.basename(sys.argv[3])
            )
            print_fusion_report(result)

    elif action == "extract" and len(sys.argv) > 2:
        result = ForeignGeneExtractor.extract_from_markdown(sys.argv[2])
        print_extraction_report(result)

    elif action == "library":
        lib = GeneLibrary()
        print("\n🧬 标准基因库 (Standard Genes):")
        for g in lib.list_standard():
            print(f"  {g.get('gene_id', '?')} · {g.get('name', '?')}")
            print(f"    类别: {g.get('category', '?')} · {g.get('description', '?')[:60]}")

        print("\n📜 叙事基因 (Narrative Genes - 族谱谱系系统):")
        for g in lib.list_narrative():
            print(f"  {g.get('gene_id', '?')} · {g.get('name', '?')}")
            print(f"    存储: {g.get('storage', '?')}")
            print(f"    解码: {g.get('decode', '?')}")

        print("\n🧬 可选基因 (Optional Genes):")
        for g in lib.list_optional():
            print(f"  {g.get('gene_id', '?')} · {g.get('name', '?')}")
            print(f"    类别: {g.get('category', '?')} · 兼容: {g.get('compatible_with', [])}")

    elif action == "suggest" and len(sys.argv) > 2:
        from prometheus import load_seed

        data = load_seed(sys.argv[2])
        if data:
            genes = (
                data.get("dna_encoding", {}).get("gene_loci", [])
                if isinstance(data.get("dna_encoding"), dict)
                else []
            )
            analyzer = GeneFusionAnalyzer()
            suggestions = analyzer.suggest_optional_genes(genes)
            print(f"\n💡 推荐添加的基因 ({len(suggestions)}个):")
            for s in suggestions:
                print(f"  [{s.get('gene_id', '?')}] {s.get('name', '?')}")
                print(f"    类别: {s.get('category', '?')} · {s.get('description', '?')[:60]}")
                safety = s.get("safety_note", "")
                if safety:
                    print(f"    {safety}")


if __name__ == "__main__":
    main()
