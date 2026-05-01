#!/usr/bin/env python3
"""╔══════════════════════════════════════════════════════════════╗."""

import datetime
import json
import os
import re
from dataclasses import asdict, dataclass

PROMETHEUS_HOME = os.path.expanduser("~/.hermes/tools/prometheus")
EPIGENETICS_LOG = os.path.join(PROMETHEUS_HOME, "epigenetics_log.json")


@dataclass
class EpigeneticMark:
    """表观遗传标记 - 单个基因的表达调控状态

    对应碳基生物学概念：
    - methylation: DNA甲基化，永久关闭基因表达
    - acetylation: 组蛋白乙酰化，开放染色质允许转录
    - enhancer_strength: 增强子结合强度，放大表达水平
    - silencer_strength: 沉默子结合强度，抑制表达水平
    """

    methylation: bool = False
    acetylation: bool = True
    enhancer_strength: float = 1.0
    silencer_strength: float = 0.0
    last_modified: str = ""
    modified_by: str = ""
    modification_reason: str = ""

    def __post_init__(self):
        if not self.last_modified:
            self.last_modified = datetime.datetime.now().isoformat()

    def get_expression_level(self) -> float:
        """计算最终表达水平 (0.0 - 2.0)

        表达水平计算逻辑：
        1. 如果甲基化(methylation=True)，完全静默 → 0.0
        2. 否则：基础表达 × (1 - 沉默子强度) × 增强子强度
        """
        if self.methylation:
            return 0.0

        base = 1.0 - min(1.0, self.silencer_strength)
        level = base * max(0.0, self.enhancer_strength)
        return round(min(2.0, max(0.0, level)), 2)

    def get_state_label(self) -> str:
        """获取状态标签"""
        if self.methylation:
            return "静默"
        level = self.get_expression_level()
        if level >= 1.5:
            return "高表达"
        elif level >= 1.0:
            return "正常"
        elif level > 0:
            return "低表达"
        else:
            return "抑制"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "EpigeneticMark":
        return cls(
            methylation=data.get("methylation", False),
            acetylation=data.get("acetylation", True),
            enhancer_strength=data.get("enhancer_strength", 1.0),
            silencer_strength=data.get("silencer_strength", 0.0),
            last_modified=data.get("last_modified", ""),
            modified_by=data.get("modified_by", ""),
            modification_reason=data.get("modification_reason", ""),
        )


