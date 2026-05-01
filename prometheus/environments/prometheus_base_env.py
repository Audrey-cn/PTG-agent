"""PrometheusAgentBaseEnv -- Abstract Base Environment for Prometheus-Agent + Atropos."""

import logging
import os
import sys
import uuid
from abc import abstractmethod
from pathlib import Path
from typing import Any

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from dotenv import load_dotenv
from pydantic import Field

_env_path = _repo_root / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path)

from environments.patches import apply_patches

apply_patches()

from atroposlib.envs.base import (
    BaseEnv,
    BaseEnvConfig,
    ScoredDataGroup,
    ScoredDataItem,
)
from atroposlib.envs.server_handling.server_manager import (
    APIServerConfig,
    ServerBaseline,
)
from atroposlib.type_definitions import Item
from environments.agent_loop import AgentResult, PrometheusAgentLoop
from environments.tool_context import ToolContext
from model_tools import get_tool_definitions
from toolset_distributions import sample_toolsets_from_distribution

from prometheus.tools.budget_config import (
    DEFAULT_PREVIEW_SIZE_CHARS,
    DEFAULT_RESULT_SIZE_CHARS,
    DEFAULT_TURN_BUDGET_CHARS,
)

logger = logging.getLogger(__name__)


class PrometheusAgentEnvConfig(BaseEnvConfig):
    enabled_toolsets: list[str] | None = Field(
        default=None,
        description="Explicit list of prometheus toolsets to enable (e.g., ['terminal', 'file', 'web']). "
        "If None and distribution is also None, all available toolsets are enabled.",
    )
    disabled_toolsets: list[str] | None = Field(
        default=None,
        description="Toolsets to disable. Applied as a filter on top of enabled_toolsets or distribution.",
    )
    distribution: str | None = Field(
        default=None,
        description="Name of a toolset distribution from toolset_distributions.py "
        "(e.g., 'development', 'terminal_tasks'). Sampled once per group. "
        "Mutually exclusive with enabled_toolsets.",
    )

    max_agent_turns: int = Field(
        default=30,
        description="Maximum number of LLM calls (tool-calling iterations) per rollout.",
    )
    system_prompt: str | None = Field(
        default=None,
        description="System prompt for the agent. Tools are handled via the tools= parameter, "
        "not embedded in the prompt text.",
    )
    agent_temperature: float = Field(
        default=1.0,
        description="Sampling temperature for agent generation during rollouts.",
    )

    terminal_backend: str = Field(
        default="local",
        description="Terminal backend: 'local', 'docker', 'modal', 'daytona', 'ssh', 'singularity'. "
        "Modal or Daytona recommended for production RL (cloud isolation per rollout).",
    )
    terminal_timeout: int = Field(
        default=120,
        description="Per-command timeout in seconds for terminal tool calls. "
        "Commands exceeding this are killed. Increase for tasks with long-running "
        "commands (compilation, pip install, etc.).",
    )
    terminal_lifetime: int = Field(
        default=3600,
        description="Sandbox inactivity lifetime in seconds. The cleanup thread kills "
        "sandboxes that have been idle longer than this. Must be longer than "
        "the longest gap between tool calls (e.g., waiting for LLM response).",
    )

    dataset_name: str | None = Field(
        default=None,
        description="HuggingFace dataset name. Optional if tasks are defined inline.",
    )
    dataset_split: str = Field(
        default="train",
        description="Dataset split to use.",
    )
    prompt_field: str = Field(
        default="prompt",
        description="Which field in the dataset contains the prompt.",
    )

    tool_pool_size: int = Field(
        default=128,
        description="Thread pool size for tool execution. Each concurrent task needs a "
        "thread for tool calls. Must be large enough for parallel evaluation. "
        "Too small = thread pool starvation.",
    )

    tool_call_parser: str = Field(
        default="hermes",
        description="Tool call parser name for Phase 2 (VLLM server type). "
        "Ignored in Phase 1 (OpenAI server type where VLLM parses natively). "
        "Options: hermes, mistral, llama3_json, qwen, deepseek_v3, etc.",
    )

    default_result_size_chars: int = Field(
        default=DEFAULT_RESULT_SIZE_CHARS,
        description="Default per-tool threshold (chars) for persisting large results "
        "to sandbox. Results exceeding this are written to /tmp/prometheus-results/ "
        "and replaced with a preview. Per-tool registry values take precedence "
        "unless overridden via tool_result_overrides.",
    )
    turn_budget_chars: int = Field(
        default=DEFAULT_TURN_BUDGET_CHARS,
        description="Aggregate char budget per assistant turn. If all tool results "
        "in a single turn exceed this, the largest are persisted to disk first.",
    )
    preview_size_chars: int = Field(
        default=DEFAULT_PREVIEW_SIZE_CHARS,
        description="Size of the inline preview shown after a tool result is persisted.",
    )
    tool_result_overrides: dict[str, int] | None = Field(
        default=None,
        description="Per-tool threshold overrides (chars). Keys are tool names, "
        "values are char thresholds. Overrides both the default and registry "
        "per-tool values. Example: {'terminal': 10000, 'search_files': 5000}. "
        "Note: read_file is pinned to infinity and cannot be overridden.",
    )

    extra_body: dict[str, Any] | None = Field(
        default=None,
        description="Extra body parameters passed to the OpenAI client's "
        "chat.completions.create(). Used for OpenRouter provider preferences, "
        "transforms, and other provider-specific settings.",
    )

    def build_budget_config(self):
        from prometheus.tools.budget_config import BudgetConfig

        return BudgetConfig(
            default_result_size=self.default_result_size_chars,
            turn_budget=self.turn_budget_chars,
            preview_size=self.preview_size_chars,
            tool_overrides=dict(self.tool_result_overrides) if self.tool_result_overrides else {},
        )


