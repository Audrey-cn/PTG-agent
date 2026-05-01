"""Iteration budget management for Prometheus."""

import threading


class IterationBudget:
    """Thread-safe iteration counter for an agent.

    Each agent (parent or subagent) gets its own ``IterationBudget``.
    The parent's budget is capped at ``max_iterations`` (default 90).
    Each subagent gets an independent budget capped at
    ``delegation.max_iterations`` (default 50) — this means total
    iterations across parent + subagents can exceed the parent's cap.

    ``execute_code`` (programmatic tool calling) iterations are refunded via
    :meth:`refund` so they don't eat into the budget.
    """

    def __init__(self, max_total: int):
        """Initialize the iteration budget.

        Args:
            max_total: Maximum number of iterations allowed
        """
        self.max_total = max_total
        self._used = 0
        self._lock = threading.Lock()

    def consume(self) -> bool:
        """Try to consume one iteration.

        Returns:
            True if allowed, False if budget exhausted
        """
        with self._lock:
            if self._used >= self.max_total:
                return False
            self._used += 1
            return True

    def refund(self) -> None:
        """Give back one iteration (e.g. for execute_code turns)."""
        with self._lock:
            if self._used > 0:
                self._used -= 1

    def refund_multiple(self, count: int) -> None:
        """Refund multiple iterations at once.

        Args:
            count: Number of iterations to refund
        """
        with self._lock:
            self._used = max(0, self._used - count)

    @property
    def used(self) -> int:
        """Get the number of used iterations."""
        return self._used

    @property
    def remaining(self) -> int:
        """Get the number of remaining iterations."""
        with self._lock:
            return max(0, self.max_total - self._used)

    @property
    def exhausted(self) -> bool:
        """Check if the budget is exhausted."""
        with self._lock:
            return self._used >= self.max_total

    def reset(self) -> None:
        """Reset the budget to initial state."""
        with self._lock:
            self._used = 0

    def get_usage_ratio(self) -> float:
        """Get the usage ratio (0.0 to 1.0+).

        Returns:
            Ratio of used to max (can exceed 1.0 if over budget)
        """
        with self._lock:
            return self._used / max(1, self.max_total)

    def should_warn(self, threshold: float = 0.8) -> bool:
        """Check if should warn based on usage threshold.

        Args:
            threshold: Warning threshold (0.0 to 1.0)

        Returns:
            True if usage exceeds threshold
        """
        return self.get_usage_ratio() >= threshold

    def get_status(self) -> dict:
        """Get a status dict for the budget.

        Returns:
            Dictionary with budget status
        """
        return {
            "used": self.used,
            "remaining": self.remaining,
            "max": self.max_total,
            "exhausted": self.exhausted,
            "ratio": round(self.get_usage_ratio(), 2),
        }

    def __repr__(self) -> str:
        return f"IterationBudget({self.used}/{self.max_total})"


class BudgetManager:
    """Manages iteration budgets for parent and subagents.

    Provides budget tracking across agent hierarchies.
    """

    def __init__(self, max_iterations: int = 90, subagent_max: int = 50):
        """Initialize the budget manager.

        Args:
            max_iterations: Default max for parent agent
            subagent_max: Max for subagents
        """
        self.max_iterations = max_iterations
        self.subagent_max = subagent_max
        self._budgets = {}
        self._lock = threading.Lock()

    def create_budget(self, agent_id: str, max_iterations: int | None = None) -> IterationBudget:
        """Create a new budget for an agent.

        Args:
            agent_id: Unique agent identifier
            max_iterations: Optional override for max iterations

        Returns:
            New IterationBudget instance
        """
        budget = IterationBudget(max_iterations or self.max_iterations)

        with self._lock:
            self._budgets[agent_id] = budget

        return budget

    def get_budget(self, agent_id: str) -> IterationBudget | None:
        """Get an existing budget.

        Args:
            agent_id: Agent identifier

        Returns:
            Budget if exists, None otherwise
        """
        with self._lock:
            return self._budgets.get(agent_id)

    def remove_budget(self, agent_id: str) -> None:
        """Remove a budget.

        Args:
            agent_id: Agent identifier
        """
        with self._lock:
            if agent_id in self._budgets:
                del self._budgets[agent_id]

    def get_all_budgets(self) -> dict:
        """Get all budget statuses.

        Returns:
            Dictionary of agent_id -> status
        """
        with self._lock:
            return {agent_id: budget.get_status() for agent_id, budget in self._budgets.items()}


_global_budget_manager: BudgetManager | None = None


def get_budget_manager() -> BudgetManager:
    """Get the global budget manager instance."""
    global _global_budget_manager
    if _global_budget_manager is None:
        _global_budget_manager = BudgetManager()
    return _global_budget_manager


def create_agent_budget(agent_id: str, max_iterations: int | None = None) -> IterationBudget:
    """Create a budget for an agent.

    Args:
        agent_id: Unique agent identifier
        max_iterations: Optional max iterations override

    Returns:
        IterationBudget instance
    """
    return get_budget_manager().create_budget(agent_id, max_iterations)
