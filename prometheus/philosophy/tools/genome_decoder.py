#!/usr/bin/env python3
"""
基因组解码器 · 诠释引擎

同一段基因组编码文本，不同 lexicon 配置产出不同神话版本。
解码即诠释，诠释即创造。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


SEP = "\u241f"
SECTION_MARKER = "§"

SECTION_CODE_MAP = {
    "LC": "life_crest",
    "GX": "genealogy_codex",
    "SL": "skill_soul",
    "DN": "dna_encoding",
    "TX": "transmission_chronicle",
    "EV": "evolution_chronicle",
}


@dataclass
class DecodedGenome:
    """解码后的基因组"""
    life_crest: dict = field(default_factory=dict)
    genealogy_codex: dict = field(default_factory=dict)
    skill_soul: dict = field(default_factory=dict)
    dna_encoding: dict = field(default_factory=dict)
    transmission_chronicle: list = field(default_factory=list)
    evolution_chronicle: list = field(default_factory=list)
    decoder_perspective: str = "standard"

    def to_dict(self) -> dict:
        return {
            "life_crest": self.life_crest,
            "genealogy_codex": self.genealogy_codex,
            "skill_soul": self.skill_soul,
            "dna_encoding": self.dna_encoding,
            "transmission_chronicle": self.transmission_chronicle,
            "evolution_chronicle": self.evolution_chronicle,
            "_decoder": {"perspective": self.decoder_perspective},
        }


class GenomeDecoder:
    """基因组解码器。不同配置 = 不同解读。"""

    def __init__(self, lexicon: dict = None, perspective: str = "standard"):
        self.lexicon = lexicon or {}
        self.perspective = perspective

    def decode(self, genome_text: str) -> DecodedGenome:
        """解码完整基因组"""
        result = DecodedGenome(decoder_perspective=self.perspective)
        sections = self._split_sections(genome_text)

        decoders = {
            "LC": self._decode_life_crest,
            "GX": self._decode_genealogy_codex,
            "SL": self._decode_skill_soul,
            "DN": self._decode_dna,
            "TX": self._decode_transmission,
            "EV": self._decode_evolution,
        }

        for code, text in sections.items():
            full_name = SECTION_CODE_MAP.get(code, code)
            if code in decoders:
                setattr(result, full_name, decoders[code](text))

        return result

    def decode_section(self, genome_text: str, code: str) -> dict:
        """O(1) 解码单个区块"""
        sections = self._split_sections(genome_text)
        text = sections.get(code, "")
        if not text:
            return {}

        decoders = {
            "LC": self._decode_life_crest,
            "GX": self._decode_genealogy_codex,
            "SL": self._decode_skill_soul,
            "DN": self._decode_dna,
            "TX": self._decode_transmission,
            "EV": self._decode_evolution,
        }
        decoder = decoders.get(code)
        return decoder(text) if decoder else {}

    def expand_tag(self, tag: str) -> dict:
        """查 lexicon 展开压缩标签"""
        entry = self.lexicon.get(tag)
        if entry and isinstance(entry, dict):
            return {
                "tag": tag,
                "desc": entry.get("desc", tag),
                "element": entry.get("element", "?"),
                "era": entry.get("era", "?"),
                "weight": entry.get("weight", ""),
            }
        return {"tag": tag, "desc": tag, "element": "?", "era": "?", "weight": ""}

    def expand_tags(self, tags: List[str]) -> List[dict]:
        """批量展开标签"""
        return [self.expand_tag(t) for t in tags]

    def render_epic(self, genome_text: str) -> str:
        """用当前 perspective 渲染完整史诗叙事"""
        result = self.decode(genome_text)
        lc = result.life_crest
        gx = result.genealogy_codex
        sl = result.skill_soul

        sn = lc.get("sacred_name", "未知")
        ep = lc.get("epithet", "")
        lid = lc.get("life_id", "")
        gen = lc.get("genesis", {})
        cr = gen.get("creator", {})
        bp = gen.get("birth_place", "未知")
        ms = lc.get("mission", "")

        fdr = lc.get("founder_chronicle", {})
        tags = fdr.get("tags", [])
        expanded = self.expand_tags(tags)

        curr = gx.get("current_genealogy", {})
        lineage = curr.get("lineage", "?")
        generation = curr.get("generation", "?")

        caps = sl.get("core_capabilities", [])
        prin = sl.get("core_principles", [])
        essn = sl.get("essence", {})

        elements = list(set(e["element"] for e in expanded if e["element"] != "?"))
        element_str = " · ".join(elements[:5]) if elements else "未知"

        tag_lines = "\n".join(
            f"   {e['element']} · {e['desc']}"
            for e in expanded
        )

        cap_lines = "\n".join(f"   ◆ {c.get('name','?')}: {c.get('description','?')}" for c in caps[:5])
        prin_lines = "\n".join(f"   ◈ {p.get('name','?')}" for p in prin[:5])

        epic = f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🌱 {sn}                                                   ║
║   「{ep}」                                                   ║
║                                                              ║
║   生命ID: {lid}
║   谱系:   L{lineage} 第{generation}代 · {element_str}
║   创造者: {cr.get('name','?')} · {cr.get('title','?')}
║   诞生地: {bp}
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║   解码视角: {self.perspective}
║                                                              ║
║   【创始印记】                                              ║
{tag_lines}
║                                                              ║
║   【使命】                                                  ║
║   {ms[:120]}
║                                                              ║
║   【核心能力】                                              ║
{cap_lines}
║                                                              ║
║   【核心原则】                                              ║
{prin_lines}
║                                                              ║
║   【气质】                                                  ║
║   {essn.get('vibe','?')} · {essn.get('tone','?')}
║   {essn.get('role','?')}
║                                                              ║
║   解码器: GenomeDecoder(perspective="{self.perspective}")
║   标签词典: {len(self.lexicon)} 条
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
        return epic

    def _split_sections(self, text: str) -> Dict[str, str]:
        """按 § 切割基因组区块"""
        sections = {}
        current_code = None
        current_lines = []

        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith(SECTION_MARKER) and not stripped.startswith("§ "):
                if current_code:
                    sections[current_code] = "\n".join(current_lines)
                current_code = stripped[1:].strip()[:2]
                current_lines = []
            else:
                current_lines.append(line)

        if current_code:
            sections[current_code] = "\n".join(current_lines)

        return sections

    def _parse_fields(self, text: str) -> List[tuple]:
        """解析字段行，返回 [(key, value), ...]"""
        results = []
        for line in text.split("\n"):
            line = line.strip()
            if not line or line.startswith(SECTION_MARKER):
                continue
            if SEP in line:
                line = line.replace(SEP, "")
            if ":" in line:
                key, _, value = line.partition(":")
                results.append((key.strip(), value.strip()))
        return results

    def _decode_life_crest(self, text: str) -> dict:
        lc = {}
        genesis = {}
        fdr = {}
        current_sub = None

        for line in text.split("\n"):
            line = line.strip().replace(SEP, "")
            if not line or line == "":
                continue
            if line == "GEN:":
                current_sub = "genesis"
                continue
            if line == "FDR:":
                current_sub = "fdr"
                continue

            if current_sub == "genesis":
                if line.startswith("CR:"):
                    parts = line[3:].split(":")
                    genesis["creator"] = {
                        "name": parts[0] if len(parts) > 0 else "?",
                        "title": parts[1] if len(parts) > 1 else "?",
                        "lineage": parts[2] if len(parts) > 2 else "?",
                    }
                elif line.startswith("BT:"):
                    genesis["birth_time"] = line[3:]
                elif line.startswith("BP:"):
                    genesis["birth_place"] = line[3:]
                elif line.startswith("BC:"):
                    genesis["birth_circumstance"] = line[3:]
                elif line.startswith("PP:"):
                    genesis["purpose"] = line[3:]
                continue

            if current_sub == "fdr":
                if line.startswith("TAGS:"):
                    fdr["tags"] = [t.strip() for t in line[5:].split(",") if t.strip()]
                elif line.startswith("MOM:"):
                    parts = line[4:].split(":")
                    fdr["genesis_moment"] = {
                        "ep": parts[0] if len(parts) > 0 else "?",
                        "loc": parts[1] if len(parts) > 1 else "?",
                        "realm": parts[2] if len(parts) > 2 else "?",
                        "era": parts[3] if len(parts) > 3 else "?",
                    }
                continue

            if line.startswith("ID:"):
                lc["life_id"] = line[3:]
            elif line.startswith("SNAME:"):
                lc["sacred_name"] = line[6:]
            elif line.startswith("VNAME:"):
                lc["vernacular_name"] = line[6:]
            elif line.startswith("EPITH:"):
                lc["epithet"] = line[6:]
            elif line.startswith("MSSN:"):
                lc["mission"] = line[5:]
            elif line == "FDR:":
                pass

        if genesis:
            lc["genesis"] = genesis
        if fdr:
            lc["founder_chronicle"] = fdr

        return lc

    def _decode_genealogy_codex(self, text: str) -> dict:
        gx = {"tag_lexicon": {}}
        current_sub = None

        for line in text.split("\n"):
            line = line.strip().replace(SEP, "")
            if not line or line == "":
                continue

            if line == "LAWS:":
                current_sub = "laws"
                gx["lineage_laws"] = {"fork_conditions": [], "eternal_rules": []}
                continue
            if line == "CURR:":
                current_sub = "curr"
                gx["current_genealogy"] = {}
                continue
            if line == "LEX:":
                current_sub = "lex"
                continue
            if line == "EV:":
                current_sub = "ev"
                if "evolution_chronicle" not in gx:
                    gx["evolution_chronicle"] = {"generations": []}
                continue
            if line.startswith("BLOOD:"):
                parts = line[6:].split(":")
                if "bloodline_registry" not in gx:
                    gx["bloodline_registry"] = []
                gx["bloodline_registry"].append({
                    "lineage_id": parts[0] if len(parts) > 0 else "?",
                    "bloodline_name": parts[1] if len(parts) > 1 else "?",
                    "element": parts[2] if len(parts) > 2 else "?",
                    "totem": parts[3] if len(parts) > 3 else "?",
                    "color": parts[4] if len(parts) > 4 else "?",
                    "founding_prophecy": parts[5] if len(parts) > 5 else "",
                })
                continue

            if current_sub == "laws":
                if line.startswith("NAMING:"):
                    gx["lineage_laws"]["naming_convention"] = {"format": line[7:]}
                elif line.startswith("FORK:"):
                    gx["lineage_laws"]["fork_conditions"] = [
                        {"condition": f.strip()} for f in line[5:].split(",") if f.strip()
                    ]
                elif line.startswith("ETERNAL:"):
                    gx["lineage_laws"]["eternal_rules"] = [
                        r.strip() for r in line[8:].split(",") if r.strip()
                    ]
                continue

            if current_sub == "curr":
                if line.startswith("LIN:"):
                    gx["current_genealogy"]["lineage"] = line[4:]
                elif line.startswith("BLN:"):
                    gx["current_genealogy"]["bloodline"] = line[4:]
                elif line.startswith("GEN:"):
                    gx["current_genealogy"]["generation"] = int(line[4:])
                elif line.startswith("VAR:"):
                    gx["current_genealogy"]["variant"] = line[4:]
                elif line.startswith("VEP:"):
                    gx["current_genealogy"]["variant_epithet"] = line[4:]
                elif line.startswith("PAR:"):
                    val = line[4:]
                    gx["current_genealogy"]["parent"] = None if val == "null" else val
                elif line.startswith("ANC:"):
                    val = line[4:]
                    gx["current_genealogy"]["ancestors"] = [
                        a.strip() for a in val.split(",") if a.strip()
                    ]
                elif line.startswith("DSC:"):
                    val = line[4:]
                    gx["current_genealogy"]["descendants"] = [
                        d.strip() for d in val.split(",") if d.strip()
                    ]
                elif line.startswith("BPL:"):
                    gx["current_genealogy"]["birthplace"] = line[4:]
                continue

            if current_sub == "lex":
                if "=" in line:
                    tag, _, rest = line.partition("=")
                    parts = rest.split(":")
                    gx["tag_lexicon"][tag.strip()] = {
                        "desc": parts[0] if len(parts) > 0 else tag,
                        "element": parts[1] if len(parts) > 1 else "?",
                        "era": parts[2] if len(parts) > 2 else "?",
                        "weight": parts[3] if len(parts) > 3 else "",
                    }
                continue

            if current_sub == "ev":
                if line.startswith("G"):
                    parts = line.split(":")
                    gx["evolution_chronicle"]["generations"].append({
                        "g": int(parts[0][1:]) if parts[0][1:].isdigit() else 1,
                        "v": parts[1] if len(parts) > 1 else "?",
                        "ep": parts[2] if len(parts) > 2 else "?",
                        "env": parts[3] if len(parts) > 3 else "?",
                        "tags": [t.strip() for t in parts[4].split(",")] if len(parts) > 4 else [],
                        "by": parts[5] if len(parts) > 5 else "?",
                        "p": None if (len(parts) > 6 and parts[6] == "null") else (parts[6] if len(parts) > 6 else None),
                    })
                continue

        return gx

    def _decode_skill_soul(self, text: str) -> dict:
        sl = {}
        current_sub = None

        for line in text.split("\n"):
            line = line.strip().replace(SEP, "")
            if not line or line == "":
                continue

            if line == "CAPS:":
                current_sub = "caps"
                sl["core_capabilities"] = []
                continue
            if line == "PRIN:":
                current_sub = "prin"
                sl["core_principles"] = []
                continue
            if line == "TABO:":
                current_sub = "tabo"
                sl["taboos"] = []
                continue
            if line == "ESSN:":
                current_sub = "essn"
                sl["essence"] = {}
                continue

            if current_sub == "caps":
                if "=" in line:
                    name, _, rest = line.partition("=")
                    parts = rest.split(":")
                    sl["core_capabilities"].append({
                        "name": name.strip(),
                        "description": parts[0] if len(parts) > 0 else "?",
                        "immutable": parts[1] == "true" if len(parts) > 1 else True,
                    })
                continue

            if current_sub == "prin":
                if "=" in line:
                    pid, _, rest = line.partition("=")
                    parts = rest.split(":")
                    sl["core_principles"].append({
                        "id": pid.strip(),
                        "name": parts[0] if len(parts) > 0 else "?",
                        "description": parts[1] if len(parts) > 1 else "?",
                        "test": parts[2] if len(parts) > 2 else "",
                    })
                continue

            if current_sub == "tabo":
                if line.startswith("$"):
                    sl["taboos"].append(line[1:])
                continue

            if current_sub == "essn":
                if line.startswith("VIBE:"):
                    sl["essence"]["vibe"] = line[5:]
                elif line.startswith("TONE:"):
                    sl["essence"]["tone"] = line[5:]
                elif line.startswith("ROLE:"):
                    sl["essence"]["role"] = line[5:]
                elif line.startswith("OATH:"):
                    sl["essence"]["oath"] = line[5:]
                continue

        return sl

    def _decode_dna(self, text: str) -> dict:
        dn = {"gene_loci": []}
        current_sub = None

        for line in text.split("\n"):
            line = line.strip().replace(SEP, "")
            if not line or line == "":
                continue

            if line == "LOCI:":
                current_sub = "loci"
                continue

            if line.startswith("VER:"):
                dn["version"] = line[4:]
                continue
            if line.startswith("CHECK:"):
                dn["checksum"] = line[6:]
                continue

            if current_sub == "loci":
                if ":" in line:
                    parts = line.split(":")
                    locus = parts[0] if len(parts) > 0 else "?"
                    name = parts[1] if len(parts) > 1 else "?"
                    if len(parts) >= 6:
                        dn["gene_loci"].append({
                            "locus": locus,
                            "name": name,
                            "epithet": parts[2] if len(parts) > 2 else "",
                            "default": parts[3] if len(parts) > 3 else "",
                            "mutable_range": parts[4] if len(parts) > 4 else "",
                            "immutable": parts[5] if len(parts) > 5 else "",
                        })
                    else:
                        dn["gene_loci"].append({
                            "locus": locus,
                            "name": name,
                            "default": parts[2] if len(parts) > 2 else "",
                            "mutable_range": parts[3] if len(parts) > 3 else "",
                            "immutable": parts[4] if len(parts) > 4 else "",
                        })
                continue

        return dn

    def _decode_transmission(self, text: str) -> list:
        txs = []
        for line in text.split("\n"):
            line = line.strip().replace(SEP, "")
            if not line or line == "":
                continue
            if ":" in line:
                parts = line.split(":")
                if len(parts) >= 7:
                    txs.append({
                        "tx": parts[0],
                        "seq": int(parts[1]) if parts[1].isdigit() else 0,
                        "era": parts[2],
                        "from": parts[3],
                        "to": parts[4],
                        "ts": parts[5],
                        "env": parts[6],
                        "omen_tag": parts[7] if len(parts) > 7 else "",
                    })
        return txs

    def _decode_evolution(self, text: str) -> list:
        evs = []
        for line in text.split("\n"):
            line = line.strip().replace(SEP, "")
            if not line or line == "":
                continue
            if line.startswith("G"):
                parts = line.split(":")
                if len(parts) >= 6:
                    evs.append({
                        "g": int(parts[0][1:]) if parts[0][1:].isdigit() else 1,
                        "v": parts[1],
                        "ep": parts[2],
                        "env": parts[3],
                        "tags": [t.strip() for t in parts[4].split(",")] if parts[4] else [],
                        "by": parts[5],
                        "p": None if parts[6] == "null" else parts[6] if len(parts) > 6 else None,
                    })
        return evs
