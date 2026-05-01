"""YC-Bench Evaluation Environment."""

import logging
from typing import Any, Dict

from environments.prometheus_base_env import PrometheusAgentBaseEnv, PrometheusAgentEnvConfig

logger = logging.getLogger(__name__)


class YCBenchEnv(PrometheusAgentBaseEnv):
    name = "ycbench"

    async def setup(self):
        logger.info("YC-Bench environment setup (placeholder)")
        pass

    async def get_next_item(self) -> dict[str, Any]:
        return {"instance_id": "placeholder", "prompt": "Placeholder task"}

    def format_prompt(self, item) -> str:
        return item.get("prompt", "")

    async def compute_reward(self, item, result, ctx):
        logger.warning("YC-Bench compute_reward not implemented")
        return 0.0

    async def evaluate(self, *args, **kwargs):
        logger.warning("YC-Bench evaluate not implemented")
        return []
