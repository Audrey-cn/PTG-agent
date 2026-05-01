"""Monkey patches for making prometheus-agent tools work inside async frameworks (Atropos)."""

import logging

logger = logging.getLogger(__name__)

_patches_applied = False


def apply_patches():
    """Apply all monkey patches needed for Atropos compatibility."""
    global _patches_applied
    if _patches_applied:
        return

    logger.debug("apply_patches() called; no patches needed (async safety is built-in)")
    _patches_applied = True
