"""SWE-Bench Environment (Prometheus variant)."""

import logging
from typing import Any

from environments.prometheus_base_env import PrometheusAgentBaseEnv

logger = logging.getLogger(__name__)


class PrometheusSWEEnv(PrometheusAgentBaseEnv):
    name = "prometheus-swe"

    async def setup(self):
        logger.info("Prometheus SWE environment setup (placeholder)")
        pass

    async def get_next_item(self) -> dict[str, Any]:
        return {
            "instance_id": "placeholder",
            "prompt": "Placeholder SWE task",
            "repo": "python/cpython",
            "version": "3.11.0",
            "problem_statement": "Placeholder issue description",
        }

    def format_prompt(self, item) -> str:
        return f"Task: {item.get('prompt', '')}\n\nIssue: {item.get('problem_statement', '')}"

    async def compute_reward(self, item, result, ctx):
        logger.warning("Prometheus SWE compute_reward not implemented")
        return 0.0

    async def evaluate(self, *args, **kwargs):
        logger.warning("Prometheus SWE evaluate not implemented")
        return []
