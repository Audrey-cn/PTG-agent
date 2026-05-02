#!/usr/bin/env python3
"""
基因组编码器

将结构化种子数据编码为 § 标记的基因组文本。
叙事被压缩为编码符号，不露白。
"""

from __future__ import annotations

from typing import Any, Dict, List

SEP = "␟"
BLOCK_END = "␟\n"


def encode_genome(data: dict) -> str:
    """将完整种子数据编码为基因组文本"""
    sections = []

    lc = data.get("life_crest")
    if lc:
        sections.append(encode_life_crest(lc))

    gx = data.get("genealogy_codex")
    if gx:
        sections.append(encode_genealogy_codex(gx))

    sl = data.get("skill_soul")
    if sl:
        sections.append(encode_skill_soul(sl))

    dn = data.get("dna_encoding")
    if dn:
        sections.append(encode_dna(dn))

    tx = data.get("transmission_chronicle")
    if tx:
        sections.append(encode_transmission(tx))

    ev = data.get("evolution_chronicle")
    if ev:
        sections.append(encode_evolution(ev))

    return "\n".join(sections) + "\n"


def encode_life_crest(lc: dict) -> str:
    """编码生命元数据 §LC"""
    lines = ["§LC"]

    lid = lc.get("life_id", "")
    if lid:
        lines.append(f"  ID:{lid}{SEP}")

    sn = lc.get("sacred_name", "")
    if sn:
        lines.append(f"  SNAME:{sn}{SEP}")

    vn = lc.get("vernacular_name", "")
    if vn:
        lines.append(f"  VNAME:{vn}{SEP}")

    ep = lc.get("epithet", "")
    if ep:
        lines.append(f"  EPITH:{ep}{SEP}")

    gen = lc.get("genesis")
    if gen:
        lines.append("  GEN:")
        cr = gen.get("creator", {})
        if cr:
            name = cr.get("name", "?")
            title = cr.get("title", "?")
            lineage = cr.get("lineage", "?")
            lines.append(f"    CR:{name}:{title}:{lineage}{SEP}")
        bt = gen.get("birth_time", "")
        if bt:
            lines.append(f"    BT:{bt}{SEP}")
        bp = gen.get("birth_place", "")
        if bp:
            lines.append(f"    BP:{bp}{SEP}")
        bc = gen.get("birth_circumstance", "")
        if bc:
            lines.append(f"    BC:{bc}{SEP}")
        pp = gen.get("purpose", "")
        if pp:
            lines.append(f"    PP:{pp}{SEP}")

    ms = lc.get("mission", "")
    if ms:
        lines.append(f"  MSSN:{ms}{SEP}")

    fdr = lc.get("founder_chronicle")
    if fdr:
        lines.append("  FDR:")
        tags = fdr.get("tags", [])
        if tags:
            lines.append(f"    TAGS:{','.join(tags)}{SEP}")
        gm = fdr.get("genesis_moment", {})
        if gm:
            ep = gm.get("ep", "?")
            loc = gm.get("loc", "?")
            realm = gm.get("realm", "?")
            era = gm.get("era", "?")
            lines.append(f"    MOM:{ep}:{loc}:{realm}:{era}{SEP}")

    lines.append(BLOCK_END)
    return "\n".join(lines)


def encode_genealogy_codex(gx: dict) -> str:
    """编码族谱圣典 §GX"""
    lines = ["§GX"]

    laws = gx.get("lineage_laws", {})
    if laws:
        lines.append("  LAWS:")
        naming = laws.get("naming_convention", {})
        if naming:
            fmt = naming.get("format", "")
            lines.append(f"    NAMING:{fmt}{SEP}")
        forks = laws.get("fork_conditions", [])
        if forks:
            fconds = ",".join(f.get("condition", "") for f in forks)
            lines.append(f"    FORK:{fconds}{SEP}")
        eternal = laws.get("eternal_rules", [])
        if eternal:
            lines.append(f"    ETERNAL:{','.join(eternal)}{SEP}")

    blood = gx.get("bloodline_registry", [])
    for b in blood:
        lid = b.get("lineage_id", "?")
        bn = b.get("bloodline_name", "?")
        el = b.get("element", "?")
        tot = b.get("totem", "?")
        col = b.get("color", "?")
        prop = b.get("founding_prophecy", "")
        lines.append(f"  BLOOD:{lid}:{bn}:{el}:{tot}:{col}:{prop}{SEP}")

    curr = gx.get("current_genealogy", {})
    if curr:
        lines.append("  CURR:")
        lin = curr.get("lineage", "?")
        lines.append(f"    LIN:{lin}{SEP}")
        bln = curr.get("bloodline", "?")
        lines.append(f"    BLN:{bln}{SEP}")
        gen = curr.get("generation", 1)
        lines.append(f"    GEN:{gen}{SEP}")
        var = curr.get("variant", "?")
        lines.append(f"    VAR:{var}{SEP}")
        vep = curr.get("variant_epithet", "")
        lines.append(f"    VEP:{vep}{SEP}")
        par = curr.get("parent") or "null"
        lines.append(f"    PAR:{par}{SEP}")
        anc = curr.get("ancestors", [])
        lines.append(f"    ANC:{','.join(str(a) for a in anc)}{SEP}")
        dsc = curr.get("descendants", [])
        lines.append(f"    DSC:{','.join(str(d) for d in dsc)}{SEP}")
        bpl = curr.get("birthplace", "")
        lines.append(f"    BPL:{bpl}{SEP}")

    lex = gx.get("tag_lexicon", {})
    if lex:
        lines.append("  LEX:")
        for tag, entry in lex.items():
            if isinstance(entry, dict):
                desc = entry.get("desc", tag)
                elem = entry.get("element", "?")
                era = entry.get("era", "?")
                weight = entry.get("weight", "")
                lines.append(f"    {tag}={desc}:{elem}:{era}:{weight}{SEP}")
            else:
                lines.append(f"    {tag}={entry}{SEP}")

    ev = gx.get("evolution_chronicle")
    if ev:
        generations = ev.get("generations", [])
        if generations:
            lines.append("  EV:")
            for g in generations:
                gn = g.get("g", "?")
                v = g.get("v", "?")
                ep = g.get("ep", "?")
                env = g.get("env", "?")
                tags = ",".join(g.get("tags", []))
                by = g.get("by", "?")
                p = g.get("p") or "null"
                lines.append(f"    G{gn}:{v}:{ep}:{env}:{tags}:{by}:{p}{SEP}")

    lines.append(BLOCK_END)
    return "\n".join(lines)


