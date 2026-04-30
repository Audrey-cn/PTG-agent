#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║   📎 普罗米修斯 · 引用溯源 · Citation Tracker               ║
║                                                              ║
║   句级引用追踪：                                              ║
║     - 记录每句话的来源                                       ║
║     - 验证引用完整性                                         ║
║     - 生成引用报告                                           ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import json
import re
import logging
import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Citation:
    citation_id: str
    source_id: str
    sentence_idx: int
    sentence: str
    quote: str = ""
    created_at: str = ""


@dataclass
class CitationViolation:
    knowledge_id: str
    sentence_idx: int
    sentence: str
    issue: str


class CitationTracker:
    """引用溯源追踪器"""
    
    CITATION_PATTERN = re.compile(r'\(\(([^)]+)\)\)')
    
    def __init__(self, metadata_dir: str = None):
        self.metadata_dir = metadata_dir or os.path.expanduser(
            "~/.prometheus/memory/data/knowledge/metadata"
        )
        os.makedirs(self.metadata_dir, exist_ok=True)
        
        self.citations_file = os.path.join(self.metadata_dir, "citations.json")
        self._citations: Dict[str, List[Citation]] = {}
        self._load_citations()
    
    def _load_citations(self):
        if os.path.exists(self.citations_file):
            try:
                with open(self.citations_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for kid, citations in data.items():
                    self._citations[kid] = [
                        Citation(**c) for c in citations
                    ]
            except (json.JSONDecodeError, IOError):
                self._citations = {}
    
    def _save_citations(self):
        data = {}
        for kid, citations in self._citations.items():
            data[kid] = [
                {
                    "citation_id": c.citation_id,
                    "source_id": c.source_id,
                    "sentence_idx": c.sentence_idx,
                    "sentence": c.sentence,
                    "quote": c.quote,
                    "created_at": c.created_at,
                }
                for c in citations
            ]
        
        with open(self.citations_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def index(self, knowledge_id: str, content: str) -> int:
        """
        索引知识内容的引用
        
        Args:
            knowledge_id: 知识 ID
            content: 知识内容
            
        Returns:
            索引的引用数量
        """
        sentences = self._split_sentences(content)
        citations = []
        
        for idx, sentence in enumerate(sentences):
            matches = self.CITATION_PATTERN.findall(sentence)
            for source_id in matches:
                citation = Citation(
                    citation_id=f"cite_{knowledge_id}_{idx}_{len(citations)}",
                    source_id=source_id,
                    sentence_idx=idx,
                    sentence=sentence,
                    created_at=datetime.datetime.now().isoformat(),
                )
                citations.append(citation)
        
        self._citations[knowledge_id] = citations
        self._save_citations()
        
        logger.info(f"Indexed {len(citations)} citations for {knowledge_id}")
        return len(citations)
    
    def get_sources(self, knowledge_id: str) -> List[str]:
        """获取知识的所有来源"""
        citations = self._citations.get(knowledge_id, [])
        return list(set(c.source_id for c in citations))
    
    def get_citations(self, knowledge_id: str) -> List[Citation]:
        """获取知识的所有引用"""
        return self._citations.get(knowledge_id, [])
    
    def validate(self, knowledge_id: str, content: str) -> List[CitationViolation]:
        """
        验证引用完整性
        
        Args:
            knowledge_id: 知识 ID
            content: 知识内容
            
        Returns:
            违规列表
        """
        violations = []
        sentences = self._split_sentences(content)
        
        for idx, sentence in enumerate(sentences):
            if not sentence.strip():
                continue
            
            has_citation = bool(self.CITATION_PATTERN.search(sentence))
            
            is_statement = self._is_statement(sentence)
            
            if is_statement and not has_citation:
                violations.append(CitationViolation(
                    knowledge_id=knowledge_id,
                    sentence_idx=idx,
                    sentence=sentence[:100],
                    issue="Statement without citation",
                ))
        
        return violations
    
    def add_citation(self, knowledge_id: str, source_id: str,
                     sentence_idx: int, quote: str = "") -> str:
        """添加引用"""
        citation = Citation(
            citation_id=f"cite_{knowledge_id}_{sentence_idx}_{len(self._citations.get(knowledge_id, []))}",
            source_id=source_id,
            sentence_idx=sentence_idx,
            sentence="",
            quote=quote,
            created_at=datetime.datetime.now().isoformat(),
        )
        
        if knowledge_id not in self._citations:
            self._citations[knowledge_id] = []
        
        self._citations[knowledge_id].append(citation)
        self._save_citations()
        
        return citation.citation_id
    
    def remove_citation(self, knowledge_id: str, citation_id: str) -> bool:
        """删除引用"""
        if knowledge_id not in self._citations:
            return False
        
        citations = self._citations[knowledge_id]
        for i, c in enumerate(citations):
            if c.citation_id == citation_id:
                citations.pop(i)
                self._save_citations()
                return True
        
        return False
    
    def generate_report(self, knowledge_id: str) -> dict:
        """生成引用报告"""
        citations = self._citations.get(knowledge_id, [])
        
        by_source = {}
        for c in citations:
            if c.source_id not in by_source:
                by_source[c.source_id] = []
            by_source[c.source_id].append(c.citation_id)
        
        return {
            "knowledge_id": knowledge_id,
            "total_citations": len(citations),
            "unique_sources": len(by_source),
            "by_source": by_source,
            "citations": [
                {
                    "id": c.citation_id,
                    "source": c.source_id,
                    "sentence_idx": c.sentence_idx,
                }
                for c in citations
            ],
        }
    
    def _split_sentences(self, content: str) -> List[str]:
        """分割句子"""
        content = re.sub(r'\n+', '\n', content)
        sentences = re.split(r'[。！？\.\!\?\n]', content)
        return [s.strip() for s in sentences if s.strip()]
    
    def _is_statement(self, sentence: str) -> bool:
        """判断是否是陈述句"""
        if len(sentence) < 10:
            return False
        
        if sentence.startswith('#'):
            return False
        
        if re.match(r'^[\d\-\*\.]+\s', sentence):
            return False
        
        return True
    
    def stats(self) -> dict:
        """统计信息"""
        total = sum(len(c) for c in self._citations.values())
        
        sources = set()
        for citations in self._citations.values():
            for c in citations:
                sources.add(c.source_id)
        
        return {
            "total_citations": total,
            "total_knowledge": len(self._citations),
            "unique_sources": len(sources),
        }
