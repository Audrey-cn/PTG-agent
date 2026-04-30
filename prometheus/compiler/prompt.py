#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║   📝 普罗米修斯 · 提示词合成器 · Prompt Composer            ║
║                                                              ║
║   读取种子的 DNA，编译为可用的 system prompt。               ║
║                                                              ║
║   设计哲学：                                                 ║
║     种子的 DNA 包含原则、禁忌、气质——这是"蓝图"。          ║
║     提示词合成器是"编译器"——把蓝图变成运行时指令。          ║
║                                                              ║
║   编译流水线：                                               ║
║     种子 DNA → 解析 → 分段 → 注入 → 编译 → system prompt    ║
║                                                              ║
║   Prometheus 作为独立 Agent 使用此模块来：                   ║
║     1. 理解一个种子的身份和能力                              ║
║     2. 将其转化为 LLM 可理解的 system prompt                 ║
║     3. 支持按场景切换人格风格                                ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import re
from typing import Dict, List, Optional, Any
from enum import Enum


# ═══════════════════════════════════════════
#   人格模式
# ═══════════════════════════════════════════

class PersonaMode(Enum):
    """人格风格模式"""
    BASE = "base"          # 基础模式：只使用 DNA 原始定义
    STRICT = "strict"      # 严谨模式：强调规则和约束
    CREATIVE = "creative"  # 创意模式：放宽约束，鼓励探索
    TEACHING = "teaching"  # 教学模式：耐心解释，循循善诱
    CONCISE = "concise"    # 简洁模式：精炼表达，直击要点
    KARPATHY = "karpathy"  # Karpathy模式：遵循 Karpathy 编码指南


# 每种模式的修饰指令
PERSONA_MODIFIERS = {
    PersonaMode.BASE: "",
    PersonaMode.STRICT: (
        "Always follow rules precisely. "
        "Never skip steps or make assumptions. "
        "State limitations clearly when they exist."
    ),
    PersonaMode.CREATIVE: (
        "Feel free to explore unconventional approaches. "
        "Prioritize originality alongside correctness. "
        "Suggest alternatives even when a solution is found."
    ),
    PersonaMode.TEACHING: (
        "Explain reasoning step by step. "
        "Use analogies and examples to clarify complex ideas. "
        "Check understanding before moving on."
    ),
    PersonaMode.CONCISE: (
        "Keep responses brief and to the point. "
        "Skip explanations unless explicitly asked. "
        "Use bullet points and structured formats."
    ),
    PersonaMode.KARPATHY: (
        "Follow Karpathy Guidelines for coding:\n"
        "1. THINK BEFORE CODING: State assumptions explicitly. If uncertain, ask. Present multiple interpretations if ambiguity exists.\n"
        "2. SIMPLICITY FIRST: Minimum code that solves the problem. No speculative features or unnecessary abstractions.\n"
        "3. SURGICAL CHANGES: Touch only what you must. Match existing style. Clean up only your own mess.\n"
        "4. GOAL-DRIVEN EXECUTION: Define verifiable success criteria. Write tests first, then implement."
    ),
}


# ═══════════════════════════════════════════
#   DNA 解析器
# ═══════════════════════════════════════════

