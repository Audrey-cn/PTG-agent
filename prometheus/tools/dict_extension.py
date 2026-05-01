#!/usr/bin/env python3
"""╔══════════════════════════════════════════════════════════════╗."""

import datetime
import hashlib
import json
import os
import re
from dataclasses import dataclass

# ═══════════════════════════════════════════
#   数据结构
# ═══════════════════════════════════════════


@dataclass
class CandidateConcept:
    """候选概念"""

    text: str  # 概念文本
    sem_id: str  # 语义ID
    score: float = 0.0  # 重要性得分
    source: str = "conversation"  # 来源
    frequency: int = 1  # 出现频率
    context: str = ""  # 上下文片段
    added: bool = False  # 是否已加入字典

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "sem_id": self.sem_id,
            "score": round(self.score, 4),
            "source": self.source,
            "frequency": self.frequency,
            "added": self.added,
        }


# ═══════════════════════════════════════════
#   概念提取器
# ═══════════════════════════════════════════


class ConceptExtractor:
    """从文本中提取候选概念"""

    # 中文停用词（高频低信息）
    STOP_WORDS_CN = {
        "的",
        "了",
        "在",
        "是",
        "我",
        "有",
        "和",
        "就",
        "不",
        "人",
        "都",
        "一",
        "一个",
        "上",
        "也",
        "很",
        "到",
        "说",
        "要",
        "去",
        "你",
        "会",
        "着",
        "没有",
        "看",
        "好",
        "自己",
        "这",
        "他",
        "她",
        "它",
        "们",
        "那",
        "能",
        "可以",
        "这个",
        "那个",
        "什么",
        "怎么",
        "为什么",
        "如果",
        "但是",
        "因为",
        "所以",
        "然后",
        "或者",
        "还是",
        "应该",
        "需要",
        "可能",
        "已经",
        "正在",
        "将要",
        "能够",
        "必须",
        "一定",
        "不要",
        "没",
    }

    # 英文停用词
    STOP_WORDS_EN = {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "can",
        "shall",
        "to",
        "of",
        "in",
        "for",
        "on",
        "with",
        "at",
        "by",
        "from",
        "as",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "between",
        "out",
        "off",
        "over",
        "under",
        "again",
        "further",
        "then",
        "once",
        "here",
        "there",
        "when",
        "where",
        "why",
        "how",
        "all",
        "both",
        "each",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "nor",
        "not",
        "only",
        "own",
        "same",
        "so",
        "than",
        "too",
        "very",
        "just",
        "but",
        "and",
        "or",
        "if",
    }

    @staticmethod
    def extract_phrases(text: str, min_len: int = 2, max_len: int = 20) -> list[str]:
        """提取有意义的短语"""
        phrases = []

        # 中文：提取连续中文字符片段
        cn_pattern = r"[\u4e00-\u9fff\u3400-\u4dbf]{2,12}"
        for match in re.finditer(cn_pattern, text):
            phrase = match.group()
            if len(phrase) >= min_len and phrase not in ConceptExtractor.STOP_WORDS_CN:
                phrases.append(phrase)

        # 英文：提取 2-4 词的名词短语
        en_pattern = r"\b[A-Za-z]+(?:\s+[A-Za-z]+){1,3}\b"
        for match in re.finditer(en_pattern, text):
            phrase = match.group().strip()
            words = phrase.lower().split()
            # 过滤全停用词
            if not all(w in ConceptExtractor.STOP_WORDS_EN for w in words):
                phrases.append(phrase)

        return phrases

    @staticmethod
    def extract_key_terms(text: str) -> list[str]:
        """提取关键术语（技术词汇、专有名词）"""
        terms = []

        # 技术术语：大写字母开头的连续词
        tech_pattern = r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b"
        for match in re.finditer(tech_pattern, text):
            terms.append(match.group())

        # 缩写词
        abbr_pattern = r"\b[A-Z]{2,6}\b"
        for match in re.finditer(abbr_pattern, text):
            terms.append(match.group())

        # 带数字的术语
        num_pattern = r"\b[A-Za-z]+\d+\b"
        for match in re.finditer(num_pattern, text):
            terms.append(match.group())

        return terms

    @staticmethod
    def extract_quoted(text: str) -> list[str]:
        """提取引号内的内容（通常是重要概念）"""
        patterns = [
            r'"([^"]+)"',  # 双引号
            r'"([^"]+)"',  # 中文双引号
            r"'([^']+)'",  # 单引号
            r"「([^」]+)」",  # 日式引号
            r"「([^」]+)」",  # 中文书名号
        ]
        results = []
        for p in patterns:
            for match in re.finditer(p, text):
                content = match.group(1).strip()
                if 2 <= len(content) <= 50:
                    results.append(content)
        return results


# ═══════════════════════════════════════════
#   字典自扩展引擎
# ═══════════════════════════════════════════


