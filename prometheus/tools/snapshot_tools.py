"""Snapshot and restore tools."""

from prometheus.tools.security.registry import registry, tool_error, tool_result


def create_snapshot_tool(args):
    """
    Create snapshot tool

    Args:
        name: Snapshot name (optional)
        message: Snapshot message (optional)
    """
    try:
        from prometheus.checkpoint_system import get_checkpoint_system, get_session_logger
    except ImportError:
        from checkpoint_system import get_checkpoint_system, get_session_logger

    name = args.get("name")
    message = args.get("message")

    cp_sys = get_checkpoint_system()
    session_logger = get_session_logger()

    additional_state = {}
    if message:
        additional_state["message"] = message

    cp = cp_sys.create_snapshot(name, additional_state)
    session_logger.log_snapshot(cp.name)

    return tool_result(
        {
            "success": True,
            "name": cp.name,
            "timestamp": cp.timestamp,
            "state": cp.state,
            "message": "Snapshot created",
        }
    )


registry.register(
    name="create_snapshot",
    toolset="snapshot",
    schema={
        "name": "create_snapshot",
        "description": "Create system state snapshot, save critical files and current state",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Snapshot name (optional, auto-generated)",
                },
                "message": {"type": "string", "description": "Snapshot message (optional)"},
            },
            "required": [],
        },
    },
    handler=create_snapshot_tool,
    description="Create snapshot: Save current system state",
    emoji="📸",
)


def list_snapshots_tool(args):
    """
    List snapshots tool

    Args:
        limit: Number of snapshots to return (optional)
    """
    try:
        from prometheus.checkpoint_system import get_checkpoint_system
    except ImportError:
        from checkpoint_system import get_checkpoint_system

    limit = args.get("limit", 50)

    cp_sys = get_checkpoint_system()
    snapshots = cp_sys.list_snapshots()

    limited_snapshots = snapshots[:limit]

    return tool_result(
        {
            "success": True,
            "count": len(limited_snapshots),
            "total": len(snapshots),
            "snapshots": limited_snapshots,
        }
    )


registry.register(
    name="list_snapshots",
    toolset="snapshot",
    schema={
        "name": "list_snapshots",
        "description": "List all available snapshots",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Limit number of snapshots returned (optional, default 50)",
                }
            },
            "required": [],
        },
    },
    handler=list_snapshots_tool,
    description="List snapshots: Display all available snapshots",
    emoji="📋",
)


def get_snapshot_tool(args):
    """
    Get snapshot details tool

    Args:
        name: Snapshot name
    """
    try:
        from prometheus.checkpoint_system import get_checkpoint_system
    except ImportError:
        from checkpoint_system import get_checkpoint_system

    name = args.get("name", "latest")

    if not name:
        return tool_error("Missing name parameter")

    cp_sys = get_checkpoint_system()
    cp = cp_sys.get_snapshot(name)

    if not cp:
        return tool_error(f"Snapshot not found: {name}")

    return tool_result(
        {
            "success": True,
            "name": cp.name,
            "timestamp": cp.timestamp,
            "state": cp.state,
            "checksums": cp.checksums,
        }
    )


registry.register(
    name="get_snapshot",
    toolset="snapshot",
    schema={
        "name": "get_snapshot",
        "description": "Get details of specific snapshot",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Snapshot name (default latest)"}
            },
            "required": [],
        },
    },
    handler=get_snapshot_tool,
    description="Get snapshot: View snapshot details",
    emoji="🔍",
)


def restore_snapshot_tool(args):
    """
    Restore snapshot tool

    Args:
        name: Snapshot name
        confirm: Whether to confirm restore (optional, default false, only check)
    """
    try:
        from prometheus.checkpoint_system import get_checkpoint_system
    except ImportError:
        from checkpoint_system import get_checkpoint_system

    name = args.get("name", "latest")
    confirm = args.get("confirm", False)

    cp_sys = get_checkpoint_system()
    result = cp_sys.restore_snapshot(name, confirm)

    return tool_result(result)


registry.register(
    name="restore_snapshot",
    toolset="snapshot",
    schema={
        "name": "restore_snapshot",
        "description": "Restore to specified snapshot state (default only checks differences, set confirm=true to execute)",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Snapshot name (default latest)"},
                "confirm": {
                    "type": "boolean",
                    "description": "Whether to confirm execution (default false)",
                },
            },
            "required": [],
        },
    },
    handler=restore_snapshot_tool,
    description="Restore snapshot: Revert to previous state",
    emoji="↩️",
)