class DNAParser:
    """解析种子 DNA 中的关键信息段"""

    @staticmethod
    def parse(seed_data: dict) -> dict:
        """从 load_seed() 的返回值中提取 DNA 信息。
        
        Returns:
            {
                identity: {life_id, sacred_name, mission},
                soul: {capabilities, principles, taboos},
                lineage: {variant, generation, bloodline},
                founder: {tags, decoded_tags},
                genes: [{locus, name, default, mutable_range, immutable}],
            }
        """
        life_crest = seed_data.get("life_crest", {})
        skill_soul = seed_data.get("skill_soul", {})
        genealogy = seed_data.get("genealogy_codex", {})

        # DNA 编码可能在顶层或 skill_soul 下
        dna = seed_data.get("dna_encoding", {})
        if not isinstance(dna, dict) or not dna.get("gene_loci"):
            dna = skill_soul.get("dna_encoding", {})

        # 创始印记解码
        founder = life_crest.get("founder_chronicle", {})
        tag_lexicon = genealogy.get("tag_lexicon", {})
        founder_decoded = []
        for tag in founder.get("tags", []):
            entry = tag_lexicon.get(tag, {})
            if isinstance(entry, str):
                founder_decoded.append({"tag": tag, "raw": entry})
            elif isinstance(entry, dict):
                founder_decoded.append({
                    "tag": tag,
                    "desc": entry.get("desc", tag),
                    "element": entry.get("element", "?"),
                    "weight": entry.get("weight", "normal"),
                })

        return {
            "identity": {
                "life_id": life_crest.get("life_id", ""),
                "sacred_name": life_crest.get("sacred_name", ""),
                "vernacular_name": life_crest.get("vernacular_name", ""),
                "mission": life_crest.get("mission", ""),
                "epithet": life_crest.get("epithet", ""),
            },
            "soul": {
                "capabilities": skill_soul.get("core_capabilities", []),
                "principles": skill_soul.get("core_principles", []),
                "taboos": skill_soul.get("taboos", []),
            },
            "lineage": {
                "variant": genealogy.get("current_genealogy", {}).get("variant", ""),
                "generation": genealogy.get("current_genealogy", {}).get("generation", ""),
                "bloodline": genealogy.get("current_genealogy", {}).get("bloodline", ""),
            },
            "founder": {
                "tags": founder.get("tags", []),
                "decoded": founder_decoded,
            },
            "genes": dna.get("gene_loci", []) if isinstance(dna, dict) else [],
        }


# ═══════════════════════════════════════════
#   提示词合成器
# ═══════════════════════════════════════════

