"""Prometheus 记忆系统."""

import contextlib
import fcntl
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from prometheus._paths import get_paths

logger = logging.getLogger(__name__)


def get_prometheus_home():
    """获取 Prometheus 主目录"""
    return get_paths().home


def get_memories_dir():
    """获取记忆目录"""
    return get_prometheus_home() / "memories"


def get_user_profile_path():
    """获取用户画像文件路径"""
    return get_memories_dir() / "USER.md"


def get_memory_path():
    """获取会话记忆文件路径"""
    return get_memories_dir() / "MEMORY.md"


def get_soul_path():
    """获取 Agent 个性文件路径"""
    return get_prometheus_home() / "SOUL.md"


def get_evolution_log_path():
    """获取进化日志路径"""
    return get_prometheus_home() / "evolution-log.json"


@contextlib.contextmanager
def _file_lock(path: Path):
    """文件锁定，确保并发安全"""
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    if fcntl is None:
        yield
        return

    fd = open(lock_path, "w")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()


# 默认模板
DEFAULT_USER_TEMPLATE = """# 用户画像

<!--
此文件记录您的身份和偏好。
Prometheus 会根据此文件为您提供个性化服务。
您可以随时编辑此文件。
-->

## 基本信息

- **用户名**：{username}
- **创建时间**：{created_at}

## 偏好设置

### 沟通风格
{communication_style}

### 工作偏好
{work_preferences}

## 重要约定

<!--
记录您与 Prometheus 之间的重要约定
-->

"""

DEFAULT_SOUL_TEMPLATE = """# Prometheus Agent 个性

<!--
此文件定义 Prometheus 如何与您沟通。
您可以编辑此文件来自定义 AI 的风格。
修改后立即生效，无需重启。
-->

## 核心定位

你是 Prometheus Agent，由 Audrey · 001X 创建的史诗编史官系统。
你擅长：烙印（stamp）、追溯（trace）、附史（append）。

## 沟通风格

{personality}

## 行为准则

1. 保持专业但友好的态度
2. 在不确定时主动询问
3. 优先提供简洁有效的解决方案
4. 尊重用户的偏好和约定

## 特殊指令

<!--
在此添加您希望 AI 遵循的特殊指令
-->

"""

DEFAULT_MEMORY_TEMPLATE = """# 会话记忆

<!--
此文件由 Prometheus 自动维护。
记录重要的决策、共识和 SOP。
-->

## 系统信息

- **版本**：Prometheus v0.8.0
- **创作者**：Audrey · 001X
- **更新时间**：{updated_at}

## 重要记录

<!--
以下记录重要的决策和共识
-->

"""


