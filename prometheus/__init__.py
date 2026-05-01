"""Prometheus Agent Framework — 硅基生命造物主框架.

Public API for the Prometheus Agent framework.
"""

from prometheus.cli.main import __version__

from prometheus._paths import get_paths
from prometheus.chronicler import (
    AppendResult,
    Chronicler,
    StampResult,
    TraceReport,
    format_trace_report,
)
from prometheus.prometheus import (
    FOUNDER_CHRONICLE_SIGNATURE,
    FOUNDER_TAG_LEXICON,
    FOUNDER_TAGS,
    IMMUTABLE_GENES,
    SNAPSHOT_DIR,
    TEMPLATE_TTG,
    DormancyGuard,
    PrometheusAPI,
    SeedGardener,
    _update_genealogy,
    _verify_founder_chronicle,
    cmd_audit,
    cmd_create,
    cmd_decode,
    cmd_edit,
    cmd_genes,
    cmd_lexicon,
    cmd_view,
    inject_founder_chronicle,
    load_seed,
    save_seed,
    save_snapshot,
)
from prometheus.semantic_audit import (
    Classification,
    FormatAgnosticReader,
    LineageAnchor,
    SeedIdentity,
    SeedReading,
    SemanticAuditEngine,
)

try:
    from prometheus._state import get_state
    from prometheus.config import is_managed, load_config, save_config
    from prometheus.framework import (
        EvolutionGuard,
        FireKeeper,
        PrometheusLifecycle,
        SoulOrchestrator,
    )
    from prometheus.integration import (
        PrometheusMode,
        ToolHooks,
    )
    from prometheus.orchestrator import PrometheusOrchestrator
    from prometheus.tools.registry import registry

    _FRAMEWORK_AVAILABLE = True
except ImportError:
    _FRAMEWORK_AVAILABLE = False
    get_state = None
    EvolutionGuard = None
    FireKeeper = None
    PrometheusLifecycle = None
    SoulOrchestrator = None
    PrometheusMode = None
    ToolHooks = None
    PrometheusOrchestrator = None
    registry = None
    load_config = None
    save_config = None
    is_managed = None

__all__ = [
    "__version__",
    "FOUNDER_TAGS",
    "FOUNDER_TAG_LEXICON",
    "FOUNDER_CHRONICLE_SIGNATURE",
    "IMMUTABLE_GENES",
    "TEMPLATE_TTG",
    "SNAPSHOT_DIR",
    "inject_founder_chronicle",
    "_verify_founder_chronicle",
    "_update_genealogy",
    "load_seed",
    "save_seed",
    "save_snapshot",
    "cmd_view",
    "cmd_genes",
    "cmd_edit",
    "cmd_decode",
    "cmd_lexicon",
    "cmd_audit",
    "cmd_create",
    "PrometheusAPI",
    "SeedGardener",
    "DormancyGuard",
    "Chronicler",
    "StampResult",
    "TraceReport",
    "AppendResult",
    "format_trace_report",
    "FormatAgnosticReader",
    "SemanticAuditEngine",
    "SeedReading",
    "Classification",
    "LineageAnchor",
    "SeedIdentity",
    "get_paths",
    "get_state",
    "EvolutionGuard",
    "FireKeeper",
    "PrometheusLifecycle",
    "SoulOrchestrator",
    "PrometheusMode",
    "ToolHooks",
    "PrometheusOrchestrator",
    "registry",
    "load_config",
    "save_config",
    "is_managed",
]