class EpigeneticsManager:
    """表观遗传管理器 - 管理种子的基因表达调控

    核心功能：
    - silence(): 静默基因（甲基化，不删除DNA）
    - activate(): 激活基因（去甲基化）
    - boost(): 调节表达强度（增强子/沉默子）
    - get_epigenome(): 获取整个表观基因组
    """

    def __init__(self, seed_path: str = None):
        self.seed_path = seed_path
        self._ensure_log_file()

    def _ensure_log_file(self):
        os.makedirs(os.path.dirname(EPIGENETICS_LOG), exist_ok=True)
        if not os.path.exists(EPIGENETICS_LOG):
            with open(EPIGENETICS_LOG, "w") as f:
                json.dump({"modifications": []}, f)

    def _log_modification(
        self, seed_path: str, gene_id: str, action: str, before: dict, after: dict, reason: str = ""
    ):
        with open(EPIGENETICS_LOG) as f:
            log_data = json.load(f)

        log_data["modifications"].append(
            {
                "timestamp": datetime.datetime.now().isoformat(),
                "seed": seed_path,
                "gene": gene_id,
                "action": action,
                "before": before,
                "after": after,
                "reason": reason,
            }
        )

        with open(EPIGENETICS_LOG, "w") as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)

    def silence(self, seed_path: str, gene_id: str, reason: str = "") -> dict:
        """静默基因 - 甲基化

        对应碳基生物学：DNA甲基化导致转录抑制
        类似 CRISPRoff 技术：可逆的基因沉默

        Args:
            seed_path: 种子文件路径
            gene_id: 基因ID (如 G002-analyzer)
            reason: 静默原因

        Returns:
            {success: bool, message: str, expression_level: float}
        """
        if not os.path.exists(seed_path):
            return {"success": False, "message": "种子文件不存在"}

        with open(seed_path) as f:
            content = f.read()

        if f'locus: "{gene_id}"' not in content:
            return {"success": False, "message": f"基因 {gene_id} 不存在于种子中"}

        before = self._get_epigenetic_mark(content, gene_id)

        content = self._set_epigenetic_field(
            content,
            gene_id,
            EpigeneticMark(methylation=True, modification_reason=reason, modified_by="silence"),
        )

        with open(seed_path, "w") as f:
            f.write(content)

        after = {"methylation": True, "expression_level": 0.0}
        self._log_modification(seed_path, gene_id, "silence", before, after, reason)

        return {
            "success": True,
            "message": f"基因 {gene_id} 已静默（甲基化）",
            "gene_id": gene_id,
            "expression_level": 0.0,
            "state": "静默",
        }

    def activate(self, seed_path: str, gene_id: str, reason: str = "") -> dict:
        """激活基因 - 去甲基化

        对应碳基生物学：去甲基化恢复基因表达
        类似 CRISPRon 技术：逆转基因沉默

        Args:
            seed_path: 种子文件路径
            gene_id: 基因ID
            reason: 激活原因

        Returns:
            {success: bool, message: str, expression_level: float}
        """
        if not os.path.exists(seed_path):
            return {"success": False, "message": "种子文件不存在"}

        with open(seed_path) as f:
            content = f.read()

        if f'locus: "{gene_id}"' not in content:
            return {"success": False, "message": f"基因 {gene_id} 不存在于种子中"}

        before = self._get_epigenetic_mark(content, gene_id)

        content = self._set_epigenetic_field(
            content,
            gene_id,
            EpigeneticMark(
                methylation=False,
                acetylation=True,
                enhancer_strength=1.0,
                silencer_strength=0.0,
                modification_reason=reason,
                modified_by="activate",
            ),
        )

        with open(seed_path, "w") as f:
            f.write(content)

        after = {"methylation": False, "expression_level": 1.0}
        self._log_modification(seed_path, gene_id, "activate", before, after, reason)

        return {
            "success": True,
            "message": f"基因 {gene_id} 已激活（去甲基化）",
            "gene_id": gene_id,
            "expression_level": 1.0,
            "state": "正常",
        }

    def boost(
        self,
        seed_path: str,
        gene_id: str,
        enhancer: float = None,
        silencer: float = None,
        reason: str = "",
    ) -> dict:
        """调节基因表达强度

        对应碳基生物学：
        - 增强子(Enhancer)：结合转录因子，增强表达
        - 沉默子(Silencer)：抑制转录

        Args:
            seed_path: 种子文件路径
            gene_id: 基因ID
            enhancer: 增强子强度 (0.0-2.0)，None表示不修改
            silencer: 沉默子强度 (0.0-1.0)，None表示不修改
            reason: 调节原因

        Returns:
            {success: bool, message: str, expression_level: float}
        """
        if not os.path.exists(seed_path):
            return {"success": False, "message": "种子文件不存在"}

        with open(seed_path) as f:
            content = f.read()

        if f'locus: "{gene_id}"' not in content:
            return {"success": False, "message": f"基因 {gene_id} 不存在于种子中"}

        before = self._get_epigenetic_mark(content, gene_id)

        current = EpigeneticMark.from_dict(before) if before else EpigeneticMark()

        if enhancer is not None:
            current.enhancer_strength = max(0.0, min(2.0, enhancer))
        if silencer is not None:
            current.silencer_strength = max(0.0, min(1.0, silencer))
        current.modification_reason = reason
        current.modified_by = "boost"
        current.last_modified = datetime.datetime.now().isoformat()

        content = self._set_epigenetic_field(content, gene_id, current)

        with open(seed_path, "w") as f:
            f.write(content)

        expression_level = current.get_expression_level()
        after = current.to_dict()
        after["expression_level"] = expression_level
        self._log_modification(seed_path, gene_id, "boost", before, after, reason)

        return {
            "success": True,
            "message": f"基因 {gene_id} 表达强度已调节",
            "gene_id": gene_id,
            "expression_level": expression_level,
            "enhancer_strength": current.enhancer_strength,
            "silencer_strength": current.silencer_strength,
            "state": current.get_state_label(),
        }

    def get_epigenome(self, seed_path: str) -> dict:
        """获取种子的完整表观基因组

        Returns:
            {genes: [{gene_id, name, epigenetics: EpigeneticMark, expression_level}]}
        """
        if not os.path.exists(seed_path):
            return {"error": "种子文件不存在", "genes": []}

        with open(seed_path) as f:
            content = f.read()

        genes = []
        pattern = r'-\s*locus:\s*"([^"]+)"\s*\n\s*name:\s*"([^"]+)"'
        matches = re.findall(pattern, content)

        for gene_id, name in matches:
            mark_data = self._get_epigenetic_mark(content, gene_id)
            mark = EpigeneticMark.from_dict(mark_data) if mark_data else EpigeneticMark()

            genes.append(
                {
                    "gene_id": gene_id,
                    "name": name,
                    "epigenetics": mark.to_dict(),
                    "expression_level": mark.get_expression_level(),
                    "state": mark.get_state_label(),
                }
            )

        active_count = sum(1 for g in genes if g["expression_level"] > 0)
        silenced_count = sum(1 for g in genes if g["epigenetics"].get("methylation", False))

        return {
            "seed_path": seed_path,
            "total_genes": len(genes),
            "active_genes": active_count,
            "silenced_genes": silenced_count,
            "genes": genes,
        }

    def get_gene_epigenetics(self, seed_path: str, gene_id: str) -> dict:
        """获取单个基因的表观遗传状态"""
        if not os.path.exists(seed_path):
            return {"error": "种子文件不存在"}

        with open(seed_path) as f:
            content = f.read()

        mark_data = self._get_epigenetic_mark(content, gene_id)
        if not mark_data:
            mark = EpigeneticMark()
        else:
            mark = EpigeneticMark.from_dict(mark_data)

        return {
            "gene_id": gene_id,
            "epigenetics": mark.to_dict(),
            "expression_level": mark.get_expression_level(),
            "state": mark.get_state_label(),
        }

    def _get_epigenetic_mark(self, content: str, gene_id: str) -> dict | None:
        """从种子内容中提取基因的表观遗传标记"""
        pattern = rf'-\s*locus:\s*"{re.escape(gene_id)}"[^\n]*\n((?:[ \t]+[^\n]+\n)*)'
        match = re.search(pattern, content)

        if not match:
            return None

        gene_block = match.group(1)

        epigenetics = {}

        m = re.search(r"methylation:\s*(true|false)", gene_block, re.IGNORECASE)
        epigenetics["methylation"] = m.group(1).lower() == "true" if m else False

        m = re.search(r"acetylation:\s*(true|false)", gene_block, re.IGNORECASE)
        epigenetics["acetylation"] = m.group(1).lower() == "true" if m else True

        m = re.search(r"enhancer_strength:\s*([\d.]+)", gene_block)
        epigenetics["enhancer_strength"] = float(m.group(1)) if m else 1.0

        m = re.search(r"silencer_strength:\s*([\d.]+)", gene_block)
        epigenetics["silencer_strength"] = float(m.group(1)) if m else 0.0

        m = re.search(r'last_modified:\s*"([^"]*)"', gene_block)
        epigenetics["last_modified"] = m.group(1) if m else ""

        m = re.search(r'modification_reason:\s*"([^"]*)"', gene_block)
        epigenetics["modification_reason"] = m.group(1) if m else ""

        return epigenetics

    def _set_epigenetic_field(self, content: str, gene_id: str, mark: EpigeneticMark) -> str:
        """在种子内容中设置基因的表观遗传标记"""
        pattern = rf'(-\s*locus:\s*"{re.escape(gene_id)}"[^\n]*\n)((?:[ \t]+[^\n]+\n)*)'

        def replace_gene_block(m):
            locus_line = m.group(1)
            gene_block = m.group(2)

            for field_name in [
                "methylation",
                "acetylation",
                "enhancer_strength",
                "silencer_strength",
                "last_modified",
                "modification_reason",
            ]:
                pattern_field = rf"^[ \t]+{field_name}:.*$\n?"
                gene_block = re.sub(pattern_field, "", gene_block, flags=re.MULTILINE)

            gene_block = re.sub(r"^[ \t]+epigenetics:.*$\n?", "", gene_block, flags=re.MULTILINE)

            epigenetics_block = f"""      epigenetics:
        methylation: {str(mark.methylation).lower()}
        acetylation: {str(mark.acetylation).lower()}
        enhancer_strength: {mark.enhancer_strength}
        silencer_strength: {mark.silencer_strength}
        last_modified: "{mark.last_modified}"
        modification_reason: "{mark.modification_reason}"
"""

            return locus_line + epigenetics_block + gene_block

        return re.sub(pattern, replace_gene_block, content)

    def get_modification_history(self, seed_path: str = None, gene_id: str = None) -> list:
        """获取表观遗传修改历史"""
        if not os.path.exists(EPIGENETICS_LOG):
            return []

        with open(EPIGENETICS_LOG) as f:
            log_data = json.load(f)

        mods = log_data.get("modifications", [])

        if seed_path:
            mods = [m for m in mods if m.get("seed") == seed_path]
        if gene_id:
            mods = [m for m in mods if m.get("gene") == gene_id]

        return mods