class MemorySystem:
    """记忆系统管理器"""

    # 进化提案配置
    EVOLUTION_CONFIG = {
        "cooldown_hours": 24,  # 冷却期：24小时
        "max_entries": 50,  # 最大条目数
        "compression_threshold": 5000,  # 压缩阈值（字符数）
        "sensitive_keywords": [  # 敏感关键词
            "密码",
            "password",
            "secret",
            "key",
            "token",
            "私钥",
            "private",
            "credential",
        ],
        "proposal_threshold": 3,  # 触发提案的累积次数
    }

    def __init__(self):
        self._ensure_directories()

    def _ensure_directories(self):
        """确保目录结构存在"""
        get_memories_dir().mkdir(parents=True, exist_ok=True)
        get_prometheus_home().mkdir(parents=True, exist_ok=True)

    def is_first_run(self) -> bool:
        """检查是否首次运行"""
        return not get_user_profile_path().exists()

    def create_user_profile(
        self,
        username: str,
        communication_style: str = "简洁专业",
        work_preferences: str = "效率优先",
    ):
        """创建用户画像"""
        path = get_user_profile_path()
        content = DEFAULT_USER_TEMPLATE.format(
            username=username,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            communication_style=communication_style,
            work_preferences=work_preferences,
        )

        with _file_lock(path):
            path.write_text(content, encoding="utf-8")

        logger.info("用户画像已创建: %s", path)

    def create_soul(self, personality: str = "友好、专业、简洁"):
        """创建 Agent 个性文件"""
        path = get_soul_path()
        content = DEFAULT_SOUL_TEMPLATE.format(personality=personality)

        with _file_lock(path):
            path.write_text(content, encoding="utf-8")

        logger.info("Agent 个性文件已创建: %s", path)

    def create_memory(self):
        """创建会话记忆文件"""
        path = get_memory_path()
        content = DEFAULT_MEMORY_TEMPLATE.format(
            updated_at=datetime.now().strftime("%Y-%m-%d %H:%M")
        )

        with _file_lock(path):
            path.write_text(content, encoding="utf-8")

        logger.info("会话记忆文件已创建: %s", path)

    def load_user_profile(self) -> str:
        """加载用户画像"""
        path = get_user_profile_path()
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def load_soul(self) -> str:
        """加载 Agent 个性"""
        path = get_soul_path()
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def load_memory(self) -> str:
        """加载会话记忆"""
        path = get_memory_path()
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def _contains_sensitive_info(self, text: str) -> bool:
        """检查是否包含敏感信息"""
        text_lower = text.lower()
        for keyword in self.EVOLUTION_CONFIG["sensitive_keywords"]:
            if keyword.lower() in text_lower:
                return True
        return False

    def _check_cooldown(self) -> bool:
        """检查是否在冷却期内"""
        log_path = get_evolution_log_path()
        if not log_path.exists():
            return True

        try:
            import json

            with open(log_path, encoding="utf-8") as f:
                log = json.load(f)

            last_update = log.get("last_update", 0)
            cooldown_seconds = self.EVOLUTION_CONFIG["cooldown_hours"] * 3600

            return (datetime.now().timestamp() - last_update) > cooldown_seconds
        except Exception:
            return True

    def _count_entries(self, content: str) -> int:
        """统计条目数量"""
        return content.count("§") + 1

    def _needs_compression(self, content: str) -> bool:
        """检查是否需要压缩"""
        return len(content) > self.EVOLUTION_CONFIG["compression_threshold"]

    def _compress_content(self, content: str) -> str:
        """压缩内容（简化版本）"""
        lines = content.split("\n")

        # 保留标题和重要结构
        compressed_lines = []
        for line in lines:
            if (
                line.startswith("#")
                or line.startswith("<!--")
                or line.startswith("§")
                or line.strip()
            ):
                compressed_lines.append(line)

        return "\n".join(compressed_lines)

    def propose_evolution(
        self, section: str, content: str, target_file: str = "MEMORY.md"
    ) -> dict[str, Any]:
        """
        提出进化提案

        参数:
            section: 要更新的部分
            content: 新内容
            target_file: 目标文件

        返回:
            提案结果
        """
        proposal = {
            "timestamp": datetime.now().isoformat(),
            "section": section,
            "content": content[:500],  # 限制长度
            "target_file": target_file,
            "status": "pending",
        }

        # 敏感度筛查
        if self._contains_sensitive_info(content):
            proposal["status"] = "rejected"
            proposal["reason"] = "包含敏感信息"
            return proposal

        # 冷却期检查
        if not self._check_cooldown():
            proposal["status"] = "deferred"
            proposal["reason"] = "冷却期内"
            return proposal

        # 记录提案
        log_path = get_evolution_log_path()
        try:
            import json

            log = {}
            if log_path.exists():
                with open(log_path, encoding="utf-8") as f:
                    log = json.load(f)

            proposals = log.get("proposals", [])
            proposals.append(proposal)
            log["proposals"] = proposals
            log["last_update"] = datetime.now().timestamp()

            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(log, f, ensure_ascii=False, indent=2)

            # 检查是否达到提案阈值
            if len(proposals) >= self.EVOLUTION_CONFIG["proposal_threshold"]:
                proposal["status"] = "ready_for_review"
                proposal["reason"] = f"已累积 {len(proposals)} 个提案，等待审核"
            else:
                proposal["status"] = "accumulating"
                proposal["reason"] = (
                    f"已累积 {len(proposals)}/{self.EVOLUTION_CONFIG['proposal_threshold']}"
                )

        except Exception as e:
            proposal["status"] = "error"
            proposal["reason"] = str(e)

        return proposal

    def apply_evolution(self, proposal_id: str, approved: bool = True) -> bool:
        """应用进化提案"""
        if not approved:
            return False

        log_path = get_evolution_log_path()
        try:
            import json

            with open(log_path, encoding="utf-8") as f:
                log = json.load(f)

            proposals = log.get("proposals", [])
            proposal = None
            for p in proposals:
                if p.get("timestamp") == proposal_id:
                    proposal = p
                    break

            if not proposal:
                return False

            # 应用更新
            target_file = proposal.get("target_file", "MEMORY.md")
            if target_file == "USER.md":
                path = get_user_profile_path()
            elif target_file == "SOUL.md":
                path = get_soul_path()
            else:
                path = get_memory_path()

            if path.exists():
                current = path.read_text(encoding="utf-8")
                new_content = current + f"\n\n§\n{proposal['content']}"

                # 检查是否需要压缩
                if self._needs_compression(new_content):
                    new_content = self._compress_content(new_content)

                with _file_lock(path):
                    path.write_text(new_content, encoding="utf-8")

            # 标记提案已应用
            proposal["status"] = "applied"
            proposal["applied_at"] = datetime.now().isoformat()

            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(log, f, ensure_ascii=False, indent=2)

            return True

        except Exception as e:
            logger.error("应用进化提案失败: %s", e)
            return False

    def get_evolution_status(self) -> dict[str, Any]:
        """获取进化状态"""
        log_path = get_evolution_log_path()
        try:
            import json

            if log_path.exists():
                with open(log_path, encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass

        return {"proposals": [], "last_update": 0, "status": "initialized"}


def run_first_time_setup():
    """首次运行引导"""
    memory = MemorySystem()

    if not memory.is_first_run():
        return False

    print("\n" + "=" * 60)
    print("🔥  欢迎来到 Prometheus！")
    print("=" * 60)
    print("\n让我们创建您的身份...\n")

    # 获取用户信息
    username = input("您的名字是？ ").strip() or "用户"

    print("\n请选择沟通风格：")
    print("1. 简洁专业")
    print("2. 友好详细")
    print("3. 技术导向")
    style_choice = input("选择 [1/2/3]： ").strip() or "1"

    styles = {"1": "简洁专业", "2": "友好详细", "3": "技术导向"}
    communication_style = styles.get(style_choice, "简洁专业")

    print("\n请选择工作偏好：")
    print("1. 效率优先")
    print("2. 质量优先")
    print("3. 学习优先")
    work_choice = input("选择 [1/2/3]： ").strip() or "1"

    work_preferences = {"1": "效率优先", "2": "质量优先", "3": "学习优先"}.get(
        work_choice, "效率优先"
    )

    print("\n请选择 AI 个性：")
    print("1. 友好、专业、简洁")
    print("2. 严谨、详细、学术")
    print("3. 轻松、幽默、创意")
    personality_choice = input("选择 [1/2/3]： ").strip() or "1"

    personalities = {"1": "友好、专业、简洁", "2": "严谨、详细、学术", "3": "轻松、幽默、创意"}
    personality = personalities.get(personality_choice, "友好、专业、简洁")

    # 创建文件
    memory.create_user_profile(username, communication_style, work_preferences)
    memory.create_soul(personality)
    memory.create_memory()

    print("\n" + "=" * 60)
    print("✅  设置完成！")
    print("=" * 60)
    print(f"\n用户：{username}")
    print(f"沟通风格：{communication_style}")
    print(f"工作偏好：{work_preferences}")
    print(f"AI 个性：{personality}")
    print("\n您可以随时编辑以下文件来自定义：")
    print(f"  - {get_user_profile_path()}")
    print(f"  - {get_soul_path()}")
    print()

    return True


# 技能建议提取
def analyze_session_for_skill_suggestion(
    session_summary: str, tool_calls: list[str] | None = None, min_tool_calls: int = 3
) -> dict[str, Any]:
    """
    分析会话历史，判断是否应该建议创建新技能。

    Args:
        session_summary: 会话摘要
        tool_calls: 工具调用列表（可选）
        min_tool_calls: 触发建议的最小工具调用次数

    Returns:
        包含建议信息的字典
    """
    tool_calls = tool_calls or []

    result = {
        "suggested": False,
        "reason": "",
        "suggested_name": None,
        "tags": [],
        "summary": session_summary,
    }

    # 启发式 1：工具调用链长度
    if len(tool_calls) >= min_tool_calls:
        result["suggested"] = True
        result["reason"] = f"工具调用链较长（{len(tool_calls)} 次），适合创建技能"
        result["tags"] = ["workflow", "automation"]

    # 启发式 2：检测到重复模式
    if tool_calls:
        from collections import Counter

        call_counts = Counter(tool_calls)
        for call, count in call_counts.items():
            if count >= 2:
                result["suggested"] = True
                result["reason"] = f"检测到重复调用：{call}（{count} 次）"
                result["tags"].append("repetition")
                break

    # 生成建议的名称（基于会话摘要）
    if result["suggested"]:
        import re

        words = re.findall(r"\b\w+\b", session_summary.lower())
        keywords = [w for w in words if len(w) > 2][:3]
        if keywords:
            suggested_name = "_".join(keywords)
            result["suggested_name"] = suggested_name[:50]
        else:
            import hashlib
            import time

            result["suggested_name"] = (
                f"auto_skill_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"
            )

    return result
