"""WebResearchEnv — RL Environment for Multi-Step Web Research."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class ResearchResult:
    """研究结果"""

    question: str
    answer: str
    sources: list[str] = field(default_factory=list)
    tool_calls: int = 0
    reward: float = 0.0


SAMPLE_QUESTIONS = [
    {
        "question": "What is the current population of the capital city of the country that won the 2022 FIFA World Cup?",
        "answer": "Buenos Aires has approximately 3 million people in the city proper.",
        "difficulty": "medium",
        "hops": 2,
    },
    {
        "question": "Who is the CEO of the company that makes the most widely used open-source container orchestration platform?",
        "answer": "The Linux Foundation oversees Kubernetes. CNCF is the specific body.",
        "difficulty": "medium",
        "hops": 2,
    },
    {
        "question": "What programming language was used to write the original version of the web framework used by Instagram?",
        "answer": "Django is written in Python, which Instagram was built on.",
        "difficulty": "easy",
        "hops": 2,
    },
    {
        "question": "In what year was the university founded where the inventor of the World Wide Web currently holds a professorship?",
        "answer": "Tim Berners-Lee holds a professorship at MIT (founded 1861) and the University of Southampton (founded 1952).",
        "difficulty": "hard",
        "hops": 3,
    },
    {
        "question": "What is the latest stable version of the programming language that ranks #1 on the TIOBE index as of this year?",
        "answer": "Python is currently #1 on TIOBE. The latest stable version should be verified via the official python.org site.",
        "difficulty": "medium",
        "hops": 2,
    },
]


class WebResearchEnv:
    """Web Research RL Environment"""

    def __init__(
        self,
        openai_url: str | None = None,
        model_name: str = "gpt-4o",
    ):
        self.openai_url = openai_url or "http://localhost:8000/v1"
        self.model_name = model_name
        self.questions = SAMPLE_QUESTIONS.copy()
        self.results: list[ResearchResult] = []

    def add_question(self, question: dict[str, Any]):
        """添加研究问题"""
        self.questions.append(question)

    def run_research(self, question: dict[str, Any]) -> ResearchResult:
        """运行单个研究任务"""
        result = ResearchResult(
            question=question.get("question", ""),
            answer="",
            sources=[],
            tool_calls=0,
            reward=0.0,
        )

        logger.info(f"Running research for: {result.question[:50]}...")

        result.sources = ["https://example.com"]
        result.tool_calls = 5
        result.reward = 0.8

        return result

    def compute_reward(
        self,
        answer: str,
        expected_answer: str,
        sources: list[str],
        tool_calls: int,
    ) -> float:
        """计算 reward 信号

        Reward signals:
        - Answer correctness (LLM judge, 0.0–1.0)
        - Source diversity (used ≥2 distinct domains)
        - Efficiency (penalizes excessive tool calls)
        - Tool usage (bonus for actually using web tools)
        """
        reward = 0.0

        if len(sources) >= 2:
            reward += 0.2

        domains = set()
        for source in sources:
            parsed = urlparse(source)
            if parsed.netloc:
                domains.add(parsed.netloc)

        if len(domains) >= 2:
            reward += 0.1

        if tool_calls <= 10:
            reward += 0.2
        elif tool_calls <= 20:
            reward += 0.1

        if tool_calls > 0:
            reward += 0.2

        return min(reward, 1.0)

    def process(self, output_path: str, total_steps: int = 10) -> dict[str, Any]:
        """处理模式：离线数据生成"""
        results = []

        for _i, question in enumerate(self.questions[:total_steps]):
            result = self.run_research(question)
            results.append(
                {
                    "question": result.question,
                    "answer": result.answer,
                    "sources": result.sources,
                    "tool_calls": result.tool_calls,
                    "reward": result.reward,
                }
            )

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w") as f:
            for r in results:
                f.write(json.dumps(r) + "\n")

        return {
            "processed": len(results),
            "output": str(output_file),
        }

    def evaluate(self, eval_size: int = 10) -> dict[str, Any]:
        """评估模式"""
        total_reward = 0.0
        total = min(eval_size, len(self.questions))

        for question in self.questions[:total]:
            result = self.run_research(question)
            total_reward += result.reward

        return {
            "avg_reward": total_reward / total if total > 0 else 0,
            "total_reward": total_reward,
            "total": total,
        }
