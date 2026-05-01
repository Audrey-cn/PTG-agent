"""PrometheusAgentLoop -- Reusable Multi-Turn Agent Engine."""

import asyncio
import concurrent.futures
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from prometheus.model_tools import handle_function_call
from prometheus.tools.terminal_tool import get_active_env
from prometheus.tools.tool_result_storage import enforce_turn_budget, maybe_persist_tool_result

_tool_executor = concurrent.futures.ThreadPoolExecutor(max_workers=128)


def resize_tool_pool(max_workers: int):
    global _tool_executor
    old_executor = _tool_executor
    _tool_executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
    old_executor.shutdown(wait=False)
    logger.info("Tool thread pool resized to %d workers", max_workers)


logger = logging.getLogger(__name__)


@dataclass
class ToolError:
    turn: int
    tool_name: str
    arguments: str
    error: str
    tool_result: str


@dataclass
class AgentResult:
    messages: list[dict[str, Any]]
    managed_state: dict[str, Any] | None = None
    turns_used: int = 0
    finished_naturally: bool = False
    reasoning_per_turn: list[str | None] = field(default_factory=list)
    tool_errors: list[ToolError] = field(default_factory=list)


def _extract_reasoning_from_message(message) -> str | None:
    if hasattr(message, "reasoning_content") and message.reasoning_content:
        return message.reasoning_content
    if hasattr(message, "reasoning") and message.reasoning:
        return message.reasoning
    if hasattr(message, "reasoning_details") and message.reasoning_details:
        for detail in message.reasoning_details:
            if hasattr(detail, "text") and detail.text:
                return detail.text
            if isinstance(detail, dict) and detail.get("text"):
                return detail["text"]
    return None