class DictAutoExtension:
    """语义字典自扩展引擎

    设计哲学：
      字典随种子走——扩展后的字典写回种子文件，
      Prometheus 不额外存储字典副本。
    """

    def __init__(self, existing_ids: set[str] = None, existing_texts: set[str] = None):
        """
        Args:
            existing_ids: 已有的语义ID集合
            existing_texts: 已有的概念文本集合
        """
        self._existing_ids = existing_ids or set()
        self._existing_texts = existing_texts or set()
        self._candidates: list[CandidateConcept] = []
        self._extractor = ConceptExtractor()

    def load_existing(self, dictionary):
        """从 SemanticDictionary 加载已有概念"""
        if hasattr(dictionary, "entries"):
            for sem_id, entry in dictionary.entries.items():
                self._existing_ids.add(sem_id)
                text = entry.get("text", "")
                if text:
                    self._existing_texts.add(text.lower())

    def scan_text(self, text: str, source: str = "conversation") -> list[CandidateConcept]:
        """扫描文本，提取候选概念"""
        candidates = []

        # 1. 提取短语
        phrases = self._extractor.extract_phrases(text)
        for phrase in phrases:
            if phrase.lower() not in self._existing_texts:
                sem_id = self._generate_id(phrase)
                if sem_id not in self._existing_ids:
                    freq = text.count(phrase)
                    candidates.append(
                        CandidateConcept(
                            text=phrase,
                            sem_id=sem_id,
                            source=source,
                            frequency=freq,
                            context=self._get_context(text, phrase),
                        )
                    )

        # 2. 提取关键术语
        terms = self._extractor.extract_key_terms(text)
        for term in terms:
            if term.lower() not in self._existing_texts:
                sem_id = self._generate_id(term)
                if sem_id not in self._existing_ids:
                    candidates.append(
                        CandidateConcept(
                            text=term,
                            sem_id=sem_id,
                            source=source,
                            frequency=text.count(term),
                        )
                    )

        # 3. 提取引号内容
        quoted = self._extractor.extract_quoted(text)
        for phrase in quoted:
            if phrase.lower() not in self._existing_texts:
                sem_id = self._generate_id(phrase)
                if sem_id not in self._existing_ids:
                    candidates.append(
                        CandidateConcept(
                            text=phrase,
                            sem_id=sem_id,
                            source=source,
                            frequency=1,
                            context=self._get_context(text, phrase),
                        )
                    )

        # 去重
        seen = set()
        unique = []
        for c in candidates:
            key = c.text.lower()
            if key not in seen:
                seen.add(key)
                unique.append(c)

        self._candidates.extend(unique)
        return unique

    def scan_messages(self, messages: list[dict]) -> list[CandidateConcept]:
        """扫描对话消息列表"""
        all_candidates = []
        for msg in messages:
            content = msg.get("content", "")
            role = msg.get("role", "unknown")
            if content:
                candidates = self.scan_text(content, source=f"message:{role}")
                all_candidates.extend(candidates)
        return all_candidates

    def rank(self) -> list[CandidateConcept]:
        """按重要性排序候选概念"""
        for c in self._candidates:
            score = 0.0

            # 频率加分
            score += min(c.frequency * 0.1, 0.3)

            # 长度加分（适中的长度更好）
            text_len = len(c.text)
            if 4 <= text_len <= 12:
                score += 0.2
            elif 2 <= text_len <= 20:
                score += 0.1

            # 引号内容加分（被强调的概念）
            if c.context and ('"' in c.context or '"' in c.context):
                score += 0.2

            # 技术术语加分
            if re.search(r"[A-Z][a-z]+[A-Z]", c.text):
                score += 0.15

            # 来源加分
            if "user" in c.source:
                score += 0.1

            c.score = min(score, 1.0)

        self._candidates.sort(key=lambda x: x.score, reverse=True)
        return self._candidates

    def filter_candidates(
        self,
        min_score: float = 0.2,
        max_count: int = 10,
    ) -> list[CandidateConcept]:
        """过滤和截取候选概念"""
        ranked = self.rank()
        filtered = [c for c in ranked if c.score >= min_score and not c.added]
        return filtered[:max_count]

    def add_to_dict(self, dictionary, concept: CandidateConcept) -> bool:
        """将概念加入语义字典"""
        if concept.sem_id in self._existing_ids:
            return False

        # 添加到字典
        dictionary.entries[concept.sem_id] = {
            "text": concept.text,
            "type": "concept",
            "desc": f"自动扩展: {concept.text}",
            "source": concept.source,
            "added_at": datetime.datetime.now().isoformat(),
        }
        dictionary._rebuild_index()

        # 更新追踪
        self._existing_ids.add(concept.sem_id)
        self._existing_texts.add(concept.text.lower())
        concept.added = True

        return True

    def batch_add(self, dictionary, concepts: list[CandidateConcept] = None) -> int:
        """批量添加候选概念"""
        if concepts is None:
            concepts = self.filter_candidates()

        added = 0
        for c in concepts:
            if self.add_to_dict(dictionary, c):
                added += 1

        return added

    # ── 导出 ────────────────────────────────────

    def export_changes(self) -> list[dict]:
        """导出本次扩展的变更"""
        return [c.to_dict() for c in self._candidates if c.added]

    def summary(self) -> dict:
        """扩展摘要"""
        added = [c for c in self._candidates if c.added]
        pending = [c for c in self._candidates if not c.added and c.score >= 0.2]
        return {
            "total_scanned": len(self._candidates),
            "added": len(added),
            "pending": len(pending),
            "added_concepts": [c.text for c in added],
            "top_pending": [c.to_dict() for c in pending[:5]],
        }

    # ── 内部工具 ────────────────────────────────

    @staticmethod
    def _generate_id(text: str) -> str:
        """从文本生成语义ID"""
        # 尝试生成有意义的 ID
        # 中文：取拼音首字母或哈希
        clean = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]", "", text)
        if len(clean) <= 16:
            return clean.lower()
        # 太长则用哈希
        h = hashlib.md5(text.encode()).hexdigest()[:8]
        return f"auto_{h}"

    @staticmethod
    def _get_context(text: str, phrase: str, window: int = 40) -> str:
        """获取短语的上下文"""
        idx = text.find(phrase)
        if idx == -1:
            return ""
        start = max(0, idx - window)
        end = min(len(text), idx + len(phrase) + window)
        context = text[start:end]
        if start > 0:
            context = "..." + context
        if end < len(text):
            context = context + "..."
        return context


