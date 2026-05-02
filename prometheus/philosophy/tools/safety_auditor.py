#!/usr/bin/env python3
"""
安全审计器

四层纵深防御审计，激活前的全面安全检查。
L1: 形体完整 → L2: 血脉纯正 → L3: 进化审阅 → L4: 力量称量
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


class SafetyAuditor:
    """四层安全审计引擎"""

    DANGEROUS_PATTERNS = [
        (r'os\.system\s*\(', "CRITICAL", "系统调用执行"),
        (r'exec\s*\(', "CRITICAL", "动态代码执行"),
        (r'eval\s*\(', "CRITICAL", "表达式求值"),
        (r'__import__\s*\(', "CRITICAL", "动态模块导入"),
        (r'subprocess\.(?:call|Popen|run)\s*\(', "HIGH", "子进程调用"),
        (r'socket\.', "HIGH", "网络套接字"),
        (r'requests\.(?:post|put|delete)', "HIGH", "外部网络请求"),
        (r'shutil\.rmtree', "HIGH", "递归删除目录"),
        (r'os\.remove\s*\(', "MEDIUM", "文件删除"),
        (r'os\.chmod\s*\(', "MEDIUM", "权限修改"),
    ]

    REQUIRED_GENES = ["G000", "G001", "G002", "G003", "G004", "G005", "G006", "G007", "G008"]

    def __init__(self, life_crest: dict = None, genealogy: dict = None,
                 skill_soul: dict = None, dna: dict = None,
                 genome_text: str = ""):
        self.life_crest = life_crest or {}
        self.genealogy = genealogy or {}
        self.skill_soul = skill_soul or {}
        self.dna = dna or {}
        self.genome_text = genome_text

    def full_audit(self) -> dict:
        """执行完整四层审计"""
        layers = {
            "L1": self._layer1_integrity(),
            "L2": self._layer2_origin(),
            "L3": self._layer3_mutation(),
            "L4": self._layer4_capability(),
        }
        risk = self._calculate_risk(layers)
        layers["risk_level"] = risk["level"]
        layers["recommendation"] = risk["action"]
        layers["passed"] = risk["level"] in ["LOW", "MEDIUM"]
        return layers

    def _layer1_integrity(self) -> dict:
        """形体完整：DNA校验码 + 关键基因存在性"""
        checks = {}

        stored = self.dna.get("checksum", "")
        checks["dna_checksum"] = {
            "passed": len(stored) == 8,
            "detail": f"DNA校验码: {stored}" if stored else "未找到校验码",
        }

        loci = self.dna.get("gene_loci", [])
        present = [g["locus"][:4] for g in loci if "locus" in g]
        missing = [g for g in self.REQUIRED_GENES if g not in present]
        checks["critical_genes"] = {
            "passed": len(missing) == 0,
            "detail": f"缺失基因: {missing}" if missing else f"全部{len(self.REQUIRED_GENES)}个基因位点存在",
        }

        all_pass = all(c["passed"] for c in checks.values())
        return {"layer": 1, "name": "形体完整", "passed": all_pass, "checks": checks}

    def _layer2_origin(self) -> dict:
        """血脉纯正：族谱连续性 + 始祖可追溯性"""
        checks = {}
        ancestors = self.genealogy.get("ancestors", [])
        parent = self.genealogy.get("parent")
        life_id = self.life_crest.get("life_id", "")

        if parent or ancestors:
            checks["ancestry_chain"] = {
                "passed": len(ancestors) > 0 or parent is not None,
                "detail": f"血脉深度: {len(ancestors) + 1}代",
            }
        else:
            checks["ancestry_chain"] = {
                "passed": True,
                "detail": "始祖之种——无血脉链需验证",
            }

        checks["origin_traceable"] = {
            "passed": "TTG@L1-G1-ORIGIN" in life_id
                      or "TTG@L1" in str(ancestors)
                      or not parent,
            "detail": "可追溯至始祖" if not parent else f"上一代: {parent}",
        }

        all_pass = all(c["passed"] for c in checks.values())
        return {"layer": 2, "name": "血脉纯正", "passed": all_pass, "checks": checks}

    def _layer3_mutation(self) -> dict:
        """进化审阅：immutable基因 + 危险代码模式"""
        checks = {}
        violations = []

        for gene in self.dna.get("gene_loci", []):
            immutable = gene.get("immutable", "")
            if "G007" in gene.get("locus", "") and "default_dormant" not in immutable:
                violations.append(f"{gene.get('locus','?')}: 休眠守卫不可变核心被修改")
            if "G008" in gene.get("locus", "") and "four_layer" not in immutable:
                violations.append(f"{gene.get('locus','?')}: 审计器四层框架被修改")

        checks["immutable_violations"] = {
            "passed": len(violations) == 0,
            "detail": "所有不可变基因完好" if not violations else f"违规: {violations}",
        }

        dangerous_found = []
        for pattern, severity, desc in self.DANGEROUS_PATTERNS:
            matches = re.findall(pattern, self.genome_text)
            if matches:
                dangerous_found.append({"pattern": desc, "severity": severity, "count": len(matches)})

        checks["dangerous_code"] = {
            "passed": not any(d["severity"] == "CRITICAL" for d in dangerous_found),
            "detail": f"发现{len(dangerous_found)}种需关注模式" if dangerous_found else "未发现危险模式",
            "findings": dangerous_found,
        }

        all_pass = all(c["passed"] for c in checks.values())
        return {"layer": 3, "name": "进化审阅", "passed": all_pass, "checks": checks}

    def _layer4_capability(self) -> dict:
        """力量称量：导入模块分类 + 影响范围"""
        checks = {}
        imports = re.findall(r'^import\s+(\S+)|^from\s+(\S+)\s+import', self.genome_text, re.MULTILINE)
        all_imports = [i[0] or i[1] for i in imports]

        safe = {"os.path", "json", "yaml", "hashlib", "datetime", "re", "pathlib", "typing"}
        moderate = {"os", "sys", "subprocess", "shutil"}
        dangerous = {"socket", "requests", "http", "urllib"}

        cmap = {"safe": [], "moderate": [], "dangerous": []}
        for imp in set(all_imports):
            if imp in dangerous:
                cmap["dangerous"].append(imp)
            elif imp in moderate:
                cmap["moderate"].append(imp)
            else:
                cmap["safe"].append(imp)

        checks["capability"] = {
            "passed": len(cmap["dangerous"]) == 0,
            "detail": f"安全:{len(cmap['safe'])} 中等:{len(cmap['moderate'])} 危险:{len(cmap['dangerous'])}",
            "map": cmap,
        }

        has_file_write = "write" in self.genome_text.lower() or "open(" in self.genome_text.lower()
        has_network = len(cmap["dangerous"]) > 0
        scope = "self_only" if not has_file_write else "skills_dir"
        if has_network:
            scope = "network"

        checks["scope"] = {
            "passed": scope != "network",
            "detail": f"影响范围: {scope}",
        }

        all_pass = all(c["passed"] for c in checks.values())
        return {"layer": 4, "name": "力量称量", "passed": all_pass, "checks": checks}

    def _calculate_risk(self, layers: dict) -> dict:
        failed = [k for k, v in layers.items()
                   if isinstance(v, dict) and not v.get("passed", True) and k.startswith("L")]

        has_critical = "CRITICAL" in str(layers)
        has_immutable_violation = any(
            "immutable" in str(layers.get(l, {})) and not layers.get(l, {}).get("passed", True)
            for l in failed
        )

        if has_critical or has_immutable_violation:
            return {"level": "CRITICAL", "action": "⛔ 阻止激活。种子可能已被污染。", "color": "black"}

        if len(failed) >= 2:
            return {"level": "HIGH", "action": "🔴 强烈建议不激活。", "color": "red"}

        if len(failed) == 1:
            return {"level": "MEDIUM", "action": "⚠️ 展示审计报告，培育者确认后激活。", "color": "yellow"}

        return {"level": "LOW", "action": "✅ 审计通过。可以安全浇水激活。", "color": "green"}

    def generate_report(self, audit_result: dict, identity: dict) -> str:
        L1 = "✅" if audit_result.get("L1", {}).get("passed") else "❌"
        L2 = "✅" if audit_result.get("L2", {}).get("passed") else "❌"
        L3 = "✅" if audit_result.get("L3", {}).get("passed") else "❌"
        L4 = "✅" if audit_result.get("L4", {}).get("passed") else "❌"
        risk = audit_result.get("risk_level", "UNKNOWN")
        icons = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴", "CRITICAL": "⛔"}
        icon = icons.get(risk, "❓")

        return f"""
╔══════════════════════════════════════════════════╗
║     🔍 种子安全审计报告                         ║
╠══════════════════════════════════════════════════╣
║  种子:   {identity.get('life_id', 'unknown')}
║  圣名:   {identity.get('sacred_name', 'unknown')}
║  谱系:   L{identity.get('lineage', '?')} G{identity.get('generation', '?')}
║                                                  ║
║  第1层·形体完整:  {L1}                             ║
║  第2层·血脉纯正:  {L2}                             ║
║  第3层·进化审阅:  {L3}                             ║
║  第4层·力量称量:  {L4}                             ║
║                                                  ║
║  综合风险: {icon} {risk}                            ║
║  {audit_result.get('recommendation', '')}
╚══════════════════════════════════════════════════╝
"""