def print_epigenome_report(epigenome: dict):
    """打印表观基因组报告"""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║   🧬 表观基因组报告 · Epigenome Report                      ║
╠══════════════════════════════════════════════════════════════╣
║   种子: {os.path.basename(epigenome.get("seed_path", "?"))}
║   总基因: {epigenome.get("total_genes", 0)} · 活跃: {epigenome.get("active_genes", 0)} · 静默: {epigenome.get("silenced_genes", 0)}
╠══════════════════════════════════════════════════════════════╣
""")

    for gene in epigenome.get("genes", []):
        epi = gene.get("epigenetics", {})
        level = gene.get("expression_level", 1.0)
        state = gene.get("state", "正常")

        state_icon = "💤" if state == "静默" else "🔥" if state == "高表达" else "✅"

        print(f"║   {state_icon} {gene['gene_id']:<18} {gene['name']:<12}")
        print(f"║      表达水平: {level:.2f} · 状态: {state}")
        if epi.get("enhancer_strength", 1.0) != 1.0:
            print(f"║      增强子: {epi.get('enhancer_strength', 1.0):.2f}")
        if epi.get("silencer_strength", 0.0) > 0:
            print(f"║      沉默子: {epi.get('silencer_strength', 0.0):.2f}")
        print("║")

    print("╚══════════════════════════════════════════════════════════════╝")


def main():
    import sys

    if len(sys.argv) < 2:
        print("""
