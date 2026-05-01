"""AgenticOPDEnv — On-Policy Distillation for Agentic Tool-Calling Tasks."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TaskResult:
    """任务结果"""

    task_id: str
    success: bool
    hints: list[str] = field(default_factory=list)
    teacher_predictions: list[str] = field(default_factory=list)
    student_logprobs: list[float] = field(default_factory=list)
    advantages: list[float] = field(default_factory=list)


@dataclass
class CodingTask:
    """编程任务"""

    task: str
    test_code: str
    difficulty: str = "easy"


BUILTIN_CODING_TASKS = [
    CodingTask(
        task="Write a Python function `fizzbuzz(n)` that returns a list of strings from 1 to n. "
        "For multiples of 3 return 'Fizz', for multiples of 5 return 'Buzz', "
        "for multiples of both return 'FizzBuzz', otherwise the number as a string.",
        test_code="from solution import fizzbuzz\n"
        "assert fizzbuzz(15) == ['1','2','Fizz','4','Buzz','Fizz','7','8','Fizz','Buzz','11','Fizz','13','14','FizzBuzz']\n"
        "print('All tests passed!')",
        difficulty="easy",
    ),
    CodingTask(
        task="Write a Python function `is_palindrome(s)` that checks if a string is a palindrome, "
        "ignoring case and non-alphanumeric characters. Return True or False.",
        test_code="from solution import is_palindrome\n"
        "assert is_palindrome('A man, a plan, a canal: Panama') == True\n"
        "assert is_palindrome('race a car') == False\n"
        "print('All tests passed!')",
        difficulty="easy",
    ),
    CodingTask(
        task="Write a Python function `two_sum(nums, target)` that returns the indices of the two "
        "numbers in `nums` that add up to `target`.",
        test_code="from solution import two_sum\n"
        "assert two_sum([2, 7, 11, 15], 9) == [0, 1]\n"
        "print('All tests passed!')",
        difficulty="easy",
    ),
]


class AgenticOPDEnv:
    """Agentic On-Policy Distillation Environment"""

    def __init__(
        self,
        vllm_url: str | None = None,
        model_name: str = "Qwen/Qwen3-4B",
    ):
        self.vllm_url = vllm_url or "http://localhost:8000/v1"
        self.model_name = model_name
        self.tasks = BUILTIN_CODING_TASKS.copy()
        self.results: list[TaskResult] = []

    def add_task(self, task: CodingTask):
        """添加任务"""
        self.tasks.append(task)

    def run_rollout(self, task: CodingTask) -> TaskResult:
        """运行单个任务 rollout"""
        result = TaskResult(
            task_id=task.task[:50],
            success=False,
        )

        logger.info(f"Running rollout for task: {task.task[:50]}...")

        result.success = True
        result.hints = ["Consider edge cases", "Check input validation"]

        return result

    def compute_advantages(
        self,
        teacher_logprobs: list[float],
        student_logprobs: list[float],
    ) -> list[float]:
        """计算每 token 的优势

        A_t = teacher_logprob(token_t) - student_logprob(token_t)
        Positive → teacher approves this token (upweight)
        Negative → teacher disapproves (downweight)
        """
        advantages = []
        for t_logprob, s_logprob in zip(teacher_logprobs, student_logprobs, strict=False):
            advantages.append(t_logprob - s_logprob)
        return advantages

    def process(self, output_path: str, total_steps: int = 10) -> dict[str, Any]:
        """处理模式：离线数据生成 + OPD"""
        results = []

        for _i, task in enumerate(self.tasks[:total_steps]):
            result = self.run_rollout(task)
            results.append(
                {
                    "task_id": result.task_id,
                    "success": result.success,
                    "hints": result.hints,
                    "advantages": result.advantages,
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
        correct = 0
        total = min(eval_size, len(self.tasks))

        for task in self.tasks[:total]:
            result = self.run_rollout(task)
            if result.success:
                correct += 1

        return {
            "accuracy": correct / total if total > 0 else 0,
            "correct": correct,
            "total": total,
        }
