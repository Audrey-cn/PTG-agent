#!/usr/bin/env python3
"""╔══════════════════════════════════════════════════════════════╗."""

import datetime
import hashlib
import json
import os
import re
from dataclasses import dataclass, field

# ═══════════════════════════════════════════
#   配置
# ═══════════════════════════════════════════

PROMETHEUS_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROMETHEUS_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# 默认 Wiki 路径（Hermes 环境）
DEFAULT_WIKI_PATHS = [
    os.path.expanduser("~/.hermes/local-wiki/wiki"),
    os.path.expanduser("~/.hermes/knowledge"),
]

# 种子搜索路径
DEFAULT_SEED_PATHS = [
    os.path.expanduser("~/.hermes/seed-vault"),
    os.path.expanduser("~/.hermes/tools/prometheus/seeds"),
]

# 本地 fallback 知识库路径
LOCAL_KB_DIR = os.path.join(DATA_DIR, "local_knowledge")
os.makedirs(LOCAL_KB_DIR, exist_ok=True)


# ═══════════════════════════════════════════
#   Wiki 连接器
# ═══════════════════════════════════════════


@dataclass
class WikiPage:
    """Wiki 页面的结构化表示。"""

    path: str  # 文件路径
    title: str = ""  # 标题（从 h1 或 filename）
    page_type: str = "unknown"  # concept / project / insight / stub
    maturity: str = "draft"  # stub / draft / reviewed / authoritative
    tags: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    date: str = ""  # 创建日期
    updated: str = ""  # 更新日期
    content: str = ""  # 正文内容（去掉 frontmatter）
    word_count: int = 0
    links: list[str] = field(default_factory=list)  # [[双向链接]]


