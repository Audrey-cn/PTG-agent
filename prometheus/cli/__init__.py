"""Prometheus CLI 包."""

__version__ = "0.8.0"

from .main import (
    build_parser,
    cmd_config,
    cmd_dict,
    cmd_doctor,
    cmd_gene,
    cmd_kb,
    cmd_memory,
    cmd_model,
    cmd_seed,
    cmd_setup,
    cmd_status,
    cmd_update,
    main,
)

__all__ = [
    "cmd_setup",
    "cmd_doctor",
    "cmd_model",
    "cmd_config",
    "cmd_status",
    "cmd_seed",
    "cmd_gene",
    "cmd_memory",
    "cmd_kb",
    "cmd_dict",
    "cmd_update",
    "build_parser",
    "main",
]
