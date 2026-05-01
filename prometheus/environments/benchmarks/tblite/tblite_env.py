"""Terminal-Bench (TBLite) Environment."""

import asyncio
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path

from environments.agent_loop import AgentResult
from environments.prometheus_base_env import PrometheusAgentBaseEnv
from environments.tool_context import ToolContext

ROOT = Path(__file__).resolve().parent.parent.parent.parent


logger = logging.getLogger(__name__)


@dataclass
class TBLiteItem:
    instance_id: str
    intent: str
    reference: str
    task_script: str
    evaluation_script: str
    initial_prompt: str
    max_turns: int = 30


def _load_default_tasks() -> list[TBLiteItem]:
    return [
        TBLiteItem(
            instance_id="task_git_01",
            intent="Initialize a new git repository, create a file, and commit it with a message.",
            reference="git init && echo 'hello' > file.txt && git add . && git commit -m 'Initial commit'",
            task_script="""#!/bin/bash
# Setup task environment
cd /tmp/tblite/workspace
mkdir -p project
cd project
git init
""",
            evaluation_script="""#!/bin/bash
cd /tmp/tblite/workspace/project
if [ -d .git ]; then
    echo "PASS: Git repo initialized"
    exit 0
else
    echo "FAIL: No git repo found"
    exit 1
fi
""",
            initial_prompt="Initialize a new git repository in /tmp/tblite/workspace/project.",
        ),
        TBLiteItem(
            instance_id="task_docker_01",
            intent="List running Docker containers and show logs of a specific container.",
            reference="docker ps && docker logs my_container",
            task_script="""#!/bin/bash
docker run -d --name test_container alpine sleep 3600
""",
            evaluation_script="""#!/bin/bash
if docker ps --format '{{.Names}}' | grep -q test_container; then
    echo "PASS: Container is running"
    exit 0
else
    echo "FAIL: Container not found"
    exit 1
fi
""",
            initial_prompt="Start a Docker container named 'test_container' using the alpine image, then list all running containers.",
        ),
        TBLiteItem(
            instance_id="task_file_01",
            intent="Create a directory structure, write a config file, and display its contents.",
            reference="mkdir -p dir && cat file",
            task_script="""#!/bin/bash
mkdir -p /tmp/tblite/workspace/app/config
""",
            evaluation_script="""#!/bin/bash
if [ -f /tmp/tblite/workspace/app/config/app.yaml ]; then
    echo "PASS: Config file exists"
    exit 0
else
    echo "FAIL: Config file not found"
    exit 1
fi
""",
            initial_prompt="Create a directory structure at /tmp/tblite/workspace/app/config and write a simple YAML config file to /tmp/tblite/workspace/app/config/app.yaml with a 'name: test' key.",
        ),
    ]


async def _load_tasks_from_hf(
    dataset_name: str = "prometheus-agent/tblite-eval",
) -> list[TBLiteItem]:
    try:
        from datasets import load_dataset

        ds = await asyncio.get_event_loop().run_in_executor(
            None, lambda: load_dataset(dataset_name, split="train")
        )
        items = []
        for row in ds:
            items.append(
                TBLiteItem(
                    instance_id=row.get("instance_id", row.get("id", str(uuid.uuid4()))),
                    intent=row.get("intent", ""),
                    reference=row.get("reference", ""),
                    task_script=row.get("task_script", ""),
                    evaluation_script=row.get("evaluation_script", ""),
                    initial_prompt=row.get("initial_prompt", row.get("intent", "")),
                    max_turns=row.get("max_turns", 30),
                )
            )
        return items
    except Exception as e:
        logger.warning("Failed to load TBLite from HuggingFace: %s. Using default tasks.", e)
        return _load_default_tasks()


class TBLiteEnv(PrometheusAgentBaseEnv):
    name = "tblite"

    def __init__(self, *args, dataset_name: str = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._items: list[TBLiteItem] = []
        self._item_index = 0
        self._dataset_name = dataset_name or "prometheus-agent/tblite-eval"
        self._setup_done = False

    async def setup(self):
        if not self._setup_done:
            self._items = await _load_tasks_from_hf(self._dataset_name)
            if not self._items:
                self._items = _load_default_tasks()
            self._setup_done = True
            logger.info("TBLite: loaded %d tasks from %s", len(self._items), self._dataset_name)

    async def get_next_item(self):
        await self.setup()
        if not self._items:
            raise RuntimeError("No TBLite items available")
        item = self._items[self._item_index % len(self._items)]
        self._item_index += 1
        return item

    def format_prompt(self, item) -> str:
        return item.initial_prompt

    async def compute_reward(
        self, item: TBLiteItem, result: AgentResult, ctx: ToolContext
    ) -> float:
        eval_script = item.evaluation_script.strip()
        if not eval_script:
            logger.warning("No evaluation script for %s, defaulting to 0", item.instance_id)
            return 0.0

        logger.info("Running evaluation for %s", item.instance_id)

        tmp_script = f"/tmp/tblite_eval_{uuid.uuid4().hex[:8]}.sh"
        ctx.write_file(tmp_script, eval_script)
        ctx.terminal(f"chmod +x {tmp_script}")

        eval_result = ctx.terminal(f"bash {tmp_script}", timeout=60)
        ctx.terminal(f"rm -f {tmp_script}")

        output = eval_result.get("output", "")
        exit_code = eval_result.get("exit_code", -1)

        if "PASS" in output or exit_code == 0:
            logger.info("TBLite %s: PASS", item.instance_id)
            return 1.0

        logger.info(
            "TBLite %s: FAIL (exit=%d, output=%s)", item.instance_id, exit_code, output[:200]
        )
        return 0.0

    async def evaluate(self, num_episodes: int = 10):
        await self.setup()
        results = []

        for i, item in enumerate(self._items[:num_episodes]):
            logger.info("TBLite evaluation %d/%d: %s", i + 1, num_episodes, item.instance_id)
            scored_item, _ = await self.collect_trajectory(item)
            score = scored_item.get("scores", 0.0) if scored_item else 0.0
            results.append({"instance_id": item.instance_id, "score": score})

        total = len(results)
        passed = sum(1 for r in results if r["score"] >= 1.0)
        logger.info(
            "TBLite evaluation complete: %d/%d passed (%.1f%%)",
            passed,
            total,
            100 * passed / total if total > 0 else 0,
        )
        return results