class WikiConnector:
    """连接 Hermes Wiki，提供知识检索能力。

    功能：
      - 扫描 Wiki 目录，解析 Markdown + YAML frontmatter
      - 全文搜索（基于关键词匹配）
      - 按标签、类型、成熟度过滤
      - 提取双向链接关系
    """

    def __init__(self, wiki_paths: list[str] = None):
        """
        Args:
            wiki_paths: Wiki 目录列表，None 则使用默认 Hermes 路径
        """
        self.wiki_paths = wiki_paths or DEFAULT_WIKI_PATHS
        self._pages: dict[str, WikiPage] = {}
        self._tag_index: dict[str, list[str]] = {}  # tag → [page_paths]
        self._link_graph: dict[str, set[str]] = {}  # page → {linked_pages}
        self._connected = False
        self._connect()

    def _connect(self):
        """尝试连接 Wiki 目录。"""
        for path in self.wiki_paths:
            if os.path.isdir(path):
                self._scan_directory(path)

        if self._pages:
            self._connected = True
            self._build_indexes()

    def _scan_directory(self, directory: str):
        """递归扫描目录中的 Markdown 文件。"""
        for root, dirs, files in os.walk(directory):
            # 跳过隐藏目录和 raw 目录
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "raw"]

            for f in files:
                if not f.endswith(".md"):
                    continue
                filepath = os.path.join(root, f)
                try:
                    page = self._parse_page(filepath)
                    if page:
                        self._pages[filepath] = page
                except Exception:
                    continue  # 跳过解析失败的文件

    def _parse_page(self, filepath: str) -> WikiPage | None:
        """解析 Markdown 文件，提取 YAML frontmatter 和正文。"""
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            text = f.read()

        if not text.strip():
            return None

        page = WikiPage(path=filepath)

        # 解析 YAML frontmatter
        frontmatter = {}
        content = text

        fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
        if fm_match:
            fm_text = fm_match.group(1)
            content = fm_match.group(2)
            frontmatter = self._parse_yaml_simple(fm_text)

        # 提取字段
        page.title = frontmatter.get("title", "")
        page.page_type = frontmatter.get("type", "unknown")
        page.maturity = frontmatter.get("maturity", "draft")
        page.tags = self._ensure_list(frontmatter.get("tags", []))
        page.aliases = self._ensure_list(frontmatter.get("aliases", []))
        page.sources = self._ensure_list(frontmatter.get("sources", []))
        page.date = frontmatter.get("date", "")
        page.updated = frontmatter.get("updated", "")

        # 如果没有 title，从 h1 或文件名提取
        if not page.title:
            h1_match = re.search(r"^#\s+(.+)", content, re.MULTILINE)
            if h1_match:
                page.title = h1_match.group(1).strip()
            else:
                page.title = os.path.splitext(os.path.basename(filepath))[0]

        # 清理内容（去掉 frontmatter 残留）
        content = re.sub(r"^---.*?---\s*", "", content, flags=re.DOTALL)
        page.content = content.strip()
        page.word_count = len(page.content)

        # 提取双向链接 [[...]]
        page.links = re.findall(r"\[\[([^\]]+)\]\]", content)

        return page

    @staticmethod
    def _parse_yaml_simple(text: str) -> dict:
        """简单 YAML 解析（不依赖 PyYAML）。"""
        result = {}
        current_key = None
        current_list = None

        for line in text.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # 列表项
            if line.startswith("- ") and current_key:
                if current_list is None:
                    current_list = []
                item = line[2:].strip().strip('"').strip("'")
                current_list.append(item)
                result[current_key] = current_list
                continue

            # 键值对
            if ":" in line:
                if current_list is not None:
                    current_list = None

                key, _, val = line.partition(":")
                key = key.strip()
                val = val.strip().strip('"').strip("'")

                if not val:
                    current_key = key
                    current_list = []
                else:
                    # 检查是否是列表 [a, b, c]
                    if val.startswith("[") and val.endswith("]"):
                        items = [
                            x.strip().strip('"').strip("'")
                            for x in val[1:-1].split(",")
                            if x.strip()
                        ]
                        result[key] = items
                    else:
                        result[key] = val
                    current_key = None

        return result

    @staticmethod
    def _ensure_list(val) -> list:
        if isinstance(val, list):
            return val
        if isinstance(val, str):
            return [val]
        return []

    def _build_indexes(self):
        """构建搜索索引。"""
        for path, page in self._pages.items():
            # 标签索引
            for tag in page.tags:
                tag_lower = tag.lower()
                if tag_lower not in self._tag_index:
                    self._tag_index[tag_lower] = []
                self._tag_index[tag_lower].append(path)

            # 链接图
            self._link_graph[path] = set()
            for link in page.links:
                # 查找匹配的页面
                matched = self.find_page_by_title(link)
                if matched:
                    self._link_graph[path].add(matched)

    def find_page_by_title(self, title: str) -> str | None:
        """通过标题查找页面路径。"""
        title_lower = title.lower()
        for path, page in self._pages.items():
            if page.title.lower() == title_lower:
                return path
            if title_lower in [a.lower() for a in page.aliases]:
                return path
        return None

    def search(
        self, query: str, limit: int = 10, page_type: str = None, min_maturity: str = None
    ) -> list[dict]:
        """全文搜索 Wiki 内容。

        Args:
            query: 搜索关键词
            limit: 最大返回数
            page_type: 限定页面类型
            min_maturity: 最低成熟度（stub < draft < reviewed < authoritative）

        Returns:
            [{"path", "title", "type", "maturity", "score", "snippet"}, ...]
        """
        maturity_order = {"stub": 0, "draft": 1, "reviewed": 2, "authoritative": 3}
        min_mat = maturity_order.get(min_maturity, 0) if min_maturity else 0

        query_lower = query.lower()
        query_tokens = set(re.findall(r"[\w\u4e00-\u9fff]+", query_lower))
        results = []

        for path, page in self._pages.items():
            if page_type and page.page_type != page_type:
                continue

            mat = maturity_order.get(page.maturity, 0)
            if mat < min_mat:
                continue

            # 计算匹配分数
            score = 0
            title_lower = page.title.lower()

            # 标题匹配（高权重）
            if query_lower in title_lower:
                score += 10
            for token in query_tokens:
                if token in title_lower:
                    score += 5

            # 标签匹配
            for tag in page.tags:
                tag_l = tag.lower()
                if query_lower in tag_l:
                    score += 8
                for token in query_tokens:
                    if token in tag_l:
                        score += 3

            # 内容匹配
            content_lower = page.content.lower()
            for token in query_tokens:
                count = content_lower.count(token)
                score += min(count, 5)  # 封顶 5 分

            # 成熟度加权
            score *= 1 + mat * 0.2

            if score > 0:
                # 生成摘要片段
                snippet = self._extract_snippet(page.content, query_tokens)
                results.append(
                    {
                        "path": path,
                        "title": page.title,
                        "type": page.page_type,
                        "maturity": page.maturity,
                        "tags": page.tags,
                        "score": round(score, 2),
                        "snippet": snippet,
                    }
                )

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def _extract_snippet(
        self, content: str, query_tokens: set[str], context_chars: int = 100
    ) -> str:
        """提取包含查询词的上下文片段。"""
        content_lower = content.lower()
        best_pos = -1

        for token in query_tokens:
            pos = content_lower.find(token)
            if pos >= 0:
                best_pos = pos
                break

        if best_pos < 0:
            return content[:200] + "..." if len(content) > 200 else content

        start = max(0, best_pos - context_chars)
        end = min(len(content), best_pos + context_chars)
        snippet = content[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet += "..."
        return snippet

    def get_page(self, path: str) -> WikiPage | None:
        """获取指定页面。"""
        return self._pages.get(path)

    def get_pages_by_tag(self, tag: str) -> list[WikiPage]:
        """按标签查找页面。"""
        paths = self._tag_index.get(tag.lower(), [])
        return [self._pages[p] for p in paths if p in self._pages]

    def get_linked_pages(self, path: str) -> list[WikiPage]:
        """获取页面的双向链接目标。"""
        linked_paths = self._link_graph.get(path, set())
        return [self._pages[p] for p in linked_paths if p in self._pages]

    def list_pages(self, page_type: str = None) -> list[dict]:
        """列出所有页面。"""
        pages = []
        for path, page in self._pages.items():
            if page_type and page.page_type != page_type:
                continue
            pages.append(
                {
                    "path": path,
                    "title": page.title,
                    "type": page.page_type,
                    "maturity": page.maturity,
                    "tags": page.tags,
                    "word_count": page.word_count,
                }
            )
        return sorted(pages, key=lambda x: x["title"])

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def page_count(self) -> int:
        return len(self._pages)

    def stats(self) -> dict:
        """Wiki 统计。"""
        by_type = {}
        by_maturity = {}
        total_words = 0

        for page in self._pages.values():
            by_type[page.page_type] = by_type.get(page.page_type, 0) + 1
            by_maturity[page.maturity] = by_maturity.get(page.maturity, 0) + 1
            total_words += page.word_count

        return {
            "connected": self._connected,
            "wiki_paths": self.wiki_paths,
            "total_pages": len(self._pages),
            "by_type": by_type,
            "by_maturity": by_maturity,
            "total_words": total_words,
            "unique_tags": len(self._tag_index),
        }


# ═══════════════════════════════════════════
#   种子结构索引
# ═══════════════════════════════════════════


@dataclass
class SeedInfo:
    """种子的结构化信息。"""

    path: str  # 种子文件路径
    name: str = ""  # 种子名称
    version: str = ""  # 版本
    genes: list[dict] = field(default_factory=list)  # 基因列表
    concepts: list[str] = field(default_factory=list)  # 语义概念
    description: str = ""  # 描述
    created_at: str = ""
    updated_at: str = ""
    size_bytes: int = 0


class SeedIndex:
    """种子结构索引 —— 快速查询种子的基因/概念结构。

    功能：
      - 扫描种子文件（.ttg / .md），提取基因列表和概念
      - 建立 种子↔基因↔概念 的关系映射
      - 支持按基因名、概念名查找种子
      - 追踪种子变更历史
    """

    def __init__(self, seed_paths: list[str] = None):
        self.seed_paths = seed_paths or DEFAULT_SEED_PATHS
        self._seeds: dict[str, SeedInfo] = {}
        self._gene_index: dict[str, list[str]] = {}  # gene_id → [seed_paths]
        self._concept_index: dict[str, list[str]] = {}  # concept → [seed_paths]
        self._build_index()

    def _build_index(self):
        """扫描种子目录，构建索引。"""
        for base_path in self.seed_paths:
            if not os.path.isdir(base_path):
                continue

            for root, dirs, files in os.walk(base_path):
                dirs[:] = [d for d in dirs if not d.startswith(".")]

                for f in files:
                    if f.endswith((".ttg", ".md", ".yaml", ".yml")):
                        filepath = os.path.join(root, f)
                        try:
                            seed = self._parse_seed(filepath)
                            if seed:
                                self._seeds[filepath] = seed
                                self._index_seed(filepath, seed)
                        except Exception:
                            continue

    def _parse_seed(self, filepath: str) -> SeedInfo | None:
        """解析种子文件，提取结构信息。"""
        stat = os.stat(filepath)
        seed = SeedInfo(
            path=filepath,
            name=os.path.splitext(os.path.basename(filepath))[0],
            size_bytes=stat.st_size,
            updated_at=datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
            created_at=datetime.datetime.fromtimestamp(stat.st_ctime).isoformat(),
        )

        with open(filepath, encoding="utf-8", errors="ignore") as f:
            content = f.read()

        if not content.strip():
            return None

        # 提取 YAML frontmatter（如果有）
        fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if fm_match:
            fm_text = fm_match.group(1)
            for line in fm_text.split("\n"):
                line = line.strip()
                if line.startswith("name:"):
                    seed.name = line.split(":", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("version:"):
                    seed.version = line.split(":", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("description:"):
                    seed.description = line.split(":", 1)[1].strip().strip('"').strip("'")

        # 提取基因信息（匹配 G001-G999 模式）
        gene_pattern = re.compile(r"(G\d{3})\s*[:\-—]\s*(.+?)(?:\n|$)")
        for match in gene_pattern.finditer(content):
            gene_id = match.group(1)
            gene_name = match.group(2).strip()
            seed.genes.append({"id": gene_id, "name": gene_name})

        # 提取语义概念（从语义字典部分）
        # 匹配 "概念 → 描述" 或 "- 概念: 描述" 格式
        concept_patterns = [
            re.compile(r"^\s*[-•]\s+(.+?)\s*[→:：]\s*", re.MULTILINE),
            re.compile(r'"(.+?)"\s*→', re.MULTILINE),
        ]
        for pattern in concept_patterns:
            for match in pattern.finditer(content):
                concept = match.group(1).strip()
                if len(concept) > 1 and len(concept) < 50:
                    seed.concepts.append(concept)

        # 去重
        seed.concepts = list(dict.fromkeys(seed.concepts))

        # 如果没有描述，用前 200 字
        if not seed.description:
            # 去掉 frontmatter 和标记行
            clean = re.sub(r"^---.*?---", "", content, flags=re.DOTALL)
            clean = re.sub(r"[╔║╚═╗┐┌┐┘└├┤┬┴┼─│┬┴┼]", "", clean)
            clean = re.sub(r"\n{3,}", "\n\n", clean).strip()
            seed.description = clean[:200]

        return seed

    def _index_seed(self, path: str, seed: SeedInfo):
        """将种子信息加入索引。"""
        # 基因索引
        for gene in seed.genes:
            gid = gene["id"]
            if gid not in self._gene_index:
                self._gene_index[gid] = []
            self._gene_index[gid].append(path)

        # 概念索引
        for concept in seed.concepts:
            key = concept.lower()
            if key not in self._concept_index:
                self._concept_index[key] = []
            self._concept_index[key].append(path)

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """搜索种子（匹配名称、基因、概念、描述）。"""
        query_lower = query.lower()
        query_tokens = set(re.findall(r"[\w\u4e00-\u9fff]+", query_lower))
        results = []

        for path, seed in self._seeds.items():
            score = 0

            # 名称匹配
            if query_lower in seed.name.lower():
                score += 10

            # 基因匹配
            for gene in seed.genes:
                if query_lower in gene["id"].lower() or query_lower in gene["name"].lower():
                    score += 8
                for token in query_tokens:
                    if token in gene["name"].lower():
                        score += 3

            # 概念匹配
            for concept in seed.concepts:
                if query_lower in concept.lower():
                    score += 6
                for token in query_tokens:
                    if token in concept.lower():
                        score += 2

            # 描述匹配
            desc_lower = seed.description.lower()
            for token in query_tokens:
                score += min(desc_lower.count(token), 3)

            if score > 0:
                results.append(
                    {
                        "path": path,
                        "name": seed.name,
                        "version": seed.version,
                        "gene_count": len(seed.genes),
                        "concept_count": len(seed.concepts),
                        "score": score,
                        "description": seed.description[:100],
                    }
                )

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def get_by_gene(self, gene_id: str) -> list[SeedInfo]:
        """通过基因 ID 查找包含该基因的种子。"""
        paths = self._gene_index.get(gene_id.upper(), [])
        return [self._seeds[p] for p in paths if p in self._seeds]

    def get_by_concept(self, concept: str) -> list[SeedInfo]:
        """通过概念查找相关种子。"""
        paths = self._concept_index.get(concept.lower(), [])
        return [self._seeds[p] for p in paths if p in self._seeds]

    def list_seeds(self) -> list[dict]:
        """列出所有种子。"""
        return [
            {
                "path": s.path,
                "name": s.name,
                "version": s.version,
                "gene_count": len(s.genes),
                "concept_count": len(s.concepts),
            }
            for s in sorted(self._seeds.values(), key=lambda x: x.name)
        ]

    def stats(self) -> dict:
        return {
            "total_seeds": len(self._seeds),
            "total_genes": len(self._gene_index),
            "total_concepts": len(self._concept_index),
            "seed_paths": self.seed_paths,
        }


# ═══════════════════════════════════════════
#   本地知识库（Fallback）
# ═══════════════════════════════════════════


class LocalKnowledge:
    """本地知识库 —— Wiki 不可用时的 fallback。

    当 Prometheus 作为独立 Agent 运行且无法连接 Hermes Wiki 时，
    自动创建并使用本地知识库。

    存储格式：
      - JSON 索引文件（快速查询）
      - Markdown 内容文件（人可读）
    """

    INDEX_FILE = os.path.join(LOCAL_KB_DIR, "index.json")

    def __init__(self):
        self._entries: dict[str, dict] = {}
        os.makedirs(os.path.dirname(self.INDEX_FILE), exist_ok=True)
        self._load_index()

    def _load_index(self):
        if os.path.exists(self.INDEX_FILE):
            try:
                with open(self.INDEX_FILE, encoding="utf-8") as f:
                    self._entries = json.load(f)
            except (OSError, json.JSONDecodeError):
                self._entries = {}

    def _save_index(self):
        with open(self.INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(self._entries, f, ensure_ascii=False, indent=2)

    def add(self, title: str, content: str, tags: list[str] = None, page_type: str = "note") -> str:
        """添加一条本地知识。"""
        entry_id = hashlib.md5(title.encode()).hexdigest()[:12]
        now = datetime.datetime.now().isoformat()

        self._entries[entry_id] = {
            "title": title,
            "type": page_type,
            "tags": tags or [],
            "created_at": now,
            "updated_at": now,
            "word_count": len(content),
        }

        # 保存内容文件
        safe_name = re.sub(r"[^\w\u4e00-\u9fff-]", "_", title)[:50]
        content_path = os.path.join(LOCAL_KB_DIR, f"{entry_id}_{safe_name}.md")
        with open(content_path, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\n{content}")

        self._entries[entry_id]["path"] = content_path
        self._save_index()
        return entry_id

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """搜索本地知识库。"""
        query_lower = query.lower()
        query_tokens = set(re.findall(r"[\w\u4e00-\u9fff]+", query_lower))
        results = []

        for entry_id, entry in self._entries.items():
            score = 0

            if query_lower in entry["title"].lower():
                score += 10

            for tag in entry.get("tags", []):
                if query_lower in tag.lower():
                    score += 6

            # 读取内容文件进行搜索
            content_path = entry.get("path", "")
            if score == 0 and os.path.exists(content_path):
                try:
                    with open(content_path, encoding="utf-8") as f:
                        content = f.read().lower()
                    for token in query_tokens:
                        score += min(content.count(token), 3)
                except OSError:
                    pass

            if score > 0:
                results.append(
                    {
                        "id": entry_id,
                        "title": entry["title"],
                        "type": entry["type"],
                        "tags": entry.get("tags", []),
                        "score": score,
                    }
                )

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def count(self) -> int:
        return len(self._entries)


# ═══════════════════════════════════════════
#   统一知识管理器
# ═══════════════════════════════════════════


class KnowledgeManager:
    """Prometheus 的统一知识管理入口。

    整合 WikiConnector、SeedIndex 和 LocalKnowledge，
    提供统一的知识检索 API。

    优先级：
      1. 种子结构索引（Prometheus 自建）
      2. Hermes Wiki（通过 WikiConnector）
      3. 本地知识库（LocalKnowledge fallback）

    使用方式：
      km = KnowledgeManager()

      # 搜索知识（自动跨 Wiki + 本地）
      results = km.search("基因 G001")

      # 查询种子结构
      seeds = km.find_seeds_by_gene("G001")

      # 添加本地知识（Wiki 不可用时）
      km.add_knowledge("新概念", "概念描述...")
    """

    def __init__(
        self, wiki_paths: list[str] = None, seed_paths: list[str] = None, force_local: bool = False
    ):
        """
        Args:
            wiki_paths: 自定义 Wiki 目录
            seed_paths: 自定义种子目录
            force_local: 强制使用本地知识库（不尝试连接 Wiki）
        """
        # 种子索引（始终可用）
        self.seed_index = SeedIndex(seed_paths=seed_paths)

        # Wiki 连接
        self._wiki: WikiConnector | None = None
        self._local: LocalKnowledge | None = None
        self._force_local = force_local

        if not force_local:
            try:
                self._wiki = WikiConnector(wiki_paths=wiki_paths)
                if not self._wiki.is_connected:
                    self._wiki = None
            except Exception:
                self._wiki = None

        # Wiki 连接失败 → 使用本地知识库
        if self._wiki is None:
            self._local = LocalKnowledge()

    def search(self, query: str, limit: int = 10, source: str = "all") -> dict:
        """统一搜索 —— 跨种子 + Wiki + 本地知识库。

        Args:
            query: 搜索关键词
            limit: 每个源的最大返回数
            source: "all" / "wiki" / "seeds" / "local"

        Returns:
            {"seeds": [...], "wiki": [...], "local": [...], "total": N}
        """
        results = {"seeds": [], "wiki": [], "local": [], "total": 0}

        if source in ("all", "seeds"):
            results["seeds"] = self.seed_index.search(query, limit=limit)

        if source in ("all", "wiki") and self._wiki:
            results["wiki"] = self._wiki.search(query, limit=limit)

        if source in ("all", "local"):
            if self._local:
                results["local"] = self._local.search(query, limit=limit)
            elif self._wiki is None:
                # Wiki 不可用也没有 local 实例，创建一个
                self._local = LocalKnowledge()
                results["local"] = self._local.search(query, limit=limit)

        results["total"] = len(results["seeds"]) + len(results["wiki"]) + len(results["local"])

        return results

    def find_seeds_by_gene(self, gene_id: str) -> list[SeedInfo]:
        """通过基因 ID 查找种子。"""
        return self.seed_index.get_by_gene(gene_id)

    def find_seeds_by_concept(self, concept: str) -> list[SeedInfo]:
        """通过概念查找种子。"""
        return self.seed_index.get_by_concept(concept)

    def add_knowledge(self, title: str, content: str, tags: list[str] = None) -> str:
        """添加本地知识（写入本地知识库）。

        无论 Wiki 是否连接，都写入本地知识库。
        确保 Prometheus 始终可以积累自己的知识。
        """
        if self._local is None:
            self._local = LocalKnowledge()
        return self._local.add(title, content, tags=tags)

    def list_wiki_pages(self, page_type: str = None) -> list[dict]:
        """列出 Wiki 页面。"""
        if self._wiki:
            return self._wiki.list_pages(page_type=page_type)
        return []

    def stats(self) -> dict:
        """知识库统计。"""
        seed_stats = self.seed_index.stats()
        wiki_stats = self._wiki.stats() if self._wiki else {"connected": False, "total_pages": 0}
        local_count = self._local.count() if self._local else 0

        return {
            "wiki_connected": wiki_stats.get("connected", False),
            "wiki_pages": wiki_stats.get("total_pages", 0),
            "local_entries": local_count,
            "seeds": seed_stats["total_seeds"],
            "seed_genes": seed_stats["total_genes"],
            "seed_concepts": seed_stats["total_concepts"],
            "mode": "wiki" if self._wiki else "local",
        }

    def summary(self) -> str:
        """人类可读的知识库概览。"""
        s = self.stats()
        lines = [
            f"📚 知识管理器 · {s['mode'].upper()} 模式",
            f"  Wiki: {'✅ 已连接' if s['wiki_connected'] else '❌ 未连接'} ({s['wiki_pages']} 页)",
            f"  本地: {s['local_entries']} 条",
            f"  种子: {s['seeds']} 个 · {s['seed_genes']} 基因 · {s['seed_concepts']} 概念",
        ]
        return "\n".join(lines)


# ═══════════════════════════════════════════
#   便捷入口
# ═══════════════════════════════════════════

_km: KnowledgeManager | None = None


def get_knowledge_manager(**kwargs) -> KnowledgeManager:
    global _km
    if _km is None:
        _km = KnowledgeManager(**kwargs)
    return _km


def search_knowledge(query: str, **kwargs) -> dict:
    return get_knowledge_manager().search(query, **kwargs)


def add_knowledge(title: str, content: str, **kwargs) -> str:
    return get_knowledge_manager().add_knowledge(title, content, **kwargs)