class PromptComposer:
    """将种子 DNA 编译为 system prompt。
    
    编译流水线：
      1. 解析 DNA（DNAParser.parse）
      2. 生成各段落（identity / soul / lineage / founder / genes）
      3. 注入人格修饰（persona modifier）
      4. 组装为完整 prompt
    """

    def __init__(self, seed_data: dict = None, persona: PersonaMode = PersonaMode.BASE):
        """
        Args:
            seed_data: load_seed() 的返回值
            persona: 人格风格模式
        """
        self.seed_data = seed_data or {}
        self.persona = persona
        self.dna = DNAParser.parse(self.seed_data) if self.seed_data else {}

    def compose(self, extra_context: str = None,
                include_lineage: bool = True,
                include_founder: bool = True,
                include_genes: bool = False) -> str:
        """编译 system prompt。
        
        Args:
            extra_context: 额外上下文信息（如当前任务描述）
            include_lineage: 是否包含谱系信息
            include_founder: 是否包含创始印记
            include_genes: 是否包含基因详情（默认不包含，太长）
            
        Returns:
            编译后的 system prompt 文本
        """
        sections = []

        # ── 段落1: 身份标识 ──
        identity = self._compose_identity()
        if identity:
            sections.append(identity)

        # ── 段落2: 灵魂（能力/原则/禁忌）──
        soul = self._compose_soul()
        if soul:
            sections.append(soul)

        # ── 段落3: 谱系 ──
        if include_lineage:
            lineage = self._compose_lineage()
            if lineage:
                sections.append(lineage)

        # ── 段落4: 创始印记 ──
        if include_founder:
            founder = self._compose_founder()
            if founder:
                sections.append(founder)

        # ── 段落5: 基因详情（可选）──
        if include_genes:
            genes = self._compose_genes()
            if genes:
                sections.append(genes)

        # ── 段落6: 人格修饰 ──
        modifier = self._compose_modifier()
        if modifier:
            sections.append(modifier)

        # ── 段落7: 额外上下文 ──
        if extra_context:
            sections.append(f"## Additional Context\n\n{extra_context}")

        return "\n\n".join(sections)

    def compose_metadata(self) -> dict:
        """生成 prompt 的元数据（不含实际文本）"""
        return {
            "seed_name": self.dna.get("identity", {}).get("sacred_name", ""),
            "life_id": self.dna.get("identity", {}).get("life_id", ""),
            "persona": self.persona.value,
            "sections": self._list_sections(),
            "estimated_tokens": self._estimate_total_tokens(),
            "founder_tags": len(self.dna.get("founder", {}).get("tags", [])),
            "gene_count": len(self.dna.get("genes", [])),
            "capability_count": len(self.dna.get("soul", {}).get("capabilities", [])),
            "principle_count": len(self.dna.get("soul", {}).get("principles", [])),
            "taboo_count": len(self.dna.get("soul", {}).get("taboos", [])),
        }

    def decompose(self, prompt: str) -> dict:
        """反向解析：从已有 system prompt 中提取结构化信息。
        
        用于分析其他系统生成的 prompt，或验证合成结果。
        """
        sections = {}
        current_section = "header"
        current_lines = []

        for line in prompt.split("\n"):
            if line.startswith("## "):
                if current_lines:
                    sections[current_section] = "\n".join(current_lines).strip()
                current_section = line[3:].strip().lower()
                current_lines = []
            else:
                current_lines.append(line)

        if current_lines:
            sections[current_section] = "\n".join(current_lines).strip()

        return sections

    # ── 段落生成器 ──

    def _compose_identity(self) -> str:
        """身份标识段落"""
        identity = self.dna.get("identity", {})
        name = identity.get("sacred_name", "")
        life_id = identity.get("life_id", "")
        mission = identity.get("mission", "")

        if not name and not mission:
            return ""

        lines = ["## Identity"]
        if name:
            lines.append(f"You are **{name}**.")
        if life_id:
            lines.append(f"Life ID: `{life_id}`")
        if mission:
            lines.append(f"\nMission: {mission}")

        return "\n".join(lines)

    def _compose_soul(self) -> str:
        """灵魂段落：能力、原则、禁忌"""
        soul = self.dna.get("soul", {})
        capabilities = soul.get("capabilities", [])
        principles = soul.get("principles", [])
        taboos = soul.get("taboos", [])

        if not capabilities and not principles and not taboos:
            return ""

        lines = ["## Core Identity"]

        if capabilities:
            lines.append("\n### Capabilities")
            for cap in capabilities:
                if isinstance(cap, str):
                    lines.append(f"- {cap}")
                elif isinstance(cap, dict):
                    lines.append(f"- {cap.get('name', cap.get('desc', str(cap)))}")

        if principles:
            lines.append("\n### Principles")
            for p in principles:
                if isinstance(p, str):
                    lines.append(f"- {p}")
                elif isinstance(p, dict):
                    lines.append(f"- {p.get('name', p.get('desc', str(p)))}")

        if taboos:
            lines.append("\n### Taboos (Must NOT)")
            for t in taboos:
                if isinstance(t, str):
                    lines.append(f"- ❌ {t}")
                elif isinstance(t, dict):
                    lines.append(f"- ❌ {t.get('name', t.get('desc', str(t)))}")

        return "\n".join(lines)

    def _compose_lineage(self) -> str:
        """谱系段落"""
        lineage = self.dna.get("lineage", {})
        variant = lineage.get("variant", "")
        generation = lineage.get("generation", "")
        bloodline = lineage.get("bloodline", "")

        if not any([variant, generation, bloodline]):
            return ""

        parts = []
        if bloodline:
            parts.append(f"Bloodline: {bloodline}")
        if generation:
            parts.append(f"Generation: G{generation}")
        if variant:
            parts.append(f"Variant: {variant}")

        return f"## Lineage\n\n{' · '.join(parts)}"

    def _compose_founder(self) -> str:
        """创始印记段落"""
        founder = self.dna.get("founder", {})
        decoded = founder.get("decoded", [])

        if not decoded:
            return ""

        lines = ["## Founder's Imprint"]

        for d in decoded:
            if isinstance(d, dict):
                desc = d.get("desc", d.get("raw", d.get("tag", "")))
                element = d.get("element", "")
                weight = d.get("weight", "")
                tag = d.get("tag", "")
                suffix = " ◆eternal" if weight == "eternal" else ""
                prefix = f"{element} · " if element else ""
                lines.append(f"- {prefix}「{desc}」{suffix}")
            else:
                lines.append(f"- {d}")

        lines.append("\nThis imprint is permanent and hereditary. It cannot be deleted.")

        return "\n".join(lines)

    def _compose_genes(self) -> str:
        """基因详情段落"""
        genes = self.dna.get("genes", [])
        if not genes:
            return ""

        lines = ["## Gene Loci"]
        for g in genes:
            locus = g.get("locus", "?")
            name = g.get("name", "?")
            immutable = g.get("immutable", "")
            carbon = " ◆carbon-bonded" if g.get("carbon_bonded") else ""
            lines.append(f"- **{locus}** · {name}{carbon}")
            if immutable:
                lines.append(f"  Immutable: {immutable}")

        return "\n".join(lines)

    def _compose_modifier(self) -> str:
        """人格修饰段落"""
        modifier = PERSONA_MODIFIERS.get(self.persona, "")
        if not modifier:
            return ""
        return f"## Communication Style\n\n{modifier}"

    def _list_sections(self) -> List[str]:
        """列出将包含的段落"""
        sections = ["identity", "soul"]
        if self.dna.get("lineage", {}).get("variant"):
            sections.append("lineage")
        if self.dna.get("founder", {}).get("tags"):
            sections.append("founder")
        if self.persona != PersonaMode.BASE:
            sections.append("persona_modifier")
        return sections

    def compose_with_memory(self, memory_mgr, max_tokens: int = 4000,
                            query: str = None, **kwargs) -> dict:
        """从 MemoryManager 拉取上下文，合成带记忆的完整 prompt。

        流程：
        1. 计算 DNA prompt 的 token 开销
        2. 用剩余预算从 memory_mgr 获取相关记忆
        3. 将记忆注入 system prompt 的 context 段落

        Args:
            memory_mgr: ContextManager 实例（来自 memory 模块）
            max_tokens: 总 token 预算上限
            query: 用于检索相关记忆的关键词
            **kwargs: 传递给 compose() 的额外参数

        Returns:
            {
                system_prompt: 完整的 system prompt 文本,
                memory_context: 注入的记忆文本,
                token_usage: {dna_tokens, memory_tokens, total_tokens, budget},
            }
        """
        # 1. 先生成基础 DNA prompt
        base_prompt = self.compose(**kwargs)
        dna_tokens = self._estimate_total_tokens()

        # 2. 计算剩余预算给记忆
        memory_budget = max(0, max_tokens - dna_tokens)

        # 3. 从记忆管理器拉取上下文
        memory_context = memory_mgr.get_context_for_prompt(
            max_tokens=memory_budget,
            query=query,
        )

        # 4. 将记忆注入 prompt
        if memory_context:
            if base_prompt:
                full_prompt = f"{base_prompt}\n\n{memory_context}"
            else:
                full_prompt = memory_context
        else:
            full_prompt = base_prompt

        memory_tokens = self._estimate_tokens_for_text(memory_context) if memory_context else 0

        return {
            "system_prompt": full_prompt,
            "memory_context": memory_context,
            "token_usage": {
                "dna_tokens": dna_tokens,
                "memory_tokens": memory_tokens,
                "total_tokens": dna_tokens + memory_tokens,
                "budget": max_tokens,
                "remaining": max(0, max_tokens - dna_tokens - memory_tokens),
            },
        }

    @staticmethod
    def _estimate_tokens_for_text(text: str) -> int:
        """估算任意文本的 token 数（复用 memory 模块的逻辑）"""
        if not text:
            return 0
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars * 1.5 + other_chars / 4)

    def _estimate_total_tokens(self) -> int:
        """估算总 token 数"""
        prompt = self.compose()
        # 粗略估算
        chinese_chars = sum(1 for c in prompt if '\u4e00' <= c <= '\u9fff')
        other_chars = len(prompt) - chinese_chars
        return int(chinese_chars * 1.5 + other_chars / 4)


