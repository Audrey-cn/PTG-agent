"""Resource cleanup utilities for Prometheus."""

import atexit
import logging
import threading
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)


class ResourceCleanupManager:
    """Centralized resource cleanup manager.

    Tracks resources that need cleanup on shutdown.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._cleanup_handlers = []
            cls._instance._resources = {}
            cls._instance._lock = threading.Lock()
            cls._instance._registered = False
        return cls._instance

    def register_cleanup_handler(self, handler: Callable, name: str = None):
        """Register a cleanup handler.

        Args:
            handler: Function to call during cleanup
            name: Optional name for identification
        """
        with self._lock:
            self._cleanup_handlers.append(
                {
                    "handler": handler,
                    "name": name or str(id(handler)),
                }
            )

            if not self._registered:
                atexit.register(self._cleanup)
                self._registered = True

    def register_resource(self, resource_id: str, resource, cleanup_fn: Callable):
        """Register a resource for cleanup.

        Args:
            resource_id: Unique identifier for the resource
            resource: The resource object
            cleanup_fn: Function to call to clean up this resource
        """
        with self._lock:
            self._resources[resource_id] = {
                "resource": resource,
                "cleanup_fn": cleanup_fn,
            }

    def unregister_resource(self, resource_id: str):
        """Unregister a resource."""
        with self._lock:
            if resource_id in self._resources:
                del self._resources[resource_id]

    def cleanup_resource(self, resource_id: str):
        """Clean up a specific resource immediately."""
        with self._lock:
            if resource_id in self._resources:
                resource_info = self._resources[resource_id]
                try:
                    resource_info["cleanup_fn"](resource_info["resource"])
                    del self._resources[resource_id]
                    logger.debug(f"Cleaned up resource: {resource_id}")
                except Exception as e:
                    logger.error(f"Error cleaning up resource {resource_id}: {e}")

    def _cleanup(self):
        """Execute all registered cleanup handlers."""
        logger.info("Starting resource cleanup...")

        # Clean up registered resources
        with self._lock:
            resources_copy = list(self._resources.items())

        for resource_id, resource_info in resources_copy:
            try:
                resource_info["cleanup_fn"](resource_info["resource"])
                logger.debug(f"Cleaned up resource: {resource_id}")
            except Exception as e:
                logger.error(f"Error cleaning up resource {resource_id}: {e}")

        # Execute cleanup handlers
        with self._lock:
            handlers_copy = list(self._cleanup_handlers)

        for handler_info in handlers_copy:
            try:
                handler_info["handler"]()
                logger.debug(f"Executed cleanup handler: {handler_info['name']}")
            except Exception as e:
                logger.error(f"Error executing cleanup handler {handler_info['name']}: {e}")

        logger.info("Resource cleanup completed")

    def get_resource_count(self) -> int:
        """Get the number of registered resources."""
        with self._lock:
            return len(self._resources)

    def get_handler_count(self) -> int:
        """Get the number of registered cleanup handlers."""
        with self._lock:
            return len(self._cleanup_handlers)


def get_cleanup_manager() -> ResourceCleanupManager:
    """Get global resource cleanup manager."""
    return ResourceCleanupManager()


class BrowserSessionTracker:
    """Tracks browser sessions for cleanup."""

    def __init__(self):
        self._sessions = {}
        self._lock = threading.Lock()

    def add_session(self, session_id: str, driver):
        """Add a browser session."""
        with self._lock:
            self._sessions[session_id] = {
                "driver": driver,
                "created_at": time.time(),
            }

    def remove_session(self, session_id: str):
        """Remove and close a browser session."""
        with self._lock:
            if session_id in self._sessions:
                session = self._sessions[session_id]
                try:
                    session["driver"].quit()
                    del self._sessions[session_id]
                    logger.debug(f"Closed browser session: {session_id}")
                except Exception as e:
                    logger.error(f"Error closing browser session {session_id}: {e}")

    def cleanup_all(self):
        """Clean up all browser sessions."""
        with self._lock:
            sessions_copy = list(self._sessions.keys())

        for session_id in sessions_copy:
            self.remove_session(session_id)

    def get_session_count(self) -> int:
        """Get the number of active sessions."""
        with self._lock:
            return len(self._sessions)


class VMSessionTracker:
    """Tracks VM sessions for cleanup."""

    def __init__(self):
        self._vms = {}
        self._lock = threading.Lock()

    def add_vm(self, vm_id: str, vm_instance):
        """Add a VM instance."""
        with self._lock:
            self._vms[vm_id] = {
                "instance": vm_instance,
                "created_at": time.time(),
            }

    def remove_vm(self, vm_id: str):
        """Remove and stop a VM instance."""
        with self._lock:
            if vm_id in self._vms:
                vm = self._vms[vm_id]
                try:
                    vm["instance"].stop()
                    del self._vms[vm_id]
                    logger.debug(f"Stopped VM: {vm_id}")
                except Exception as e:
                    logger.error(f"Error stopping VM {vm_id}: {e}")

    def cleanup_all(self):
        """Clean up all VM instances."""
        with self._lock:
            vms_copy = list(self._vms.keys())

        for vm_id in vms_copy:
            self.remove_vm(vm_id)

    def get_vm_count(self) -> int:
        """Get the number of active VMs."""
        with self._lock:
            return len(self._vms)


def register_browser_cleanup(driver, session_id: str):
    """Register a browser driver for cleanup."""
    tracker = BrowserSessionTracker()
    tracker.add_session(session_id, driver)

    def cleanup():
        tracker.remove_session(session_id)

    get_cleanup_manager().register_cleanup_handler(cleanup, f"browser_{session_id}")


def register_vm_cleanup(vm_instance, vm_id: str):
    """Register a VM instance for cleanup."""
    tracker = VMSessionTracker()
    tracker.add_vm(vm_id, vm_instance)

    def cleanup():
        tracker.remove_vm(vm_id)

    get_cleanup_manager().register_cleanup_handler(cleanup, f"vm_{vm_id}")


def register_general_cleanup(cleanup_fn: Callable, name: str = None):
    """Register a general cleanup function."""
    get_cleanup_manager().register_cleanup_handler(cleanup_fn, name)
