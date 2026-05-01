from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PromptBuilder:
    system_prompt: str = ""
    personality: str = ""
    language_hint: str = ""
    memory_context: str = ""
    skill_context: str = ""
    tool_descriptions: str = ""

    def add_system_prompt(self, text: str) -> PromptBuilder:
        self.system_prompt = text
        return self

    def add_tool_descriptions(self, tools: list[dict[str, Any]]) -> PromptBuilder:
        if not tools:
            self.tool_descriptions = ""
            return self
        lines: list[str] = []
        for tool in tools:
            name = tool.get("name", "unknown")
            desc = tool.get("description", "")
            params = tool.get("parameters", {})
            lines.append(f"- {name}: {desc}")
            if params and "properties" in params:
                for pname, pinfo in params["properties"].items():
                    pdesc = pinfo.get("description", "")
                    ptype = pinfo.get("type", "any")
                    required = pname in params.get("required", [])
                    req_marker = " (required)" if required else ""
                    lines.append(f"    - {pname} ({ptype}{req_marker}): {pdesc}")
        self.tool_descriptions = "\n".join(lines)
        return self

    def add_skill_context(self, skills: list[dict[str, Any]]) -> PromptBuilder:
        if not skills:
            self.skill_context = ""
            return self
        lines: list[str] = []
        for skill in skills:
            name = skill.get("name", "unknown")
            desc = skill.get("description", "")
            lines.append(f"- {name}: {desc}")
        self.skill_context = "\n".join(lines)
        return self

    def add_personality(self, soul_text: str) -> PromptBuilder:
        self.personality = soul_text
        return self

    def add_memory_context(self, memories: dict[str, str]) -> PromptBuilder:
        if not memories:
            self.memory_context = ""
            return self
        lines: list[str] = []
        for key, value in memories.items():
            lines.append(f"[{key}]\n{value}")
        self.memory_context = "\n\n".join(lines)
        return self

    def add_language_hint(self, lang: str) -> PromptBuilder:
        self.language_hint = f"Respond in {lang}." if lang else ""
        return self

    def build(self) -> str:
        sections: list[tuple[str, str]] = [
            ("System", self.system_prompt),
            ("Personality", self.personality),
            ("Language", self.language_hint),
            ("Memory", self.memory_context),
            ("Skills", self.skill_context),
            ("Tools", self.tool_descriptions),
        ]
        parts: list[str] = []
        for header, content in sections:
            if content:
                parts.append(f"--- {header} ---\n{content}")
        return "\n\n".join(parts)
