"""Automatic snapshot manager."""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class AutoSnapshotManager:
    """Automatic snapshot manager"""

    def __init__(self):
        try:
            from prometheus.checkpoint_system import get_checkpoint_system, get_session_logger

            self.cp_sys = get_checkpoint_system()
            self.session_logger = get_session_logger()
        except ImportError:
            from checkpoint_system import get_checkpoint_system, get_session_logger

            self.cp_sys = get_checkpoint_system()
            self.session_logger = get_session_logger()

        self.last_snapshot_time = None
        self.snapshot_count = 0

    def snapshot_on_event(self, event_type, context=None, force=False, min_interval_minutes=5):
        """
        Trigger snapshot based on event

        Args:
            event_type: Event type
            context: Event context
            force: Whether to force snapshot
            min_interval_minutes: Minimum interval between snapshots in minutes

        Returns:
            Whether snapshot was created
        """
        now = datetime.now()

        if not force and self.last_snapshot_time:
            interval = (now - self.last_snapshot_time).total_seconds() / 60
            if interval < min_interval_minutes:
                logger.debug(
                    f"Snapshot interval too short ({interval:.1f} minutes < {min_interval_minutes} minutes)"
                )
                return False

        snapshot_name = f"auto_{event_type}_{now.strftime('%Y%m%d_%H%M%S')}"

        additional_state = {
            "event_type": event_type,
            "auto_snapshot": True,
            "snapshot_number": self.snapshot_count + 1,
        }

        if context:
            additional_state.update(context)

        try:
            cp = self.cp_sys.create_snapshot(
                name=snapshot_name, additional_state=additional_state, save_files=True
            )

            self.last_snapshot_time = now
            self.snapshot_count += 1

            self.session_logger.log_snapshot(cp.name)
            logger.info(f"Auto snapshot created: {cp.name} (event: {event_type})")

            return True
        except Exception as e:
            logger.error(f"Auto snapshot failed: {e}")
            return False

    def snapshot_on_error(self, error, context=None):
        """
        Trigger snapshot on error

        Args:
            error: Exception object
            context: Error context

        Returns:
            Whether snapshot was created
        """
        ctx = context or {}
        ctx["error_type"] = type(error).__name__
        ctx["error_message"] = str(error)

        return self.snapshot_on_event("error", ctx, force=True, min_interval_minutes=0)

    def snapshot_on_config_change(self, config_key, old_value, new_value):
        """
        Trigger snapshot on config change

        Args:
            config_key: Config key
            old_value: Old value
            new_value: New value

        Returns:
            Whether snapshot was created
        """
        return self.snapshot_on_event(
            "config_change",
            {"config_key": config_key, "old_value": str(old_value), "new_value": str(new_value)},
            min_interval_minutes=1,
        )

    def snapshot_on_session_start(self):
        """Trigger snapshot on session start"""
        return self.snapshot_on_event("session_start", min_interval_minutes=10)

    def snapshot_before_risky_operation(self, operation_name, details=None):
        """
        Trigger snapshot before risky operation

        Args:
            operation_name: Operation name
            details: Operation details

        Returns:
            Whether snapshot was created
        """
        ctx = {"operation": operation_name}
        if details:
            ctx["details"] = details

        return self.snapshot_on_event(
            "pre_risky_operation", ctx, force=True, min_interval_minutes=0
        )


_auto_snapshot_manager = None


def get_auto_snapshot_manager():
    """Get auto snapshot manager singleton"""
    global _auto_snapshot_manager
    if _auto_snapshot_manager is None:
        _auto_snapshot_manager = AutoSnapshotManager()
    return _auto_snapshot_manager