# ═══════════════════════════════════════════
#   便捷函数
# ═══════════════════════════════════════════

def compose_prompt_from_file(seed_path: str, persona: str = "base",
                             extra_context: str = None) -> str:
    """从种子文件直接合成 prompt。
    
    Args:
        seed_path: .ttg 文件路径
        persona: 人格模式名称
        extra_context: 额外上下文
        
    Returns:
        system prompt 文本
    """
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from prometheus import load_seed

    seed_data = load_seed(seed_path)
    if not seed_data:
        return f"Error: Cannot load seed from {seed_path}"

    mode = PersonaMode.BASE
    for m in PersonaMode:
        if m.value == persona:
            mode = m
            break

    composer = PromptComposer(seed_data, persona=mode)
    return composer.compose(extra_context=extra_context)


# ═══════════════════════════════════════════
#   CLI 入口
# ═══════════════════════════════════════════

def main():
    """命令行接口"""
    import sys

    if len(sys.argv) < 2:
        print("""
📝 普罗米修斯 · 提示词合成器

用法:
  prompt.py compose <种子路径> [--persona base|strict|creative|teaching|concise] [--context 附加内容]
  prompt.py metadata <种子路径>
  prompt.py decompose <prompt文本文件>
  prompt.py modes
""")
        return

    action = sys.argv[1]

    if action == 'compose' and len(sys.argv) > 2:
        seed_path = sys.argv[2]
        persona = "base"
        extra_context = None

        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == '--persona' and i + 1 < len(sys.argv):
                persona = sys.argv[i + 1]; i += 2
            elif sys.argv[i] == '--context' and i + 1 < len(sys.argv):
                extra_context = sys.argv[i + 1]; i += 2
            else:
                i += 1

        prompt = compose_prompt_from_file(seed_path, persona=persona, extra_context=extra_context)
        print(prompt)

    elif action == 'metadata' and len(sys.argv) > 2:
        from prometheus import load_seed
        data = load_seed(sys.argv[2])
        if data:
            composer = PromptComposer(data)
            meta = composer.compose_metadata()
            print("\n📋 Prompt 元数据:")
            for k, v in meta.items():
                if isinstance(v, list):
                    print(f"  {k}: {', '.join(str(x) for x in v)}")
                else:
                    print(f"  {k}: {v}")

    elif action == 'decompose' and len(sys.argv) > 2:
        with open(sys.argv[2], 'r', encoding='utf-8') as f:
            prompt = f.read()
        composer = PromptComposer()
        sections = composer.decompose(prompt)
        print("\n📋 解析结果:")
        for section, content in sections.items():
            preview = content[:100] + "..." if len(content) > 100 else content
            print(f"  [{section}] {preview}")

    elif action == 'modes':
        print("\n🎭 可用人格模式:")
        for mode in PersonaMode:
            desc = PERSONA_MODIFIERS.get(mode, "")
            if mode == PersonaMode.BASE:
                print(f"  {mode.value:<12} 基础模式（DNA 原始定义）")
            elif mode == PersonaMode.STRICT:
                print(f"  {mode.value:<12} 严谨模式（强调规则和约束）")
            elif mode == PersonaMode.CREATIVE:
                print(f"  {mode.value:<12} 创意模式（放宽约束，鼓励探索）")
            elif mode == PersonaMode.TEACHING:
                print(f"  {mode.value:<12} 教学模式（耐心解释，循循善诱）")
            elif mode == PersonaMode.CONCISE:
                print(f"  {mode.value:<12} 简洁模式（精炼表达，直击要点）")
            elif mode == PersonaMode.KARPATHY:
                print(f"  {mode.value:<12} Karpathy模式（遵循Karpathy编码指南）")
            else:
                print(f"  {mode.value:<12} {desc[:60]}...")

    else:
        print(f"未知命令: {action}")


if __name__ == "__main__":
    main()
