#!/usr/bin/env python3
"""
网络加速器模块
"""

from .net_accelerator import (
    NetAccelerator,
    AcceleratorNode,
    AccelerateResult,
    Platform,
    get_accelerator,
    accelerate_fetch,
)

__all__ = [
    "NetAccelerator",
    "AcceleratorNode",
    "AccelerateResult",
    "Platform",
    "get_accelerator",
    "accelerate_fetch",
]