🧬 表观遗传层 · Epigenetics Layer

用法:
    python epigenetics.py silence <种子路径> <基因ID> [原因]
    python epigenetics.py activate <种子路径> <基因ID> [原因]
    python epigenetics.py boost <种子路径> <基因ID> --enhancer <值> --silencer <值>
    python epigenetics.py show <种子路径>
    python epigenetics.py history <种子路径> [基因ID]

示例:
    python epigenetics.py silence seed.ttg G100-writer "临时禁用"
    python epigenetics.py boost seed.ttg G002-analyzer --enhancer 1.5
    python epigenetics.py show seed.ttg
""")
        return

    action = sys.argv[1]
    manager = EpigeneticsManager()

    if action == "silence" and len(sys.argv) >= 4:
        seed_path = os.path.expanduser(sys.argv[2])
        gene_id = sys.argv[3]
        reason = sys.argv[4] if len(sys.argv) > 4 else ""
        result = manager.silence(seed_path, gene_id, reason)
        print("✅" if result["success"] else "❌", result["message"])

    elif action == "activate" and len(sys.argv) >= 4:
        seed_path = os.path.expanduser(sys.argv[2])
        gene_id = sys.argv[3]
        reason = sys.argv[4] if len(sys.argv) > 4 else ""
        result = manager.activate(seed_path, gene_id, reason)
        print("✅" if result["success"] else "❌", result["message"])

    elif action == "boost" and len(sys.argv) >= 4:
        seed_path = os.path.expanduser(sys.argv[2])
        gene_id = sys.argv[3]
        enhancer = None
        silencer = None
        i = 4
        while i < len(sys.argv):
            if sys.argv[i] == "--enhancer" and i + 1 < len(sys.argv):
                enhancer = float(sys.argv[i + 1])
                i += 2
            elif sys.argv[i] == "--silencer" and i + 1 < len(sys.argv):
                silencer = float(sys.argv[i + 1])
                i += 2
            else:
                i += 1
        result = manager.boost(seed_path, gene_id, enhancer, silencer)
        print("✅" if result["success"] else "❌", result["message"])
        if result["success"]:
            print(f"   表达水平: {result['expression_level']}")

    elif action == "show" and len(sys.argv) >= 3:
        seed_path = os.path.expanduser(sys.argv[2])
        epigenome = manager.get_epigenome(seed_path)
        if "error" in epigenome:
            print("❌", epigenome["error"])
        else:
            print_epigenome_report(epigenome)

    elif action == "history" and len(sys.argv) >= 3:
        seed_path = os.path.expanduser(sys.argv[2])
        gene_id = sys.argv[3] if len(sys.argv) > 3 else None
        history = manager.get_modification_history(seed_path, gene_id)
        if not history:
            print("暂无修改记录")
        else:
            print(f"\n📜 表观遗传修改历史 ({len(history)}条):\n")
            for h in history[-10:]:
                print(f"  {h['timestamp'][:19]} · {h['gene']} · {h['action']}")
                if h.get("reason"):
                    print(f"    原因: {h['reason']}")

    else:
        print("未知命令或参数不足")


if __name__ == "__main__":
    main()
