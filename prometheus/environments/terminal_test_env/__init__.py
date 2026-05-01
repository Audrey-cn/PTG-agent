"""Terminal Test Environment."""

import logging
import os
from pathlib import Path
from typing import Any, Dict

from environments.agent_loop import AgentResult
from environments.prometheus_base_env import PrometheusAgentBaseEnv, PrometheusAgentEnvConfig
from environments.tool_context import ToolContext

logger = logging.getLogger(__name__)


class TerminalTestEnv(PrometheusAgentBaseEnv):
    name = "terminal-test"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._test_items = [
            {
                "instance_id": "test_create_file",
                "prompt": "Create a file /tmp/prometheus_test_file.txt with the content 'Hello from Prometheus-Agent!'",
                "expected_path": "/tmp/prometheus_test_file.txt",
                "expected_content": "Hello from Prometheus-Agent!",
                "reward_fn": self._reward_check_file,
            },
            {
                "instance_id": "test_run_command",
                "prompt": "Run the command 'echo test_output' in the terminal and report the output.",
                "expected_output": "test_output",
                "reward_fn": self._reward_check_output,
            },
            {
                "instance_id": "test_create_directory",
                "prompt": "Create a directory at /tmp/prometheus_test_dir",
                "expected_path": "/tmp/prometheus_test_dir",
                "reward_fn": self._reward_check_dir,
            },
        ]
        self._item_index = 0

    async def setup(self):
        pass

    async def get_next_item(self) -> dict[str, Any]:
        item = self._test_items[self._item_index % len(self._test_items)]
        self._item_index += 1
        return item

    def format_prompt(self, item) -> str:
        return item["prompt"]

    def _reward_check_file(self, item: dict, result: AgentResult, ctx: ToolContext) -> float:
        path = item.get("expected_path", "")
        if not Path(path).exists():
            logger.info("File not found: %s", path)
            return 0.0

        content = Path(path).read_text()
        expected = item.get("expected_content", "")

        if expected and expected in content:
            logger.info("File content matches expected: %s", path)
            return 1.0

        if content.strip():
            logger.info("File exists but content differs: got %r, expected %r", content, expected)
            return 0.5

        return 0.0

    def _reward_check_output(self, item: dict, result: AgentResult, ctx: ToolContext) -> float:
        full_text = "\n".join(
            msg.get("content", "")
            for msg in result.messages
            if msg.get("role") == "assistant" and msg.get("content")
        )
        expected = item.get("expected_output", "")
        if expected and expected in full_text:
            return 1.0
        return 0.0

    def _reward_check_dir(self, item: dict, result: AgentResult, ctx: ToolContext) -> float:
        path = item.get("expected_path", "")
        if Path(path).is_dir():
            logger.info("Directory exists: %s", path)
            return 1.0
        logger.info("Directory not found: %s", path)
        return 0.0

    async def compute_reward(self, item: dict, result: AgentResult, ctx: ToolContext) -> float:
        reward_fn = item.get("reward_fn")
        if reward_fn:
            return reward_fn(item, result, ctx)
        return 0.0

    async def evaluate(self, num_episodes: int = 3):
        await self.setup()
        results = []
        for i in range(min(num_episodes, len(self._test_items))):
            item = self._test_items[i]
            scored_item, _ = await self.collect_trajectory(item)
            score = scored_item.get("scores", 0.0) if scored_item else 0.0
            results.append({"instance_id": item["instance_id"], "score": score})
            logger.info("Test %d: %s -> %.1f", i + 1, item["instance_id"], score)

        passed = sum(1 for r in results if r["score"] >= 1.0)
        logger.info("Terminal test: %d/%d passed", passed, len(results))
        return results