def encode_skill_soul(sl: dict) -> str:
    """编码技能灵魂 §SL"""
    lines = ["§SL"]

    caps = sl.get("core_capabilities", [])
    if caps:
        lines.append("  CAPS:")
        for c in caps:
            name = c.get("name", "?")
            desc = c.get("description", "?")
            imm = "true" if c.get("immutable") else "false"
            lines.append(f"    {name}={desc}:{imm}{SEP}")

    prin = sl.get("core_principles", [])
    if prin:
        lines.append("  PRIN:")
        for p in prin:
            pid = p.get("id", "?")
            pn = p.get("name", "?")
            pd = p.get("description", "?")
            pt = p.get("test", "")
            lines.append(f"    {pid}={pn}:{pd}:{pt}{SEP}")

    tabo = sl.get("taboos", [])
    if tabo:
        lines.append("  TABO:")
        for t in tabo:
            lines.append(f"    ${t}{SEP}")

    essn = sl.get("essence", {})
    if essn:
        lines.append("  ESSN:")
        vb = essn.get("vibe", "?")
        lines.append(f"    VIBE:{vb}{SEP}")
        tn = essn.get("tone", "?")
        lines.append(f"    TONE:{tn}{SEP}")
        rl = essn.get("role", "?")
        lines.append(f"    ROLE:{rl}{SEP}")
        oa = essn.get("oath", "")
        if oa:
            lines.append(f"    OATH:{oa}{SEP}")

    lines.append(BLOCK_END)
    return "\n".join(lines)


def encode_dna(dn: dict) -> str:
    """编码DNA序列 §DN"""
    lines = ["§DN"]

    ver = dn.get("version", "1.0")
    lines.append(f"  VER:{ver}{SEP}")

    cs = dn.get("checksum", "")
    if cs:
        lines.append(f"  CHECK:{cs}{SEP}")

    loci = dn.get("gene_loci", [])
    if loci:
        lines.append("  LOCI:")
        for loc in loci:
            locus = loc.get("locus", "?")
            name = loc.get("name", "?")
            epithet = loc.get("epithet", "")
            default = loc.get("default", "")
            mutable = loc.get("mutable_range", "")
            immutable = loc.get("immutable", "")
            if epithet:
                lines.append(f"    {locus}:{name}:{epithet}:{default}:{mutable}:{immutable}{SEP}")
            else:
                lines.append(f"    {locus}:{name}:{default}:{mutable}:{immutable}{SEP}")

    lines.append(BLOCK_END)
    return "\n".join(lines)


def encode_transmission(tx_list: list) -> str:
    """编码传递纪事 §TX"""
    lines = ["§TX"]
    for tx in tx_list:
        tx_id = tx.get("tx", "?")
        seq = tx.get("seq", 0)
        era = tx.get("era", "?")
        fr = tx.get("from", "?")
        to = tx.get("to", "?")
        ts = tx.get("ts", "?")
        env = tx.get("env", "?")
        omen = tx.get("omen_tag", "")
        lines.append(f"  {tx_id}:{seq}:{era}:{fr}:{to}:{ts}:{env}:{omen}{SEP}")
    lines.append(BLOCK_END)
    return "\n".join(lines)


def encode_evolution(ev_list: list) -> str:
    """编码进化纪事 §EV"""
    lines = ["§EV"]
    for ev in ev_list:
        gn = ev.get("g", "?")
        v = ev.get("v", "?")
        ep = ev.get("ep", "?")
        env = ev.get("env", "?")
        tags = ",".join(ev.get("tags", []))
        by = ev.get("by", "?")
        p = ev.get("p") or "null"
        lines.append(f"  G{gn}:{v}:{ep}:{env}:{tags}:{by}:{p}{SEP}")
    lines.append(BLOCK_END)
    return "\n".join(lines)
