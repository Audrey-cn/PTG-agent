#!/usr/bin/env python3
"""
网络加速器模块
"""

from .net_accelerator import (
    AccelerateResult,
    AcceleratorNode,
    NetAccelerator,
    Platform,
    accelerate_fetch,
    get_accelerator,
)

__all__ = [
    "NetAccelerator",
    "AcceleratorNode",
    "AccelerateResult",
    "Platform",
    "get_accelerator",
    "accelerate_fetch",
]
