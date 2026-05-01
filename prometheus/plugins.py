"""Enhanced plugin system with middleware for Prometheus."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class MiddlewareHook(Enum):
    """Available middleware hook points."""

    PRE_TOOL_CALL = "pre_tool_call"
    POST_TOOL_CALL = "post_tool_call"
    PRE_MESSAGE = "pre_message"
    POST_MESSAGE = "post_message"
    PRE_COMPRESS = "pre_compress"
    POST_COMPRESS = "post_compress"
    PRE_MEMORY_WRITE = "pre_memory_write"
    POST_MEMORY_WRITE = "post_memory_write"
    ON_ERROR = "on_error"
    ON_SESSION_START = "on_session_start"
    ON_SESSION_END = "on_session_end"


class Middleware:
    """Base middleware class.

    Middleware can intercept and modify operations at various hook points.
    """

    @property
    def name(self) -> str:
        """Middleware name."""
        return self.__class__.__name__

    def pre_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Called before a tool is executed.

        Args:
            tool_name: Name of the tool
            arguments: Tool arguments

        Returns:
            Modified arguments
        """
        return arguments

    def post_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        result: Any,
    ) -> Any:
        """Called after a tool is executed.

        Args:
            tool_name: Name of the tool
            arguments: Tool arguments
            result: Tool result

        Returns:
            Modified result
        """
        return result

    def pre_message(self, message: dict[str, Any]) -> dict[str, Any]:
        """Called before a message is processed.

        Args:
            message: Message dictionary

        Returns:
            Modified message
        """
        return message

    def post_message(
        self,
        message: dict[str, Any],
        response: dict[str, Any],
    ) -> dict[str, Any]:
        """Called after a message is processed.

        Args:
            message: Original message
            response: Response dictionary

        Returns:
            Modified response
        """
        return response

    def pre_compress(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Called before context compression.

        Args:
            messages: Messages to compress

        Returns:
            Modified messages
        """
        return messages

    def post_compress(
        self,
        messages: list[dict[str, Any]],
        compressed: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Called after context compression.

        Args:
            messages: Original messages
            compressed: Compressed messages

        Returns:
            Modified compressed messages
        """
        return compressed

    def on_error(self, error: Exception, context: dict[str, Any]) -> Exception:
        """Called when an error occurs.

        Args:
            error: The exception
            context: Error context

        Returns:
            Possibly modified exception
        """
        return error

    def on_session_start(self, session_id: str, context: dict[str, Any]) -> None:
        """Called when a session starts."""
        pass

    def on_session_end(
        self,
        session_id: str,
        messages: list[dict[str, Any]],
    ) -> None:
        """Called when a session ends."""
        pass


class MiddlewarePipeline:
    """Pipeline for executing middleware in order."""

    def __init__(self):
        self._middlewares: list[Middleware] = []

    def add(self, middleware: Middleware) -> "MiddlewarePipeline":
        """Add middleware to the pipeline.

        Args:
            middleware: Middleware instance

        Returns:
            Self for chaining
        """
        self._middlewares.append(middleware)
        return self

    def execute_pre_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute pre_tool_call hooks."""
        for mw in self._middlewares:
            arguments = mw.pre_tool_call(tool_name, arguments)
        return arguments

    def execute_post_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        result: Any,
    ) -> Any:
        """Execute post_tool_call hooks."""
        for mw in self._middlewares:
            result = mw.post_tool_call(tool_name, arguments, result)
        return result

    def execute_pre_message(self, message: dict[str, Any]) -> dict[str, Any]:
        """Execute pre_message hooks."""
        for mw in self._middlewares:
            message = mw.pre_message(message)
        return message

    def execute_post_message(
        self,
        message: dict[str, Any],
        response: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute post_message hooks."""
        for mw in self._middlewares:
            response = mw.post_message(message, response)
        return response

    def execute_pre_compress(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Execute pre_compress hooks."""
        for mw in self._middlewares:
            messages = mw.pre_compress(messages)
        return messages

    def execute_post_compress(
        self,
        messages: list[dict[str, Any]],
        compressed: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Execute post_compress hooks."""
        for mw in self._middlewares:
            compressed = mw.post_compress(messages, compressed)
        return compressed

    def execute_on_error(
        self,
        error: Exception,
        context: dict[str, Any],
    ) -> Exception:
        """Execute on_error hooks."""
        for mw in self._middlewares:
            error = mw.on_error(error, context)
        return error


class EnhancedPlugin:
    """Enhanced plugin with middleware support."""

    def __init__(
        self,
        name: str,
        version: str = "1.0.0",
        description: str = "",
        middleware: list[Middleware] | None = None,
    ):
        self.name = name
        self.version = version
        self.description = description
        self._middleware = middleware or []
        self._enabled = True

    @property
    def middleware(self) -> list[Middleware]:
        """Get plugin middleware."""
        return self._middleware

    def enable(self):
        """Enable the plugin."""
        self._enabled = True

    def disable(self):
        """Disable the plugin."""
        self._enabled = False

    @property
    def is_enabled(self) -> bool:
        """Check if plugin is enabled."""
        return self._enabled


class EnhancedPluginRegistry:
    """Enhanced plugin registry with middleware support."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._plugins: dict[str, EnhancedPlugin] = {}
            cls._instance._middleware_pipeline = MiddlewarePipeline()
            cls._instance._enabled_middleware: list[Middleware] = []
        return cls._instance

    def register(
        self,
        plugin: EnhancedPlugin,
        middleware: list[Middleware] | None = None,
    ) -> None:
        """Register a plugin.

        Args:
            plugin: Plugin instance
            middleware: Optional middleware for this plugin
        """
        self._plugins[plugin.name] = plugin

        if middleware:
            for mw in middleware:
                self._middleware_pipeline.add(mw)
                self._enabled_middleware.append(mw)

        logger.info(f"Registered plugin: {plugin.name} v{plugin.version}")

    def unregister(self, name: str) -> None:
        """Unregister a plugin.

        Args:
            name: Plugin name
        """
        if name in self._plugins:
            plugin = self._plugins[name]
            for mw in plugin.middleware:
                if mw in self._enabled_middleware:
                    self._enabled_middleware.remove(mw)
            del self._plugins[name]
            logger.info(f"Unregistered plugin: {name}")

    def get_plugin(self, name: str) -> EnhancedPlugin | None:
        """Get a plugin by name."""
        return self._plugins.get(name)

    def list_plugins(self) -> list[EnhancedPlugin]:
        """List all plugins."""
        return list(self._plugins.values())

    def get_middleware_pipeline(self) -> MiddlewarePipeline:
        """Get the middleware pipeline."""
        return self._middleware_pipeline

    def enable_plugin(self, name: str) -> None:
        """Enable a plugin."""
        plugin = self._plugins.get(name)
        if plugin:
            plugin.enable()
            for mw in plugin.middleware:
                if mw not in self._enabled_middleware:
                    self._middleware_pipeline.add(mw)
                    self._enabled_middleware.append(mw)

    def disable_plugin(self, name: str) -> None:
        """Disable a plugin."""
        plugin = self._plugins.get(name)
        if plugin:
            plugin.disable()
            for mw in plugin.middleware:
                if mw in self._enabled_middleware:
                    self._enabled_middleware.remove(mw)


_global_registry: EnhancedPluginRegistry | None = None


def get_plugin_registry() -> EnhancedPluginRegistry:
    """Get the global plugin registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = EnhancedPluginRegistry()
    return _global_registry


def register_plugin(
    plugin: EnhancedPlugin,
    middleware: list[Middleware] | None = None,
) -> None:
    """Register a plugin.

    Args:
        plugin: Plugin instance
        middleware: Optional middleware
    """
    get_plugin_registry().register(plugin, middleware)


class LoggingMiddleware(Middleware):
    """Middleware for logging operations."""

    def __init__(self, logger_name: str = "prometheus"):
        self._logger = logging.getLogger(logger_name)

    def pre_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self._logger.debug(f"Tool call: {tool_name}({arguments})")
        return arguments

    def post_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        result: Any,
    ) -> Any:
        self._logger.debug(f"Tool result: {tool_name} -> {str(result)[:100]}")
        return result

    def on_error(self, error: Exception, context: dict[str, Any]) -> Exception:
        self._logger.error(f"Error in {context.get('operation', 'unknown')}: {error}")
        return error


class MetricsMiddleware(Middleware):
    """Middleware for collecting metrics."""

    def __init__(self):
        self._tool_call_count = 0
        self._error_count = 0
        self._total_tokens = 0

    def pre_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self._tool_call_count += 1
        return arguments

    def on_error(self, error: Exception, context: dict[str, Any]) -> Exception:
        self._error_count += 1
        return error

    def get_metrics(self) -> dict[str, Any]:
        """Get collected metrics."""
        return {
            "tool_call_count": self._tool_call_count,
            "error_count": self._error_count,
            "total_tokens": self._total_tokens,
        }