class PrometheusAgentLoop:
    def __init__(
        self,
        server,
        tool_schemas: list[dict[str, Any]],
        valid_tool_names: set[str],
        max_turns: int = 30,
        task_id: str | None = None,
        temperature: float = 1.0,
        max_tokens: int | None = None,
        extra_body: dict[str, Any] | None = None,
        budget_config: Optional["BudgetConfig"] = None,
    ):
        from prometheus.tools.budget_config import DEFAULT_BUDGET

        self.server = server
        self.tool_schemas = tool_schemas
        self.valid_tool_names = valid_tool_names
        self.max_turns = max_turns
        self.task_id = task_id or str(uuid.uuid4())
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.extra_body = extra_body
        self.budget_config = budget_config or DEFAULT_BUDGET

    async def run(self, messages: list[dict[str, Any]]) -> AgentResult:
        reasoning_per_turn = []
        tool_errors: list[ToolError] = []

        from prometheus.tools.todo_tool import TodoStore
        from prometheus.tools.todo_tool import todo_tool as _todo_tool

        _todo_store = TodoStore()

        _user_task = None
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str) and content.strip():
                    _user_task = content.strip()[:500]
                break

        import time as _time

        for turn in range(self.max_turns):
            turn_start = _time.monotonic()

            chat_kwargs = {
                "messages": messages,
                "n": 1,
                "temperature": self.temperature,
            }

            if self.tool_schemas:
                chat_kwargs["tools"] = self.tool_schemas

            if self.max_tokens is not None:
                chat_kwargs["max_tokens"] = self.max_tokens

            if self.extra_body:
                chat_kwargs["extra_body"] = self.extra_body

            api_start = _time.monotonic()
            try:
                response = await self.server.chat_completion(**chat_kwargs)
            except Exception as e:
                api_elapsed = _time.monotonic() - api_start
                logger.error("API call failed on turn %d (%.1fs): %s", turn + 1, api_elapsed, e)
                return AgentResult(
                    messages=messages,
                    managed_state=self._get_managed_state(),
                    turns_used=turn + 1,
                    finished_naturally=False,
                    reasoning_per_turn=reasoning_per_turn,
                    tool_errors=tool_errors,
                )

            api_elapsed = _time.monotonic() - api_start

            if not response or not response.choices:
                logger.warning("Empty response on turn %d (api=%.1fs)", turn + 1, api_elapsed)
                return AgentResult(
                    messages=messages,
                    managed_state=self._get_managed_state(),
                    turns_used=turn + 1,
                    finished_naturally=False,
                    reasoning_per_turn=reasoning_per_turn,
                    tool_errors=tool_errors,
                )

            assistant_msg = response.choices[0].message

            reasoning = _extract_reasoning_from_message(assistant_msg)
            reasoning_per_turn.append(reasoning)

            if (
                not assistant_msg.tool_calls
                and assistant_msg.content
                and self.tool_schemas
                and "<tool_call>" in (assistant_msg.content or "")
            ):
                try:
                    from environments.tool_call_parsers import get_parser

                    fallback_parser = get_parser("hermes")
                    parsed_content, parsed_calls = fallback_parser.parse(assistant_msg.content)
                    if parsed_calls:
                        assistant_msg.tool_calls = parsed_calls
                        if parsed_content is not None:
                            assistant_msg.content = parsed_content
                        logger.debug(
                            "Fallback parser extracted %d tool calls from raw content",
                            len(parsed_calls),
                        )
                except Exception:
                    pass

            if assistant_msg.tool_calls:

                def _tc_to_dict(tc):
                    if isinstance(tc, dict):
                        return {
                            "id": tc.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                            "type": "function",
                            "function": {
                                "name": tc.get("function", {}).get("name", tc.get("name", "")),
                                "arguments": tc.get("function", {}).get(
                                    "arguments", tc.get("arguments", "{}")
                                ),
                            },
                        }
                    return {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }

                msg_dict: dict[str, Any] = {
                    "role": "assistant",
                    "content": assistant_msg.content or "",
                    "tool_calls": [_tc_to_dict(tc) for tc in assistant_msg.tool_calls],
                }

                if reasoning:
                    msg_dict["reasoning_content"] = reasoning

                messages.append(msg_dict)

                for tc in assistant_msg.tool_calls:
                    if isinstance(tc, dict):
                        tool_name = tc.get("function", {}).get("name", tc.get("name", ""))
                        tool_args_raw = tc.get("function", {}).get(
                            "arguments", tc.get("arguments", "{}")
                        )
                    else:
                        tool_name = tc.function.name
                        tool_args_raw = tc.function.arguments

                    if tool_name not in self.valid_tool_names:
                        tool_result = json.dumps(
                            {
                                "error": f"Unknown tool '{tool_name}'. "
                                f"Available tools: {sorted(self.valid_tool_names)}"
                            }
                        )
                        tool_errors.append(
                            ToolError(
                                turn=turn + 1,
                                tool_name=tool_name,
                                arguments=tool_args_raw[:200],
                                error=f"Unknown tool '{tool_name}'",
                                tool_result=tool_result,
                            )
                        )
                        logger.warning(
                            "Model called unknown tool '%s' on turn %d",
                            tool_name,
                            turn + 1,
                        )
                    else:
                        try:
                            args = json.loads(tool_args_raw)
                        except json.JSONDecodeError as e:
                            args = None
                            tool_result = json.dumps(
                                {
                                    "error": f"Invalid JSON in tool arguments: {e}. Please retry with valid JSON."
                                }
                            )
                            tool_errors.append(
                                ToolError(
                                    turn=turn + 1,
                                    tool_name=tool_name,
                                    arguments=tool_args_raw[:200],
                                    error=f"Invalid JSON: {e}",
                                    tool_result=tool_result,
                                )
                            )
                            logger.warning(
                                "Invalid JSON in tool call arguments for '%s': %s",
                                tool_name,
                                tool_args_raw[:200],
                            )

                        if args is not None:
                            try:
                                if tool_name == "terminal":
                                    os.getenv("TERMINAL_ENV", "local")
                                    cmd_preview = args.get("command", "")[:80]
                                    logger.info(
                                        "[%s] $ %s",
                                        self.task_id[:8],
                                        cmd_preview,
                                    )

                                tool_submit_time = _time.monotonic()

                                if tool_name == "todo":
                                    tool_result = _todo_tool(
                                        todos=args.get("todos"),
                                        merge=args.get("merge", False),
                                        store=_todo_store,
                                    )
                                    tool_elapsed = _time.monotonic() - tool_submit_time
                                elif tool_name == "memory":
                                    tool_result = json.dumps(
                                        {"error": "Memory is not available in RL environments."}
                                    )
                                    tool_elapsed = _time.monotonic() - tool_submit_time
                                elif tool_name == "session_search":
                                    tool_result = json.dumps(
                                        {
                                            "error": "Session search is not available in RL environments."
                                        }
                                    )
                                    tool_elapsed = _time.monotonic() - tool_submit_time
                                else:
                                    loop = asyncio.get_event_loop()
                                    _tn, _ta, _tid = tool_name, args, self.task_id
                                    tool_result = await loop.run_in_executor(
                                        _tool_executor,
                                        lambda: handle_function_call(
                                            _tn,
                                            _ta,
                                            task_id=_tid,
                                            user_task=_user_task,
                                        ),
                                    )
                                    tool_elapsed = _time.monotonic() - tool_submit_time

                                pool_active = _tool_executor._work_queue.qsize()
                                if tool_elapsed > 30:
                                    logger.warning(
                                        "[%s] turn %d: %s took %.1fs (pool queue=%d)",
                                        self.task_id[:8],
                                        turn + 1,
                                        tool_name,
                                        tool_elapsed,
                                        pool_active,
                                    )
                            except Exception as e:
                                tool_result = json.dumps(
                                    {
                                        "error": f"Tool execution failed: {type(e).__name__}: {str(e)}"
                                    }
                                )
                                tool_errors.append(
                                    ToolError(
                                        turn=turn + 1,
                                        tool_name=tool_name,
                                        arguments=tool_args_raw[:200],
                                        error=f"{type(e).__name__}: {str(e)}",
                                        tool_result=tool_result,
                                    )
                                )
                                logger.error(
                                    "Tool '%s' execution failed on turn %d: %s",
                                    tool_name,
                                    turn + 1,
                                    e,
                                )

                        try:
                            result_data = json.loads(tool_result)
                            if isinstance(result_data, dict):
                                err = result_data.get("error")
                                exit_code = result_data.get("exit_code")
                                if err and exit_code and exit_code < 0:
                                    tool_errors.append(
                                        ToolError(
                                            turn=turn + 1,
                                            tool_name=tool_name,
                                            arguments=tool_args_raw[:200],
                                            error=str(err),
                                            tool_result=tool_result[:500],
                                        )
                                    )
                        except (json.JSONDecodeError, TypeError):
                            pass

                    tc_id = tc.get("id", "") if isinstance(tc, dict) else tc.id
                    tool_result = maybe_persist_tool_result(
                        content=tool_result,
                        tool_name=tool_name,
                        tool_use_id=tc_id,
                        env=get_active_env(self.task_id),
                        config=self.budget_config,
                    )

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "content": tool_result,
                        }
                    )

                num_tcs = len(assistant_msg.tool_calls)
                if num_tcs > 0:
                    enforce_turn_budget(
                        messages[-num_tcs:],
                        env=get_active_env(self.task_id),
                        config=self.budget_config,
                    )

                turn_elapsed = _time.monotonic() - turn_start
                logger.info(
                    "[%s] turn %d: api=%.1fs, %d tools, turn_total=%.1fs",
                    self.task_id[:8],
                    turn + 1,
                    api_elapsed,
                    len(assistant_msg.tool_calls),
                    turn_elapsed,
                )

            else:
                msg_dict = {
                    "role": "assistant",
                    "content": assistant_msg.content or "",
                }
                if reasoning:
                    msg_dict["reasoning_content"] = reasoning
                messages.append(msg_dict)

                turn_elapsed = _time.monotonic() - turn_start
                logger.info(
                    "[%s] turn %d: api=%.1fs, no tools (finished), turn_total=%.1fs",
                    self.task_id[:8],
                    turn + 1,
                    api_elapsed,
                    turn_elapsed,
                )

                return AgentResult(
                    messages=messages,
                    managed_state=self._get_managed_state(),
                    turns_used=turn + 1,
                    finished_naturally=True,
                    reasoning_per_turn=reasoning_per_turn,
                    tool_errors=tool_errors,
                )

        logger.info("Agent hit max_turns (%d) without finishing", self.max_turns)
        return AgentResult(
            messages=messages,
            managed_state=self._get_managed_state(),
            turns_used=self.max_turns,
            finished_naturally=False,
            reasoning_per_turn=reasoning_per_turn,
            tool_errors=tool_errors,
        )

    def _get_managed_state(self) -> dict[str, Any] | None:
        if hasattr(self.server, "get_state"):
            return self.server.get_state()
        return None
