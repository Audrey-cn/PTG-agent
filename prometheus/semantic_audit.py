"""语义审核引擎 — Semantic Audit Engine."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import yaml

from prometheus.codec.layer1 import MAGIC, decode_seed
from prometheus.codec.layer2 import decode_seed_l2

FOUNDER_TAGS = [
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

FOUNDER_TAG_NORMALIZED = {t.lower().replace("-", "_").replace(" ", "_"): t for t in FOUNDER_TAGS}

FUZZY_TAG_PATTERNS = {
    "audrey_001x": re.compile(r"audrey[_\-\s]*001x", re.IGNORECASE),
    "promethean_gift": re.compile(r"promethe\w*|普罗米修斯", re.IGNORECASE),
    "engineer_craft": re.compile(r"engineer|工程师", re.IGNORECASE),
    "open_source": re.compile(r"open[_\-\s]*source|开放源代码|开源", re.IGNORECASE),
}


class SeedIdentity(Enum):
    OUR_FRAMEWORK = "our_framework"
    OUR_DESCENDANT = "our_descendant"
    FOREIGN_LINEAGE = "foreign_lineage"
    FOREIGN_RAW = "foreign_raw"
    UNKNOWN = "unknown"


@dataclass
class SeedReading:
    file_path: str
    format: str
    raw_text: str | None = None
    structured_data: dict | None = None
    fingerprints: dict[str, Any] = field(default_factory=dict)
    parse_errors: list[str] = field(default_factory=list)

    def has_structured_data(self) -> bool:
        return self.structured_data is not None and len(self.structured_data) > 0

    def get_life_crest(self) -> dict:
        if not self.has_structured_data():
            return {}
        return self.structured_data.get("life_crest", {})

    def get_founder_covenant(self) -> dict:
        life_crest = self.get_life_crest()
        return life_crest.get("founder_covenant", {})

    def get_eternal_seals(self) -> list[dict]:
        covenant = self.get_founder_covenant()
        return covenant.get("eternal_seals", [])

    def get_eternal_seal_tags(self) -> list[str]:
        seals = self.get_eternal_seals()
        return [s.get("seal", "") for s in seals if s.get("seal")]

    def get_genealogy_codex(self) -> dict:
        if not self.has_structured_data():
            return {}
        return self.structured_data.get("genealogy_codex", {})

    def get_tag_lexicon(self) -> dict:
        genea = self.get_genealogy_codex()
        return genea.get("tag_lexicon", {})

    def get_evolution_chronicle(self) -> dict:
        genea = self.get_genealogy_codex()
        return genea.get("evolution_chronicle", {})

    def get_current_genealogy(self) -> dict:
        genea = self.get_genealogy_codex()
        return genea.get("current_genealogy", {})

    def get_genesis(self) -> dict:
        life_crest = self.get_life_crest()
        return life_crest.get("genesis", {})


@dataclass
class Classification:
    identity: SeedIdentity
    confidence: float
    evidence: dict[str, Any] = field(default_factory=dict)
    narrative: str = ""

    def is_ours(self) -> bool:
        return self.identity in (SeedIdentity.OUR_FRAMEWORK, SeedIdentity.OUR_DESCENDANT)

    def requires_append(self) -> bool:
        return self.identity in (SeedIdentity.FOREIGN_LINEAGE, SeedIdentity.FOREIGN_RAW)


@dataclass
class LineageAnchor:
    has_genealogy_codex: bool
    has_evolution_chronicle: bool
    has_current_genealogy: bool
    lineage: str = "?"
    bloodline: str = "?"
    generation: int = 0
    variant: str = "?"
    parent_id: str | None = None
    ancestor_chain: list[str] = field(default_factory=list)
    description: str = ""

    def can_append_to_evolution(self) -> bool:
        return self.has_evolution_chronicle


class FormatAgnosticReader:
    """格式无关读取器 — 支持多种种子格式的自动识别与解析"""

    def read(self, file_path: str) -> SeedReading:
        if not os.path.exists(file_path):
            return SeedReading(file_path=file_path, format="not_found", parse_errors=["文件不存在"])

        try:
            with open(file_path, "rb") as f:
                raw_bytes = f.read()
        except Exception as e:
            return SeedReading(file_path=file_path, format="error", parse_errors=[f"读取失败: {e}"])

        if raw_bytes[:4] == MAGIC:
            return self._read_binary(raw_bytes, file_path)

        text = raw_bytes.decode("utf-8", errors="replace")

        if "```yaml" in text:
            reading = self._parse_markdown_yaml(text, file_path)
            if reading.has_structured_data():
                return reading

        stripped = text.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            reading = self._parse_json(text, file_path)
            if reading.has_structured_data():
                return reading

        return self._extract_from_plain_text(text, file_path)

    def _read_binary(self, raw_bytes: bytes, file_path: str) -> SeedReading:
        try:
            data = decode_seed_l2(raw_bytes)
            if data:
                return SeedReading(
                    file_path=file_path,
                    format="ttgc_l2",
                    structured_data=data,
                    fingerprints={"binary_format": "layer2"},
                )
        except Exception:
            pass

        try:
            data = decode_seed(raw_bytes)
            if data:
                return SeedReading(
                    file_path=file_path,
                    format="ttgc_l1",
                    structured_data=data,
                    fingerprints={"binary_format": "layer1"},
                )
        except Exception as e:
            return SeedReading(
                file_path=file_path, format="binary_unknown", parse_errors=[f"二进制解码失败: {e}"]
            )

        return SeedReading(file_path=file_path, format="binary_failed")

    def _parse_markdown_yaml(self, text: str, file_path: str) -> SeedReading:
        errors = []
        result = {}

        pattern = r"```yaml\s*\n(.*?)```"
        blocks = re.findall(pattern, text, re.DOTALL)

        for i, block in enumerate(blocks[:5]):
            try:
                parsed = yaml.safe_load(block)
                if parsed and isinstance(parsed, dict):
                    result.update(parsed)
            except Exception as e:
                errors.append(f"YAML块{i + 1}解析错误: {e}")

        if result:
            return SeedReading(
                file_path=file_path,
                format="markdown_yaml",
                raw_text=text,
                structured_data=result,
                parse_errors=errors,
            )

        return SeedReading(
            file_path=file_path, format="markdown_yaml_failed", raw_text=text, parse_errors=errors
        )

    def _parse_json(self, text: str, file_path: str) -> SeedReading:
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return SeedReading(
                    file_path=file_path, format="json", raw_text=text, structured_data=data
                )
        except Exception as e:
            return SeedReading(
                file_path=file_path,
                format="json_failed",
                raw_text=text,
                parse_errors=[f"JSON解析失败: {e}"],
            )

        return SeedReading(file_path=file_path, format="json_invalid")

    def _extract_from_plain_text(self, text: str, file_path: str) -> SeedReading:
        fingerprints = {
            "founder_tags_found": self._fuzzy_find_tags(text),
            "has_audrey": bool(re.search(r"audrey", text, re.IGNORECASE)),
            "has_001x": bool(re.search(r"001x", text, re.IGNORECASE)),
            "has_prometheus": bool(re.search(r"promethe|普罗米修斯", text, re.IGNORECASE)),
            "has_lineage": bool(re.search(r"lineage|genealogy|族谱|谱系", text, re.IGNORECASE)),
            "has_founder_chronicle": bool(
                re.search(r"founder.chronicle|创始铭刻", text, re.IGNORECASE)
            ),
            "has_ttg": bool(re.search(r"TTG|teach.to.grow", text, re.IGNORECASE)),
            "text_length": len(text),
        }

        return SeedReading(
            file_path=file_path, format="plain_text", raw_text=text, fingerprints=fingerprints
        )

    def _fuzzy_find_tags(self, text: str) -> list[str]:
        found = []
        text_lower = text.lower()

        for tag in FOUNDER_TAGS:
            if tag.lower() in text_lower:
                found.append(tag)
                continue

            normalized = tag.lower().replace("-", "_")
            if normalized in text_lower:
                found.append(tag)
                continue

        for tag_name, pattern in FUZZY_TAG_PATTERNS.items():
            if tag_name not in found and pattern.search(text):
                found.append(tag_name)

        return found


class SemanticAuditEngine:
    """语义审核引擎 — 身份分类与谱系定位"""

    def __init__(self):
        self.reader = FormatAgnosticReader()

    def ingest(self, file_path: str) -> SeedReading:
        return self.reader.read(file_path)

    def classify(self, reading: SeedReading) -> Classification:
        scores = {
            "founder_tags": 0.0,
            "genesis_match": 0.0,
            "framework_signature": 0.0,
            "lineage_structure": 0.0,
            "lineage_coherence": 0.0,
        }
        evidence = {}

        tags_hit, tags_total = self._check_founder_tags(reading)
        scores["founder_tags"] = (tags_hit / tags_total) * 40 if tags_total > 0 else 0
        evidence["founder_tags_hit"] = tags_hit
        evidence["founder_tags_total"] = tags_total

        genesis_match = self._check_genesis_match(reading)
        scores["genesis_match"] = 20 if genesis_match else 0
        evidence["genesis_match"] = genesis_match

        has_signature = self._check_framework_signature(reading)
        scores["framework_signature"] = 15 if has_signature else 0
        evidence["framework_signature"] = has_signature

        has_lineage = self._check_lineage_structure(reading)
        scores["lineage_structure"] = 15 if has_lineage else 0
        evidence["has_lineage_structure"] = has_lineage

        coherence = self._check_lineage_coherence(reading)
        scores["lineage_coherence"] = coherence * 10
        evidence["lineage_coherence"] = coherence

        total_score = sum(scores.values())
        evidence["scores"] = scores
        evidence["total_score"] = total_score

        identity, confidence, narrative = self._determine_identity(total_score, evidence)

        return Classification(
            identity=identity, confidence=confidence, evidence=evidence, narrative=narrative
        )

    def _check_founder_tags(self, reading: SeedReading) -> tuple[int, int]:
        if reading.has_structured_data():
            seal_tags = reading.get_eternal_seal_tags()
            if seal_tags:
                hit = sum(1 for t in FOUNDER_TAGS if t in seal_tags)
                return hit, len(FOUNDER_TAGS)

        if reading.fingerprints:
            found = reading.fingerprints.get("founder_tags_found", [])
            return len(found), len(FOUNDER_TAGS)

        return 0, len(FOUNDER_TAGS)

    def _check_genesis_match(self, reading: SeedReading) -> bool:
        if reading.has_structured_data():
            genesis = reading.get_genesis()
            birth = genesis.get("birth", {})
            if birth:
                epoch = birth.get("epoch", "")
                if epoch and epoch != "?" and "ORIGIN" not in epoch.upper():
                    return True

        return False

    def _check_framework_signature(self, reading: SeedReading) -> bool:
        if reading.raw_text:
            text = reading.raw_text
            sig_markers = [
                "Audrey · 001X",
                "普罗米修斯框架",
                "Prometheus",
                "创始印记",
                "TTG@L1-G1-ORIGIN",
            ]
            for marker in sig_markers:
                if marker in text:
                    return True

        if reading.has_structured_data():
            seal_tags = reading.get_eternal_seal_tags()
            if "audrey_001x" in seal_tags:
                return True

        return False

    def _check_lineage_structure(self, reading: SeedReading) -> bool:
        if reading.has_structured_data():
            genea = reading.get_genealogy_codex()
            life_crest = reading.get_life_crest()

            has_founder_covenant = "founder_covenant" in life_crest
            has_lineage_laws = "lineage_laws" in genea
            has_bloodline = "bloodline_registry" in genea
            has_evolution = "evolution_chronicle" in genea
            has_current = "current_genealogy" in genea
            return (
                has_founder_covenant
                or has_lineage_laws
                or has_bloodline
                or has_evolution
                or has_current
            )

        if reading.fingerprints:
            return reading.fingerprints.get("has_lineage", False)

        return False

    def _check_lineage_coherence(self, reading: SeedReading) -> float:
        if not reading.has_structured_data():
            return 0.0

        genea = reading.get_genealogy_codex()
        if not genea:
            return 0.0

        coherence = 0.0

        current = genea.get("current_genealogy", {})
        if current:
            if current.get("lineage"):
                coherence += 0.2
            if current.get("generation"):
                coherence += 0.2
            if current.get("variant"):
                coherence += 0.2
            if current.get("parent") is not None or current.get("ancestors"):
                coherence += 0.2

        evolution = genea.get("evolution_chronicle", {})
        if evolution:
            generations = evolution.get("generations", [])
            if generations and len(generations) > 0:
                coherence += 0.2

        return min(coherence, 1.0)

    def _determine_identity(self, score: float, evidence: dict) -> tuple[SeedIdentity, float, str]:
        tags_hit = evidence.get("founder_tags_hit", 0)
        tags_total = evidence.get("founder_tags_total", 10)

        if score >= 90:
            return (
                SeedIdentity.OUR_FRAMEWORK,
                min(score / 100, 1.0),
                f"我们的框架产物 — {tags_hit}/{tags_total}标签命中，签名完整",
            )
        elif score >= 50:
            return (
                SeedIdentity.OUR_DESCENDANT,
                score / 100,
                f"我们的后代种子 — {tags_hit}/{tags_total}标签命中，谱系可追溯",
            )
        elif score >= 20:
            return (
                SeedIdentity.FOREIGN_LINEAGE,
                score / 100,
                "外来种子(有族谱) — 无创始标签，但存在谱系结构",
            )
        else:
            return (
                SeedIdentity.FOREIGN_RAW,
                score / 100,
                "外来种子(无结构) — 无标签，无谱系，可能来自其他Agent",
            )

    def locate_lineage(self, reading: SeedReading) -> LineageAnchor:
        if not reading.has_structured_data():
            return self._locate_from_fingerprints(reading)

        genea = reading.get_genealogy_codex()
        current = reading.get_current_genealogy()
        evolution = reading.get_evolution_chronicle()

        anchor = LineageAnchor(
            has_genealogy_codex=bool(genea),
            has_evolution_chronicle="generations" in evolution,
            has_current_genealogy=bool(current),
        )

        if current:
            anchor.lineage = current.get("lineage", "?")
            anchor.bloodline = current.get("bloodline", "?")
            anchor.generation = current.get("generation", 0)
            anchor.variant = current.get("variant", "?")
            anchor.parent_id = current.get("parent")
            anchor.ancestor_chain = current.get("ancestors", [])

        if anchor.has_genealogy_codex:
            anchor.description = f"谱系{anchor.lineage} · {anchor.bloodline} · 第{anchor.generation}代 · {anchor.variant}变种"
        else:
            anchor.description = "无族谱结构"

        return anchor

    def _locate_from_fingerprints(self, reading: SeedReading) -> LineageAnchor:
        has_lineage = (
            reading.fingerprints.get("has_lineage", False) if reading.fingerprints else False
        )

        return LineageAnchor(
            has_genealogy_codex=False,
            has_evolution_chronicle=False,
            has_current_genealogy=False,
            description="无结构化族谱(纯文本指纹)" if has_lineage else "无族谱信息",
        )