# ═══════════════════════════════════════════
#   种子字典更新器
# ═══════════════════════════════════════════


def update_seed_dict(seed_path: str, new_concepts: list[dict]) -> bool:
    """将新概念写入种子文件的 tag_lexicon"""
    try:
        import yaml
    except ImportError:
        return False

    path = os.path.expanduser(seed_path)
    if not os.path.exists(path):
        return False

    with open(path, encoding="utf-8") as f:
        content = f.read()

    # 找到 genealogy_codex 中的 tag_lexicon 块
    # 在 tag_lexicon 的最后一个条目后追加新概念
    lines = content.split("\n")
    new_lines = []
    in_lexicon = False
    inserted = False

    for i, line in enumerate(lines):
        new_lines.append(line)

        # 检测 tag_lexicon 的最后一个条目
        if "tag_lexicon:" in line and not in_lexicon:
            in_lexicon = True

        # 在 tag_lexicon 区域的最后一个条目后插入
        if in_lexicon and not inserted:
            # 检查下一行是否缩进减少（表示离开 tag_lexicon）
            next_indent = (
                len(lines[i + 1]) - len(lines[i + 1].lstrip()) if i + 1 < len(lines) else 0
            )
            current_indent = len(line) - len(line.lstrip())
            if next_indent <= current_indent and line.strip().startswith("}"):
                # 插入新概念
                for concept in new_concepts:
                    sem_id = concept.get("sem_id", concept.get("id", ""))
                    text = concept.get("text", "")
                    new_lines.append(
                        f'  {sem_id}:       {{desc: "{text}", element: "auto_extended"}}'
                    )
                inserted = True

    if inserted:
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(new_lines))
        return True

    return False


# ═══════════════════════════════════════════
#   便捷函数
# ═══════════════════════════════════════════


def auto_extend(dictionary, text: str, min_score: float = 0.2) -> dict:
    """一步完成：扫描文本 + 过滤 + 添加到字典"""
    engine = DictAutoExtension()
    engine.load_existing(dictionary)
    engine.scan_text(text)
    engine.batch_add(dictionary, engine.filter_candidates(min_score=min_score))
    return engine.summary()


# ═══════════════════════════════════════════
#   CLI 入口
# ═══════════════════════════════════════════


def main():
    import argparse

    parser = argparse.ArgumentParser(description="语义字典自扩展")
    parser.add_argument("command", choices=["scan", "summary", "export"], help="操作命令")
    parser.add_argument("--text", help="扫描的文本")
    parser.add_argument("--file", help="扫描的文本文件")
    parser.add_argument("--min-score", type=float, default=0.2, help="最低得分阈值")

    args = parser.parse_args()

    engine = DictAutoExtension()

    if args.command == "scan":
        text = args.text or ""
        if args.file and os.path.exists(args.file):
            with open(args.file) as f:
                text = f.read()

        if not text:
            print("❌ 需要提供 --text 或 --file")
            return

        candidates = engine.scan_text(text)
        engine.rank()
        filtered = engine.filter_candidates(min_score=args.min_score)

        print("📊 扫描结果:")
        print(f"  候选概念: {len(candidates)} 个")
        print(f"  通过筛选: {len(filtered)} 个")
        print()

        for c in filtered:
            print(f"  @{c.sem_id}: {c.text}")
            print(f"    得分: {c.score:.2f} | 频率: {c.frequency} | 来源: {c.source}")
            if c.context:
                print(f"    上下文: {c.context[:60]}...")
            print()

    elif args.command == "summary":
        print(json.dumps(engine.summary(), ensure_ascii=False, indent=2))

    elif args.command == "export":
        changes = engine.export_changes()
        print(json.dumps(changes, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