class PrometheusAgentBaseEnv(BaseEnv):
    name: str | None = "prometheus-agent"
    env_config_cls = PrometheusAgentEnvConfig

    def __init__(
        self,
        config: PrometheusAgentEnvConfig,
        server_configs: ServerBaseline | list[APIServerConfig],
        slurm=False,
        testing=False,
    ):
        super().__init__(config, server_configs, slurm, testing)

        if config.terminal_backend:
            os.environ["TERMINAL_ENV"] = config.terminal_backend
        os.environ["TERMINAL_TIMEOUT"] = str(config.terminal_timeout)
        os.environ["TERMINAL_LIFETIME_SECONDS"] = str(config.terminal_lifetime)
        print(
            f"🖥️  Terminal: backend={config.terminal_backend}, "
            f"timeout={config.terminal_timeout}s, lifetime={config.terminal_lifetime}s"
        )

        from environments.agent_loop import resize_tool_pool

        resize_tool_pool(config.tool_pool_size)

        if hasattr(self.server, "tool_parser"):
            self.server.tool_parser = config.tool_call_parser
            print(f"🔧 Tool parser: {config.tool_call_parser}")

        self._current_group_tools: tuple[list[dict], set[str]] | None = None
        self._tool_error_buffer: list[dict[str, Any]] = []

    def _resolve_tools_for_group(self) -> tuple[list[dict[str, Any]], set[str]]:
        config = self.config

        if config.distribution:
            group_toolsets = sample_toolsets_from_distribution(config.distribution)
            logger.info("Sampled toolsets from '%s': %s", config.distribution, group_toolsets)
        else:
            group_toolsets = config.enabled_toolsets
            if group_toolsets is None:
                logger.warning(
                    "enabled_toolsets is None -- loading ALL tools including messaging. "
                    "Set explicit enabled_toolsets for RL training."
                )

        tools = get_tool_definitions(
            enabled_toolsets=group_toolsets,
            disabled_toolsets=config.disabled_toolsets,
            quiet_mode=True,
        )

        valid_names = {t["function"]["name"] for t in tools} if tools else set()
        logger.info("Resolved %d tools for group: %s", len(valid_names), sorted(valid_names))
        return tools, valid_names

    def _use_managed_server(self) -> bool:
        if not self.server.servers:
            return False

        server = self.server.servers[0]
        from atroposlib.envs.server_handling.openai_server import OpenAIServer

        return not isinstance(server, OpenAIServer)

    async def collect_trajectories(
        self, item: Item
    ) -> tuple[
        ScoredDataGroup | None | list[ScoredDataGroup | None],
        list[Item],
    ]:
        self._current_group_tools = self._resolve_tools_for_group()
        return await super().collect_trajectories(item)

    @staticmethod
    def _format_trajectory_for_display(messages: list[dict[str, Any]]) -> str:
        parts = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            if role == "system":
                parts.append(f"[SYSTEM]\n{content}")
            elif role == "user":
                parts.append(f"[USER]\n{content}")
            elif role == "assistant":
                reasoning = msg.get("reasoning_content", "")
                if reasoning:
                    if len(reasoning) > 300:
                        reasoning = reasoning[:300] + "..."
                    parts.append(f"[ASSISTANT thinking]\n{reasoning}")
                if content:
                    parts.append(f"[ASSISTANT]\n{content}")
                tool_calls = msg.get("tool_calls", [])
                for tc in tool_calls:
                    func = tc.get("function", {})
                    name = func.get("name", "?")
                    args = func.get("arguments", "{}")
                    if len(args) > 200:
                        args = args[:200] + "..."
                    parts.append(f"[TOOL CALL] {name}({args})")
            elif role == "tool":
                msg.get("tool_call_id", "")
                result = content
                if len(result) > 500:
                    result = result[:500] + "..."
                parts.append(f"[TOOL RESULT] {result}")

        return "\n\n".join(parts)

    async def add_rollouts_for_wandb(
        self,
        scored_data,
        item=None,
    ):
        num_keep = self.config.num_rollouts_per_group_for_logging
        if num_keep == -1:
            num_keep = self.config.group_size

        group = []
        for i in range(min(num_keep, len(scored_data.get("scores", [])))):
            score = scored_data["scores"][i]
            messages = None
            if scored_data.get("messages") and i < len(scored_data["messages"]):
                messages = scored_data["messages"][i]

            if messages:
                text = self._format_trajectory_for_display(messages)
            elif scored_data.get("tokens") and i < len(scored_data["tokens"]):
                text = self.tokenizer.decode(scored_data["tokens"][i])
            else:
                text = "(no data)"

            group.append((text, score))

        self.rollouts_for_wandb.append(group)
        if len(self.rollouts_for_wandb) > self.config.num_rollouts_to_keep:
            self.rollouts_for_wandb.pop(0)

    async def wandb_log(self, wandb_metrics: dict | None = None):
        if wandb_metrics is None:
            wandb_metrics = {}

        if self._tool_error_buffer:
            wandb_metrics["train/tool_errors_count"] = len(self._tool_error_buffer)
            error_summaries = []
            for err in self._tool_error_buffer:
                error_summaries.append(
                    f"[turn {err['turn']}] {err['tool']}({err['args'][:80]}) -> {err['error'][:150]}"
                )
            wandb_metrics["train/tool_error_details"] = "\n".join(error_summaries)
            for summary in error_summaries:
                print(f"  Tool Error: {summary}")
            self._tool_error_buffer = []
        else:
            wandb_metrics["train/tool_errors_count"] = 0

        await super().wandb_log(wandb_metrics)

    async def collect_trajectory(
        self, item: Item
    ) -> tuple[ScoredDataItem | Any | None, list[Item]]:
        task_id = str(uuid.uuid4())

        if self._current_group_tools is None:
            tools, valid_names = self._resolve_tools_for_group()
        else:
            tools, valid_names = self._current_group_tools

        messages: list[dict[str, Any]] = []
        if self.config.system_prompt:
            messages.append({"role": "system", "content": self.config.system_prompt})
        messages.append({"role": "user", "content": self.format_prompt(item)})

        result: AgentResult
        if self._use_managed_server():
            try:
                async with self.server.managed_server(
                    tokenizer=self.tokenizer,
                    preserve_think_blocks=bool(self.config.thinking_mode),
                ) as managed:
                    agent = PrometheusAgentLoop(
                        server=managed,
                        tool_schemas=tools,
                        valid_tool_names=valid_names,
                        max_turns=self.config.max_agent_turns,
                        task_id=task_id,
                        temperature=self.config.agent_temperature,
                        max_tokens=self.config.max_token_length,
                        extra_body=self.config.extra_body,
                        budget_config=self.config.build_budget_config(),
                    )
                    result = await agent.run(messages)
            except NotImplementedError:
                logger.warning(
                    "ManagedServer not available (OpenAI server?). "
                    "Falling back to direct server mode."
                )
                agent = PrometheusAgentLoop(
                    server=self.server,
                    tool_schemas=tools,
                    valid_tool_names=valid_names,
                    max_turns=self.config.max_agent_turns,
                    task_id=task_id,
                    temperature=self.config.agent_temperature,
                    max_tokens=self.config.max_token_length,
                    extra_body=self.config.extra_body,
                    budget_config=self.config.build_budget_config(),
                )
                result = await agent.run(messages)
        else:
            agent = PrometheusAgentLoop(
                server=self.server,
                tool_schemas=tools,
                valid_tool_names=valid_names,
                max_turns=self.config.max_agent_turns,
                task_id=task_id,
                temperature=self.config.agent_temperature,
                max_tokens=self.config.max_token_length,
                extra_body=self.config.extra_body,
                budget_config=self.config.build_budget_config(),
            )
            result = await agent.run(messages)

        only_system_and_user = all(msg.get("role") in ("system", "user") for msg in result.messages)
        if result.turns_used == 0 or only_system_and_user:
            logger.warning(
                "Agent loop produced no output (turns=%d, msgs=%d). Skipping reward.",
                result.turns_used,
                len(result.messages),
            )
            reward = 0.0
        else:
            ctx = ToolContext(task_id)
            try:
                reward = await self.compute_reward(item, result, ctx)
            except Exception as e:
                logger.error("compute_reward failed: %s", e)
                reward = 0.0
            finally:
                ctx.cleanup()

        if result.tool_errors:
            for err in result.tool_errors:
                self._tool_error_buffer.append(
                    {
                        "turn": err.turn,
                        "tool": err.tool_name,
                        "args": err.arguments[:150],
                        "error": err.error[:300],
                        "result": err.tool_result[:300],
                    }
                )

        nodes = (result.managed_state or {}).get("nodes", [])

        if nodes:
            node = nodes[-1]
            scored_item: dict[str, Any] = {
                "tokens": node.tokens,
                "masks": node.masked_tokens,
                "scores": reward,
            }
            if hasattr(node, "logprobs") and node.logprobs:
                scored_item["advantages"] = None
                scored_item["ref_logprobs"] = None
        else:
            full_text = "\n".join(
                msg.get("content", "") for msg in result.messages if msg.get("content")
            )
            if self.tokenizer:
                tokens = self.tokenizer.encode(full_text, add_special_tokens=True)
            else:
                tokens = list(range(min(len(full_text) // 4, 128)))

            scored_item = {
                "tokens": tokens,
                "masks": [-100] + tokens[1:],
                "scores": reward,
            }

        scored_item["messages"] = result.messages

        return scored_item, []

    @abstractmethod
    async def setup(self):
        raise NotImplementedError

    @abstractmethod
    async def get_next_item(self) -> Item:
        raise NotImplementedError

    @abstractmethod
    def format_prompt(self, item: Item) -> str:
        raise NotImplementedError

    @abstractmethod
    async def compute_reward(self, item: Item, result: AgentResult, ctx: ToolContext) -> float:
        raise NotImplementedError

    @abstractmethod
    async def evaluate(self, *args, **kwargs):
        raise NotImplementedError
