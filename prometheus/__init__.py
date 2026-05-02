"""Prometheus Agent Framework — 硅基生命造物主框架.

Public API for the Prometheus Agent framework.
"""

__version__ = "0.8.0"

# Lazy imports — only load when actually accessed.
# This avoids circular-dependency issues during pip install.
# fmt: off
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
    "PrometheusConfig",
    "load_config",
    "save_config",
    "is_managed",
]

def __getattr__(name):
    if name == "get_paths":
        from prometheus._paths import get_paths
        return get_paths
    if name == "get_state":
        from prometheus._state import get_state
        return get_state
    if name in ("PrometheusConfig", "load_config", "save_config", "is_managed"):
        from prometheus.config import PrometheusConfig, is_managed, load_config, save_config
        return {"PrometheusConfig": PrometheusConfig, "load_config": load_config, "save_config": save_config, "is_managed": is_managed}[name]
    if name in ("EvolutionGuard", "FireKeeper", "PrometheusLifecycle", "SoulOrchestrator"):
        from prometheus.framework import (
            EvolutionGuard,
            FireKeeper,
            PrometheusLifecycle,
            SoulOrchestrator,
        )
        return {"EvolutionGuard": EvolutionGuard, "FireKeeper": FireKeeper, "PrometheusLifecycle": PrometheusLifecycle, "SoulOrchestrator": SoulOrchestrator}[name]
    if name in ("PrometheusMode", "ToolHooks"):
        from prometheus.integration import PrometheusMode, ToolHooks
        return {"PrometheusMode": PrometheusMode, "ToolHooks": ToolHooks}[name]
    if name == "PrometheusOrchestrator":
        from prometheus.orchestrator import PrometheusOrchestrator
        return PrometheusOrchestrator
    if name == "registry":
        from prometheus.tools.registry import registry
        return registry
    if name in ("AppendResult", "Chronicler", "StampResult", "TraceReport", "format_trace_report"):
        from prometheus.chronicler import (
            AppendResult,
            Chronicler,
            StampResult,
            TraceReport,
            format_trace_report,
        )
        return {"AppendResult": AppendResult, "Chronicler": Chronicler, "StampResult": StampResult, "TraceReport": TraceReport, "format_trace_report": format_trace_report}[name]
    if name in ("FOUNDER_CHRONICLE_SIGNATURE", "FOUNDER_TAG_LEXICON", "FOUNDER_TAGS", "IMMUTABLE_GENES", "SNAPSHOT_DIR", "TEMPLATE_TTG", "DormancyGuard", "PrometheusAPI", "SeedGardener", "_update_genealogy", "_verify_founder_chronicle", "cmd_audit", "cmd_create", "cmd_decode", "cmd_edit", "cmd_genes", "cmd_lexicon", "cmd_view", "inject_founder_chronicle", "load_seed", "save_seed", "save_snapshot"):
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
        return {"FOUNDER_CHRONICLE_SIGNATURE": FOUNDER_CHRONICLE_SIGNATURE, "FOUNDER_TAG_LEXICON": FOUNDER_TAG_LEXICON, "FOUNDER_TAGS": FOUNDER_TAGS, "IMMUTABLE_GENES": IMMUTABLE_GENES, "SNAPSHOT_DIR": SNAPSHOT_DIR, "TEMPLATE_TTG": TEMPLATE_TTG, "DormancyGuard": DormancyGuard, "PrometheusAPI": PrometheusAPI, "SeedGardener": SeedGardener, "_update_genealogy": _update_genealogy, "_verify_founder_chronicle": _verify_founder_chronicle, "cmd_audit": cmd_audit, "cmd_create": cmd_create, "cmd_decode": cmd_decode, "cmd_edit": cmd_edit, "cmd_genes": cmd_genes, "cmd_lexicon": cmd_lexicon, "cmd_view": cmd_view, "inject_founder_chronicle": inject_founder_chronicle, "load_seed": load_seed, "save_seed": save_seed, "save_snapshot": save_snapshot}[name]
    if name in ("Classification", "FormatAgnosticReader", "LineageAnchor", "SeedIdentity", "SeedReading", "SemanticAuditEngine"):
        from prometheus.semantic_audit import (
            Classification,
            FormatAgnosticReader,
            LineageAnchor,
            SeedIdentity,
            SeedReading,
            SemanticAuditEngine,
        )
        return {"Classification": Classification, "FormatAgnosticReader": FormatAgnosticReader, "LineageAnchor": LineageAnchor, "SeedIdentity": SeedIdentity, "SeedReading": SeedReading, "SemanticAuditEngine": SemanticAuditEngine}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