def resume_session_tool(args):
    """
    Resume session tool

    Args:
        query: Semantic query (optional, used to find related sessions)
    """
    try:
        from prometheus.checkpoint_system import get_checkpoint_system, get_session_logger
    except ImportError:
        from checkpoint_system import get_checkpoint_system

    args.get("query")

    cp_sys = get_checkpoint_system()

    latest = cp_sys.get_snapshot("latest")

    session_info = {
        "has_latest_snapshot": latest is not None,
        "latest": latest.to_dict() if latest else None,
    }

    return tool_result(
        {"success": True, "session": session_info, "message": "Session state retrieved"}
    )


registry.register(
    name="resume_session",
    toolset="snapshot",
    schema={
        "name": "resume_session",
        "description": "Resume previous session state, supports semantic query to find related sessions",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Semantic query (optional, used to find related sessions)",
                }
            },
            "required": [],
        },
    },
    handler=resume_session_tool,
    description="Resume session: Continue previous work",
    emoji="🔄",
)


def log_event_tool(args):
    """
    Log event tool

    Args:
        event_type: Event type
        data: Event data (optional)
    """
    try:
        from prometheus.checkpoint_system import get_session_logger
    except ImportError:
        from checkpoint_system import get_session_logger

    event_type = args.get("event_type")
    data = args.get("data", {})

    if not event_type:
        return tool_error("Missing event_type parameter")

    session_logger = get_session_logger()
    session_logger.log_event(event_type, **data)

    return tool_result(
        {"success": True, "event_type": event_type, "data": data, "message": "Event logged"}
    )


registry.register(
    name="log_event",
    toolset="snapshot",
    schema={
        "name": "log_event",
        "description": "Log session events",
        "parameters": {
            "type": "object",
            "properties": {
                "event_type": {"type": "string", "description": "Event type"},
                "data": {"type": "object", "description": "Event data (optional)"},
            },
            "required": ["event_type"],
        },
    },
    handler=log_event_tool,
    description="Log event: Record session events",
    emoji="📝",
)


def auto_snapshot_on_event_tool(args):
    """
    Event-triggered auto snapshot tool

    Args:
        event_type: Event type
        context: Event context (optional)
        force: Whether to force snapshot
        min_interval_minutes: Minimum interval in minutes
    """
    try:
        from prometheus.auto_snapshot import get_auto_snapshot_manager
    except ImportError:
        from auto_snapshot import get_auto_snapshot_manager

    event_type = args.get("event_type")
    context = args.get("context")
    force = args.get("force", False)
    min_interval = args.get("min_interval_minutes", 5)

    if not event_type:
        return tool_error("Missing event_type parameter")

    manager = get_auto_snapshot_manager()
    success = manager.snapshot_on_event(
        event_type=event_type, context=context, force=force, min_interval_minutes=min_interval
    )

    return tool_result(
        {
            "success": success,
            "event_type": event_type,
            "message": "Auto snapshot created"
            if success
            else "Snapshot not created (interval too short)",
        }
    )


registry.register(
    name="auto_snapshot_on_event",
    toolset="snapshot",
    schema={
        "name": "auto_snapshot_on_event",
        "description": "Auto snapshot triggered by events",
        "parameters": {
            "type": "object",
            "properties": {
                "event_type": {
                    "type": "string",
                    "description": "Event type (like config_change, error, important_action)",
                },
                "context": {"type": "object", "description": "Event context (optional)"},
                "force": {
                    "type": "boolean",
                    "description": "Whether to force creation (ignore interval limit)",
                },
                "min_interval_minutes": {
                    "type": "integer",
                    "description": "Minimum snapshot interval in minutes (default 5)",
                },
            },
            "required": ["event_type"],
        },
    },
    handler=auto_snapshot_on_event_tool,
    description="Event snapshot: Auto-save triggered by events",
    emoji="⚡",
)


def get_session_logs_tool(args):
    """
    Get session logs tool

    Args:
        limit: Limit on number of logs returned
    """
    try:
        from prometheus.checkpoint_system import get_session_logger
    except ImportError:
        from checkpoint_system import get_session_logger

    limit = args.get("limit", 50)

    logger = get_session_logger()
    events = logger.get_recent_events(limit)

    return tool_result({"success": True, "count": len(events), "events": events})


registry.register(
    name="get_session_logs",
    toolset="snapshot",
    schema={
        "name": "get_session_logs",
        "description": "Get recent session event logs",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Limit number of logs returned (default 50)",
                }
            },
            "required": [],
        },
    },
    handler=get_session_logs_tool,
    description="View logs: Get session event records",
    emoji="📋",
)
