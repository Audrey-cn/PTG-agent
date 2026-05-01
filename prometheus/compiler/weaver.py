#!/usr/bin/env python3
"""╔══════════════════════════════════════════════════════════════╗."""

import datetime
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Entity:
    name: str
    entity_type: str
    description: str = ""
    sources: list[str] = field(default_factory=list)


@dataclass
class Viewpoint:
    content: str
    source_id: str
    stance: str = "neutral"
    confidence: float = 0.5


@dataclass
class ClusteredViews:
    topic: str
    consensus: list[Viewpoint] = field(default_factory=list)
    divergence: list[tuple[Viewpoint, Viewpoint]] = field(default_factory=list)


@dataclass
class WovenKnowledge:
    title: str
    content: str
    entities: list[Entity] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
    created_at: str = ""


class KnowledgeWeaver:
    """知识编织器"""

    def __init__(self, knowledge_manager=None):
        self.knowledge_manager = knowledge_manager

    def distill(self, source_ids: list[str]) -> list[Entity]:
        """
        Distill 阶段：从素材中提取实体、观点、关联

        Args:
            source_ids: 素材 ID 列表

        Returns:
            提取的实体列表
        """
        entities = []

        for source_id in source_ids:
            source = self._get_source(source_id)
            if not source:
                continue

            extracted = self._extract_entities(source)
            for entity in extracted:
                entity.sources.append(source_id)
                entities.append(entity)

        merged = self._merge_entities(entities)

        logger.info(f"Distilled {len(merged)} entities from {len(source_ids)} sources")
        return merged

    def converge(self, entities: list[Entity]) -> list[ClusteredViews]:
        """
        Converge 阶段：聚类共识、发现分歧

        Args:
            entities: 实体列表

        Returns:
            聚类后的观点
        """
        clusters = defaultdict(list)

        for entity in entities:
            key = entity.name.lower()
            clusters[key].append(entity)

        results = []
        for topic, entity_list in clusters.items():
            if len(entity_list) < 2:
                continue

            cluster = ClusteredViews(topic=topic)

            viewpoints = []
            for entity in entity_list:
                vp = Viewpoint(
                    content=entity.description,
                    source_id=entity.sources[0] if entity.sources else "",
                )
                viewpoints.append(vp)

            cluster.consensus = viewpoints

            results.append(cluster)

        logger.info(f"Converged into {len(results)} clusters")
        return results

    def synthesize(self, clusters: list[ClusteredViews], title: str = None) -> WovenKnowledge:
        """
        Synthesize 阶段：生成带引用的知识

        Args:
            clusters: 聚类后的观点
            title: 知识标题

        Returns:
            编织后的知识
        """
        if not title:
            title = f"综合知识_{datetime.datetime.now().strftime('%Y%m%d')}"

        sections = []
        citations = []
        all_entities = []

        for _i, cluster in enumerate(clusters):
            section = f"## {cluster.topic}\n\n"

            for vp in cluster.consensus:
                citation_id = f"cite_{len(citations) + 1}"
                section += f"- {vp.content} [({citation_id})]\n"

                citations.append(
                    {
                        "id": citation_id,
                        "source_id": vp.source_id,
                        "content": vp.content[:100],
                    }
                )

            section += "\n"
            sections.append(section)

        content = f"# {title}\n\n"
        content += "\n".join(sections)

        content += "\n## 引用来源\n\n"
        for citation in citations:
            content += f"- (({citation['source_id']})) {citation['content']}...\n"

        return WovenKnowledge(
            title=title,
            content=content,
            entities=all_entities,
            citations=citations,
            created_at=datetime.datetime.now().isoformat(),
        )

    def weave(self, source_ids: list[str], title: str = None) -> WovenKnowledge:
        """
        完整编织流程：Distill → Converge → Synthesize

        Args:
            source_ids: 素材 ID 列表
            title: 知识标题

        Returns:
            编织后的知识
        """
        entities = self.distill(source_ids)
        clusters = self.converge(entities)
        knowledge = self.synthesize(clusters, title)

        logger.info(f"Woven knowledge: {knowledge.title}")
        return knowledge

    def _get_source(self, source_id: str) -> dict | None:
        """获取素材"""
        if self.knowledge_manager:
            return self.knowledge_manager.get_knowledge(source_id)
        return None

    def _extract_entities(self, source: dict) -> list[Entity]:
        """从素材中提取实体"""
        entities = []

        content = source.get("content", "")
        source_id = source.get("id", "")

        patterns = [
            (r"【(.+?)】", "concept"),
            (r"「(.+?)」", "term"),
            (r"《(.+?)》", "work"),
            (r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", "name"),
        ]

        for pattern, entity_type in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if len(match) > 1 and len(match) < 50:
                    entities.append(
                        Entity(
                            name=match,
                            entity_type=entity_type,
                            sources=[source_id],
                        )
                    )

        return entities

    def _merge_entities(self, entities: list[Entity]) -> list[Entity]:
        """合并相同实体"""
        merged = {}

        for entity in entities:
            key = (entity.name.lower(), entity.entity_type)
            if key in merged:
                existing = merged[key]
                existing.sources.extend(entity.sources)
                existing.sources = list(set(existing.sources))
            else:
                merged[key] = entity

        return list(merged.values())
