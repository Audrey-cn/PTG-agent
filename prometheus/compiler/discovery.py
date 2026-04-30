#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║   🔍 普罗米修斯 · 自动发现 · Auto Discovery                  ║
║                                                              ║
║   跨领域知识关联发现：                                        ║
║     - 扫描遗忘的素材                                         ║
║     - 发现跨领域弱连接                                       ║
║     - 生成洞察                                               ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import json
import re
import logging
import datetime
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Connection:
    source_a: str
    source_b: str
    connection_type: str
    strength: float
    evidence: str = ""


@dataclass
class Insight:
    insight_id: str
    title: str
    content: str
    connections: List[Connection] = field(default_factory=list)
    created_at: str = ""


class AutoDiscovery:
    """自动发现知识关联"""
    
    def __init__(self, knowledge_manager=None, source_dir: str = None):
        self.knowledge_manager = knowledge_manager
        self.source_dir = source_dir or os.path.expanduser(
            "~/.prometheus/memory/data/knowledge/source"
        )
        
        self._keywords_cache: Dict[str, Set[str]] = {}
    
    def patrol(self, min_age_days: int = 14) -> List[dict]:
        """
        扫描遗忘的素材
        
        Args:
            min_age_days: 最小天数
            
        Returns:
            遗忘的素材列表
        """
        forgotten = []
        now = datetime.datetime.now()
        
        if not os.path.exists(self.source_dir):
            return forgotten
        
        for filepath in Path(self.source_dir).glob("*.md"):
            stat = os.stat(filepath)
            mtime = datetime.datetime.fromtimestamp(stat.st_mtime)
            age_days = (now - mtime).days
            
            if age_days >= min_age_days:
                forgotten.append({
                    "id": filepath.stem,
                    "path": str(filepath),
                    "age_days": age_days,
                    "last_modified": mtime.isoformat(),
                })
        
        logger.info(f"Found {len(forgotten)} forgotten sources")
        return forgotten
    
    def find_connections(self, source_ids: List[str] = None,
                         min_strength: float = 0.3) -> List[Connection]:
        """
        发现跨领域弱连接
        
        Args:
            source_ids: 指定素材 ID，None 则扫描全部
            min_strength: 最小连接强度
            
        Returns:
            发现的连接列表
        """
        if source_ids is None:
            source_ids = self._get_all_source_ids()
        
        keywords_map = {}
        for sid in source_ids:
            keywords = self._extract_keywords(sid)
            keywords_map[sid] = keywords
        
        connections = []
        checked_pairs = set()
        
        source_list = list(keywords_map.keys())
        for i, sid_a in enumerate(source_list):
            for sid_b in source_list[i+1:]:
                pair = tuple(sorted([sid_a, sid_b]))
                if pair in checked_pairs:
                    continue
                checked_pairs.add(pair)
                
                keywords_a = keywords_map[sid_a]
                keywords_b = keywords_map[sid_b]
                
                common = keywords_a & keywords_b
                if not common:
                    continue
                
                strength = len(common) / min(len(keywords_a), len(keywords_b))
                
                if strength >= min_strength:
                    connections.append(Connection(
                        source_a=sid_a,
                        source_b=sid_b,
                        connection_type="shared_keywords",
                        strength=strength,
                        evidence=", ".join(list(common)[:5]),
                    ))
        
        connections.sort(key=lambda x: x.strength, reverse=True)
        
        logger.info(f"Found {len(connections)} connections")
        return connections
    
    def crystalize_insight(self, connections: List[Connection],
                           title: str = None) -> Insight:
        """
        从连接生成洞察
        
        Args:
            connections: 连接列表
            title: 洞察标题
            
        Returns:
            生成的洞察
        """
        if not connections:
            return Insight(
                insight_id=self._generate_id(),
                title="无洞察",
                content="未发现足够的连接来生成洞察。",
                created_at=datetime.datetime.now().isoformat(),
            )
        
        if not title:
            title = f"洞察_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}"
        
        content_parts = [f"# {title}\n\n"]
        content_parts.append("## 发现的关联\n\n")
        
        for i, conn in enumerate(connections[:10]):
            content_parts.append(
                f"### 关联 {i+1}\n\n"
                f"- **素材 A**: {conn.source_a}\n"
                f"- **素材 B**: {conn.source_b}\n"
                f"- **类型**: {conn.connection_type}\n"
                f"- **强度**: {conn.strength:.2f}\n"
                f"- **证据**: {conn.evidence}\n\n"
            )
        
        content_parts.append("## 建议\n\n")
        content_parts.append(
            "基于以上关联，建议进一步探索这些素材之间的潜在联系，"
            "可能发现新的知识洞察。\n"
        )
        
        return Insight(
            insight_id=self._generate_id(),
            title=title,
            content="".join(content_parts),
            connections=connections,
            created_at=datetime.datetime.now().isoformat(),
        )
    
    def discover(self, min_age_days: int = 14,
                 min_strength: float = 0.3) -> Insight:
        """
        完整发现流程：Patrol → Find Connections → Crystalize
        
        Args:
            min_age_days: 最小天数
            min_strength: 最小连接强度
            
        Returns:
            生成的洞察
        """
        forgotten = self.patrol(min_age_days)
        
        if not forgotten:
            return Insight(
                insight_id=self._generate_id(),
                title="无需处理",
                content="未发现遗忘的素材。",
                created_at=datetime.datetime.now().isoformat(),
            )
        
        source_ids = [f["id"] for f in forgotten]
        connections = self.find_connections(source_ids, min_strength)
        insight = self.crystalize_insight(connections)
        
        logger.info(f"Generated insight: {insight.title}")
        return insight
    
    def _get_all_source_ids(self) -> List[str]:
        """获取所有素材 ID"""
        if not os.path.exists(self.source_dir):
            return []
        
        return [f.stem for f in Path(self.source_dir).glob("*.md")]
    
    def _extract_keywords(self, source_id: str) -> Set[str]:
        """从素材中提取关键词"""
        if source_id in self._keywords_cache:
            return self._keywords_cache[source_id]
        
        filepath = os.path.join(self.source_dir, f"{source_id}.md")
        if not os.path.exists(filepath):
            return set()
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        content = re.sub(r'^---.*?---', '', content, flags=re.DOTALL)
        
        words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', content.lower())
        
        stopwords = set("的了在是我有和人这中大为上个国不也子时道出会三要于下得可你年生自")
        keywords = set(w for w in words if len(w) > 1 and w not in stopwords)
        
        self._keywords_cache[source_id] = keywords
        return keywords
    
    def _generate_id(self) -> str:
        import hashlib
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = hashlib.md5(
            str(datetime.datetime.now().timestamp()).encode()
        ).hexdigest()[:6]
        return f"insight_{timestamp}_{random_suffix}"
