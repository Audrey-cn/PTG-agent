"""Cloud browser provider abstraction.

Import the ABC so callers can do::

    from prometheus.tools.browser_providers import CloudBrowserProvider
"""

from prometheus.tools.browser_providers.base import CloudBrowserProvider

__all__ = ["CloudBrowserProvider"]
