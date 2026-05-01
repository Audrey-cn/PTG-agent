#!/usr/bin/env python3
"""╔══════════════════════════════════════════════════════════════╗."""

import datetime
import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .storage import HybridStorage

MATURITY_LEVELS = ["draft", "initial", "reviewed", "authoritative"]


@dataclass
class KnowledgeEntry:
    entry_id: str
    title: str
    content: str
    entry_type: str = "concept"
    maturity: str = "draft"
    tags: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    word_count: int = 0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at
        if self.word_count == 0:
            self.word_count = len(self.content)


class CompiledKnowledgeManager:
    """知识管理器"""

    def __init__(self, data_dir: str = None):
        self.storage = HybridStorage(data_dir=data_dir)

        self.source_dir = os.path.join(self.storage.data_dir, "knowledge", "source")
        self.compiled_dir = os.path.join(self.storage.data_dir, "knowledge", "compiled")
        self.metadata_dir = os.path.join(self.storage.data_dir, "knowledge", "metadata")

        os.makedirs(self.source_dir, exist_ok=True)
        os.makedirs(self.compiled_dir, exist_ok=True)
        os.makedirs(self.metadata_dir, exist_ok=True)

    def add_source(
        self, content: str, title: str = None, tags: list[str] = None, source_type: str = "raw"
    ) -> str:
        """添加原始素材"""
        entry_id = self._generate_id("src")
        title = title or f"素材_{entry_id}"

        filepath = os.path.join(self.source_dir, f"{entry_id}.md")

        frontmatter = {
            "id": entry_id,
            "type": source_type,
            "title": title,
            "tags": tags or [],
            "created_at": datetime.datetime.now().isoformat(),
        }

        self._write_md(filepath, frontmatter, content)

        return entry_id

    def add_knowledge(
        self,
        title: str,
        content: str,
        entry_type: str = "concept",
        maturity: str = "draft",
        tags: list[str] = None,
        sources: list[str] = None,
    ) -> str:
        """添加编译后的知识"""
        entry_id = self._generate_id("know")

        filepath = os.path.join(self.compiled_dir, f"{entry_id}.md")

        frontmatter = {
            "id": entry_id,
            "type": entry_type,
            "title": title,
            "maturity": maturity,
            "tags": tags or [],
            "sources": sources or [],
            "created_at": datetime.datetime.now().isoformat(),
            "updated_at": datetime.datetime.now().isoformat(),
        }

        self._write_md(filepath, frontmatter, content)

        self._update_metadata(entry_id, frontmatter, content)

        return entry_id

    def get_knowledge(self, entry_id: str) -> KnowledgeEntry | None:
        """获取知识条目"""
        filepath = self._find_entry(entry_id)
        if not filepath:
            return None

        entry = self._parse_md(filepath)
        if entry:
            return KnowledgeEntry(**entry)
        return None

    def update_maturity(self, entry_id: str, new_maturity: str) -> bool:
        """更新成熟度"""
        if new_maturity not in MATURITY_LEVELS:
            return False

        filepath = self._find_entry(entry_id)
        if not filepath:
            return False

        entry = self._parse_md(filepath)
        if not entry:
            return False

        current_idx = MATURITY_LEVELS.index(entry.get("maturity", "draft"))
        new_idx = MATURITY_LEVELS.index(new_maturity)

        if new_idx != current_idx + 1:
            return False

        entry["maturity"] = new_maturity
        entry["updated_at"] = datetime.datetime.now().isoformat()

        self._write_md(filepath, entry, entry.get("content", ""))

        return True

    def add_citation(
        self, entry_id: str, source_id: str, sentence_idx: int = None, quote: str = None
    ) -> bool:
        """添加引用"""
        entry = self.get_knowledge(entry_id)
        if not entry:
            return False

        citation = {
            "source_id": source_id,
            "sentence_idx": sentence_idx,
            "quote": quote,
            "created_at": datetime.datetime.now().isoformat(),
        }

        if source_id not in entry.sources:
            entry.sources.append(source_id)

        self._save_citation(entry_id, citation)

        return True

    def search(
        self, query: str, limit: int = 10, entry_type: str = None, min_maturity: str = None
    ) -> list[dict]:
        """搜索知识"""
        results = []
        query_lower = query.lower()

        for filepath in self._iter_entries():
            entry = self._parse_md(filepath)
            if not entry:
                continue

            if entry_type and entry.get("type") != entry_type:
                continue

            if min_maturity:
                current_idx = MATURITY_LEVELS.index(entry.get("maturity", "draft"))
                min_idx = MATURITY_LEVELS.index(min_maturity)
                if current_idx < min_idx:
                    continue

            score = 0
            title = entry.get("title", "").lower()
            content = entry.get("content", "").lower()
            tags = entry.get("tags", [])

            if query_lower in title:
                score += 10
            if query_lower in content:
                score += 5
            for tag in tags:
                if query_lower in tag.lower():
                    score += 8

            if score > 0:
                results.append(
                    {
                        "id": entry.get("id"),
                        "title": entry.get("title"),
                        "type": entry.get("type"),
                        "maturity": entry.get("maturity"),
                        "tags": tags,
                        "score": score,
                        "snippet": content[:200] + "..." if len(content) > 200 else content,
                    }
                )

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def list_sources(self) -> list[dict]:
        """列出所有素材"""
        sources = []
        for filepath in Path(self.source_dir).glob("*.md"):
            entry = self._parse_md(str(filepath))
            if entry:
                sources.append(
                    {
                        "id": entry.get("id"),
                        "title": entry.get("title"),
                        "type": entry.get("type"),
                        "tags": entry.get("tags", []),
                        "created_at": entry.get("created_at"),
                    }
                )
        return sources

    def list_knowledge(self, entry_type: str = None, maturity: str = None) -> list[dict]:
        """列出所有知识"""
        knowledge = []
        for filepath in Path(self.compiled_dir).glob("*.md"):
            entry = self._parse_md(str(filepath))
            if not entry:
                continue

            if entry_type and entry.get("type") != entry_type:
                continue
            if maturity and entry.get("maturity") != maturity:
                continue

            knowledge.append(
                {
                    "id": entry.get("id"),
                    "title": entry.get("title"),
                    "type": entry.get("type"),
                    "maturity": entry.get("maturity"),
                    "tags": entry.get("tags", []),
                    "sources": entry.get("sources", []),
                    "created_at": entry.get("created_at"),
                    "updated_at": entry.get("updated_at"),
                }
            )
        return knowledge

    def stats(self) -> dict:
        """统计信息"""
        sources = self.list_sources()
        knowledge = self.list_knowledge()

        by_maturity = {}
        for k in knowledge:
            m = k.get("maturity", "draft")
            by_maturity[m] = by_maturity.get(m, 0) + 1

        by_type = {}
        for k in knowledge:
            t = k.get("type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1

        return {
            "sources": len(sources),
            "knowledge": len(knowledge),
            "by_maturity": by_maturity,
            "by_type": by_type,
        }

    def _generate_id(self, prefix: str = "entry") -> str:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = hashlib.md5(str(datetime.datetime.now().timestamp()).encode()).hexdigest()[
            :6
        ]
        return f"{prefix}_{timestamp}_{random_suffix}"

    def _write_md(self, filepath: str, frontmatter: dict, content: str):
        fm_yaml = yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"---\n{fm_yaml}---\n\n{content}")

    def _parse_md(self, filepath: str) -> dict | None:
        if not os.path.exists(filepath):
            return None

        with open(filepath, encoding="utf-8") as f:
            content = f.read()

        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", content, re.DOTALL)
        if not match:
            return None

        frontmatter = yaml.safe_load(match.group(1))
        body = match.group(2).strip()

        result = dict(frontmatter)
        result["content"] = body
        result["word_count"] = len(body)

        return result

    def _find_entry(self, entry_id: str) -> str | None:
        for directory in [self.compiled_dir, self.source_dir]:
            filepath = os.path.join(directory, f"{entry_id}.md")
            if os.path.exists(filepath):
                return filepath
        return None

    def _iter_entries(self):
        for directory in [self.compiled_dir, self.source_dir]:
            for filepath in Path(directory).glob("*.md"):
                yield str(filepath)

    def _update_metadata(self, entry_id: str, frontmatter: dict, content: str):
        index_path = os.path.join(self.metadata_dir, "index.json")

        index = {}
        if os.path.exists(index_path):
            try:
                with open(index_path, encoding="utf-8") as f:
                    index = json.load(f)
            except (OSError, json.JSONDecodeError):
                index = {}

        index[entry_id] = {
            "title": frontmatter.get("title"),
            "type": frontmatter.get("type"),
            "maturity": frontmatter.get("maturity"),
            "tags": frontmatter.get("tags", []),
            "word_count": len(content),
            "updated_at": frontmatter.get("updated_at"),
        }

        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

    def _save_citation(self, entry_id: str, citation: dict):
        citations_path = os.path.join(self.metadata_dir, "citations.json")

        citations = {}
        if os.path.exists(citations_path):
            try:
                with open(citations_path, encoding="utf-8") as f:
                    citations = json.load(f)
            except (OSError, json.JSONDecodeError):
                citations = {}

        if entry_id not in citations:
            citations[entry_id] = []

        citations[entry_id].append(citation)

        with open(citations_path, "w", encoding="utf-8") as f:
            json.dump(citations, f, ensure_ascii=False, indent=2)
