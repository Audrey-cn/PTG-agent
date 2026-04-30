#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║   🧠 普罗米修斯 · 上下文管理器 · Context Manager            ║
║                                                              ║
║   三层记忆模型：                                              ║
║     工作记忆（working）  — 当前任务上下文                    ║
║     情景记忆（episodic） — 近期交互，随时间衰减              ║
║     长期记忆（longterm） — 稳定事实，持久保存                ║
║                                                              ║
║   基于混合存储层实现，支持 MD 文件和 SQLite                  ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import math
import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

from .storage import HybridStorage, MemoryRecord


class MemoryLayer(Enum):
    WORKING = "working"
    EPISODIC = "episodic"
    LONGTERM = "longterm"


@dataclass
class MemoryUnit:
    """记忆单元——信息的最小存储单位"""
    content: str
    source: str = "unknown"
    importance: float = 0.5
    layer: str = "working"
    created_at: str = ""
    accessed_at: str = ""
    access_count: int = 0
    decay_rate: float = 0.01
    tags: List[str] = field(default_factory=list)
    token_estimate: int = 0

    def __post_init__(self):
        now = datetime.datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.accessed_at:
            self.accessed_at = now
        if self.token_estimate == 0:
            self.token_estimate = estimate_tokens(self.content)

    def effective_importance(self) -> float:
        """计算当前有效重要性（随时间衰减）"""
        if self.layer == MemoryLayer.LONGTERM.value:
            return self.importance

        try:
            created = datetime.datetime.fromisoformat(self.created_at)
            days_elapsed = (datetime.datetime.now() - created).days
            decay = math.exp(-self.decay_rate * days_elapsed)
            floor = 0.1 if self.layer == MemoryLayer.EPISODIC.value else 0.05
            return max(self.importance * decay, floor)
        except (ValueError, TypeError):
            return self.importance

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "MemoryUnit":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数（中文约1.5字/token，英文约4字符/token）"""
    if not text:
        return 0
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars * 1.5 + other_chars / 4)


class ContextManager:
    """上下文管理器 - 三层记忆系统
    
    管理三层记忆：工作记忆、情景记忆、长期记忆。
    支持预算控制、重要性衰减、自动压缩和检索。
    """
    
    DEFAULT_BUDGET = {
        MemoryLayer.WORKING.value: 8000,
        MemoryLayer.EPISODIC.value: 16000,
        MemoryLayer.LONGTERM.value: 32000,
    }
    
    EPISODIC_COMPRESS_THRESHOLD = 50
    
    def __init__(self, data_dir: str = None, db_path: str = None, budget: dict = None,
                 state_file: str = None):
        """
        Args:
            data_dir: 数据目录
            db_path: SQLite 数据库路径
            budget: 每层 token 预算覆盖
            state_file: 持久化文件路径（保留兼容，不再使用）
        """
        self.storage = HybridStorage(data_dir=data_dir, db_path=db_path)
        self.budget = {**self.DEFAULT_BUDGET, **(budget or {})}
        self._memories_cache: Dict[str, List[MemoryUnit]] = {
            MemoryLayer.WORKING.value: [],
            MemoryLayer.EPISODIC.value: [],
            MemoryLayer.LONGTERM.value: [],
        }
        self._cache_loaded = False
    
    def _ensure_cache_loaded(self):
        """确保缓存已加载"""
        if self._cache_loaded:
            return
        
        for layer in MemoryLayer:
            records = self.storage.list_by_layer(layer.value, limit=10000)
            for r in records:
                unit = MemoryUnit(
                    content=r.content,
                    source=r.source,
                    importance=r.importance,
                    layer=r.layer,
                    created_at=r.created_at,
                    accessed_at=r.accessed_at or r.created_at,
                    access_count=r.access_count,
                    decay_rate=r.metadata.get('decay_rate', 0.01) if r.metadata else 0.01,
                    tags=r.tags,
                    token_estimate=r.token_estimate,
                )
                self._memories_cache[layer.value].append(unit)
        self._cache_loaded = True
    
    def _sync_cache_to_storage(self):
        """将缓存同步到存储"""
        for layer in ["working", "episodic", "longterm"]:
            records = self.storage.list_by_layer(layer, limit=10000)
            for r in records:
                self.storage.delete(r.memory_id)
        
        for layer, units in self._memories_cache.items():
            for unit in units:
                record = MemoryRecord(
                    memory_id="",
                    content=unit.content,
                    layer=unit.layer,
                    importance=unit.importance,
                    source=unit.source,
                    tags=unit.tags,
                    metadata={
                        "decay_rate": unit.decay_rate,
                    },
                )
                self.storage.save(record)

    def add(self, content: str, layer: str = "working",
            importance: float = 0.5, source: str = "task",
            tags: List[str] = None, **metadata) -> dict:
        """添加记忆条目
        
        Args:
            content: 信息内容
            layer: 目标层级（working/episodic/longterm）
            importance: 重要性 0.0-1.0
            source: 来源标记
            tags: 检索标签
            
        Returns:
            {id, layer, token_estimate, budget_usage}
        """
        self._ensure_cache_loaded()
        
        if layer not in self._memories_cache:
            return {"error": f"无效的记忆层级: {layer}"}

        unit = MemoryUnit(
            content=content,
            source=source,
            importance=min(max(importance, 0.0), 1.0),
            layer=layer,
            tags=tags or [],
        )

        self._enforce_budget(layer)
        self._memories_cache[layer].append(unit)
        self._sync_cache_to_storage()

        return {
            "id": f"mem_{len(unit.content)}",
            "layer": layer,
            "token_estimate": unit.token_estimate,
            "budget_usage": self.budget_status(),
        }

    def recall(self, query: str = None, layer: str = None,
               top_k: int = 10, min_importance: float = 0.0) -> List[dict]:
        """检索记忆
        
        Args:
            query: 搜索关键词（None 返回所有，按重要性排序）
            layer: 限定层级（None 搜索所有层级）
            top_k: 返回条数
            min_importance: 最低有效重要性阈值
            
        Returns:
            [{content, source, importance, layer, created_at, tags}]
        """
        self._ensure_cache_loaded()
        
        candidates = []
        layers = [layer] if layer else list(self._memories_cache.keys())

        for l in layers:
            for unit in self._memories_cache.get(l, []):
                eff = unit.effective_importance()
                if eff < min_importance:
                    continue

                score = eff
                if query:
                    query_lower = query.lower()
                    content_lower = unit.content.lower()
                    tag_match = any(query_lower in t.lower() for t in unit.tags)
                    content_match = query_lower in content_lower

                    if not content_match and not tag_match:
                        continue

                    score = eff * 1.5
                    if tag_match:
                        score *= 1.2
                    if content_match:
                        score *= 1.1

                candidates.append({
                    "content": unit.content,
                    "source": unit.source,
                    "importance": round(unit.effective_importance(), 3),
                    "base_importance": unit.importance,
                    "layer": unit.layer,
                    "created_at": unit.created_at,
                    "tags": unit.tags,
                    "token_estimate": unit.token_estimate,
                    "_score": score,
                })

        candidates.sort(key=lambda x: x["_score"], reverse=True)
        results = candidates[:top_k]

        for r in results:
            for l in layers:
                for unit in self._memories_cache.get(l, []):
                    if unit.content == r["content"]:
                        unit.access_count += 1
                        unit.accessed_at = datetime.datetime.now().isoformat()
                        break

        self._sync_cache_to_storage()

        for r in results:
            r.pop("_score", None)

        return results

    def promote(self, content: str = None, from_layer: str = "episodic",
                to_layer: str = "longterm", min_importance: float = 0.7,
                memory_id: str = None) -> dict:
        """将记忆从低层提升到高层
        
        Args:
            content: 指定提升某条内容（None 则按重要性自动提升）
            from_layer: 源层级
            to_layer: 目标层级
            min_importance: 最低有效重要性阈值
            memory_id: 兼容新版参数（指定 memory_id）
            
        Returns:
            {promoted: int, details: [...]} 或 bool（使用 memory_id 时）
        """
        self._ensure_cache_loaded()
        
        if memory_id:
            records = self.storage.list_by_layer(from_layer, limit=10000)
            for r in records:
                if r.memory_id == memory_id:
                    r.layer = to_layer
                    self.storage.save(r)
                    return True
            return False
        
        promoted = []
        remaining = []

        for unit in self._memories_cache.get(from_layer, []):
            eff = unit.effective_importance()
            should_promote = False

            if content and content in unit.content:
                should_promote = True
            elif not content and eff >= min_importance:
                should_promote = True

            if should_promote:
                unit.layer = to_layer
                self._memories_cache[to_layer].append(unit)
                promoted.append({
                    "content": unit.content[:50] + "..." if len(unit.content) > 50 else unit.content,
                    "importance": round(eff, 3),
                    "access_count": unit.access_count,
                })
            else:
                remaining.append(unit)

        self._memories_cache[from_layer] = remaining
        self._sync_cache_to_storage()

        return {"promoted": len(promoted), "details": promoted}

    def compress_episodic(self, keep_recent: int = 20) -> dict:
        """压缩情景记忆——将旧的、低重要性的条目清理掉
        
        保留策略：
          1. 最近 keep_recent 条始终保留
          2. 重要性 > 0.7 的始终保留
          3. 其余按重要性排序，保留前 50%
          
        Returns:
            {before: int, after: int, compressed: int}
        """
        self._ensure_cache_loaded()
        
        episodic = self._memories_cache[MemoryLayer.EPISODIC.value]
        before = len(episodic)

        if before <= keep_recent:
            return {"before": before, "after": before, "compressed": 0}

        episodic.sort(key=lambda u: u.created_at, reverse=True)

        recent = episodic[:keep_recent]
        old = episodic[keep_recent:]

        preserved = [u for u in old if u.effective_importance() >= 0.7]
        discarded = [u for u in old if u.effective_importance() < 0.7]

        discarded.sort(key=lambda u: u.effective_importance(), reverse=True)
        keep_count = len(discarded) // 2
        more_preserved = discarded[:keep_count]
        truly_discarded = discarded[keep_count:]

        self._memories_cache[MemoryLayer.EPISODIC.value] = recent + preserved + more_preserved
        after = len(self._memories_cache[MemoryLayer.EPISODIC.value])
        self._sync_cache_to_storage()

        return {
            "before": before,
            "after": after,
            "compressed": before - after,
            "discarded_content_hints": [
                d.content[:30] + "..." for d in truly_discarded[:5]
            ],
        }

    def budget_status(self) -> dict:
        """当前各层 token 预算使用情况
        
        Returns:
            {working: {used, budget, pct}, episodic: {...}, longterm: {...}, total: {...}}
        """
        self._ensure_cache_loaded()
        
        status = {}
        total_used = 0
        total_budget = 0

        for layer_name in [MemoryLayer.WORKING.value, MemoryLayer.EPISODIC.value, MemoryLayer.LONGTERM.value]:
            units = self._memories_cache.get(layer_name, [])
            used = sum(u.token_estimate for u in units)
            budget = self.budget.get(layer_name, 0)
            total_used += used
            total_budget += budget

            status[layer_name] = {
                "used": used,
                "budget": budget,
                "pct": round(used / budget * 100, 1) if budget > 0 else 0,
                "count": len(units),
            }

        status["total"] = {
            "used": total_used,
            "budget": total_budget,
            "pct": round(total_used / total_budget * 100, 1) if total_budget > 0 else 0,
        }

        return status

    def snapshot(self) -> dict:
        """导出完整记忆状态"""
        self._ensure_cache_loaded()
        return {
            "memories": {
                layer: [u.to_dict() for u in units]
                for layer, units in self._memories_cache.items()
            },
            "budget": self.budget,
            "timestamp": datetime.datetime.now().isoformat(),
        }

    def restore(self, state: dict) -> dict:
        """从快照恢复记忆状态"""
        if "memories" not in state:
            return {"error": "无效的状态快照"}

        for layer, units in state["memories"].items():
            if layer in self._memories_cache:
                self._memories_cache[layer] = [MemoryUnit.from_dict(u) for u in units]

        self.budget = state.get("budget", self.budget)
        self._sync_cache_to_storage()

        return {"restored": True, "layers": list(self._memories_cache.keys())}

    def clear(self, layer: str = None) -> dict:
        """清空记忆
        
        Args:
            layer: 指定层级（None 则全部清空）
        """
        self._ensure_cache_loaded()
        
        if layer:
            if layer in self._memories_cache:
                count = len(self._memories_cache[layer])
                self._memories_cache[layer] = []
                self._sync_cache_to_storage()
                return {"cleared": layer, "count": count}
            return {"error": f"无效层级: {layer}"}
        else:
            total = sum(len(units) for units in self._memories_cache.values())
            for layer in self._memories_cache:
                self._memories_cache[layer] = []
            self._sync_cache_to_storage()
            return {"cleared": "all", "count": total}

    def summary(self) -> dict:
        """记忆概览"""
        budget = self.budget_status()
        return {
            "working": f"{budget['working']['count']}条 · {budget['working']['used']}tok ({budget['working']['pct']}%)",
            "episodic": f"{budget['episodic']['count']}条 · {budget['episodic']['used']}tok ({budget['episodic']['pct']}%)",
            "longterm": f"{budget['longterm']['count']}条 · {budget['longterm']['used']}tok ({budget['longterm']['pct']}%)",
            "total": f"{budget['total']['used']}/{budget['total']['budget']}tok ({budget['total']['pct']}%)",
        }

    def search(self, query: str, limit: int = 10) -> List[MemoryUnit]:
        """全文搜索记忆（使用 SQLite FTS，支持中英文子串匹配）

        Args:
            query: 搜索关键词
            limit: 最大返回条数

        Returns:
            匹配的 MemoryUnit 列表
        """
        records = self.storage.search(query, limit=limit)
        units = []
        for r in records:
            meta = r.metadata or {}
            units.append(MemoryUnit(
                content=r.content,
                source=r.source,
                importance=r.importance,
                layer=r.layer,
                created_at=r.created_at,
                accessed_at=r.accessed_at or r.created_at,
                access_count=r.access_count,
                decay_rate=meta.get('decay_rate', 0.01),
                tags=r.tags,
                token_estimate=r.token_estimate,
            ))
        return units

    def get_context_for_prompt(self, max_tokens: int = 4000, query: str = None,
                               layers: List[str] = None) -> str:
        """为提示词合成器提供 token 预算内的最优记忆片段

        策略：
        1. 按 effective_importance 降序排列所有记忆
        2. 逐条添加直到 token 预算用尽
        3. 如果有 query，优先匹配相关记忆
        4. 返回格式化的记忆文本，可直接注入 prompt

        Args:
            max_tokens: token 预算上限
            query: 搜索关键词，用于优先匹配
            layers: 限定搜索层级（None 搜索所有层级）

        Returns:
            格式化的记忆文本，可直接注入 system prompt
        """
        self._ensure_cache_loaded()
        
        target_layers = layers or list(self._memories_cache.keys())

        candidates = []
        for layer_name in target_layers:
            for unit in self._memories_cache.get(layer_name, []):
                eff = unit.effective_importance()

                score = eff
                if query:
                    query_lower = query.lower()
                    content_lower = unit.content.lower()
                    tag_match = any(query_lower in t.lower() for t in unit.tags)
                    content_match = query_lower in content_lower

                    if not content_match and not tag_match:
                        continue

                    score = eff * 1.5
                    if tag_match:
                        score *= 1.2
                    if content_match:
                        score *= 1.1

                candidates.append((unit, score))

        candidates.sort(key=lambda x: (x[1], x[0].created_at), reverse=True)

        selected = []
        remaining_tokens = max_tokens

        for unit, score in candidates:
            if unit.token_estimate <= remaining_tokens:
                selected.append(unit)
                remaining_tokens -= unit.token_estimate
            elif remaining_tokens > 20:
                truncated_content = unit.content[:int(remaining_tokens * 4)]
                selected_item = MemoryUnit(
                    content=truncated_content,
                    source=unit.source,
                    importance=unit.importance,
                    layer=unit.layer,
                    tags=unit.tags,
                )
                selected.append(selected_item)
                break

        if not selected:
            return ""

        layer_groups: Dict[str, List[MemoryUnit]] = {}
        for unit in selected:
            layer_name = unit.layer
            if layer_name not in layer_groups:
                layer_groups[layer_name] = []
            layer_groups[layer_name].append(unit)

        layer_labels = {
            "working": "工作记忆",
            "episodic": "情景记忆",
            "longterm": "长期记忆",
        }

        lines = ["## Relevant Memory Context\n"]
        total_tokens_used = 0

        for layer_name in ["working", "episodic", "longterm"]:
            units = layer_groups.get(layer_name, [])
            if not units:
                continue

            label = layer_labels.get(layer_name, layer_name)
            lines.append(f"### {label}")

            for unit in units:
                lines.append(f"- {unit.content}")
                total_tokens_used += unit.token_estimate

            lines.append("")

        lines.append(f"<!-- memory: {len(selected)} items, ~{total_tokens_used} tokens -->")

        return "\n".join(lines).strip()

    def token_budget_report(self) -> dict:
        """返回详细的 token 预算使用报告

        Returns:
            {layer: {used, available, percentage}, total: {used, available, percentage}}
        """
        status = self.budget_status()
        report = {}

        for layer_name in ["working", "episodic", "longterm"]:
            s = status.get(layer_name, {})
            used = s.get("used", 0)
            budget = s.get("budget", 0)
            report[layer_name] = {
                "used": used,
                "available": budget - used,
                "percentage": s.get("pct", 0),
                "count": s.get("count", 0),
            }

        total = status.get("total", {})
        total_used = total.get("used", 0)
        total_budget = total.get("budget", 0)
        report["total"] = {
            "used": total_used,
            "available": total_budget - total_used,
            "percentage": total.get("pct", 0),
        }

        return report

    def _enforce_budget(self, layer: str):
        """当某层超出预算时，自动迁移或清理"""
        units = self._memories_cache[layer]
        used = sum(u.token_estimate for u in units)
        budget = self.budget.get(layer, 0)

        if used <= budget:
            return

        if layer == MemoryLayer.WORKING.value:
            units.sort(key=lambda u: u.created_at)
            while used > budget * 0.8 and units:
                oldest = units.pop(0)
                oldest.layer = MemoryLayer.EPISODIC.value
                self._memories_cache[MemoryLayer.EPISODIC.value].append(oldest)
                used -= oldest.token_estimate

    def forget(self, memory_id: str) -> bool:
        """删除记忆（兼容新版）"""
        return self.storage.delete(memory_id)
