"""Raised when plugin metadata fails a trust check."""


class PluginTrustError(Exception):
    """Plugin metadata violated a trust invariant (e.g. wrong plugin_type for a HookPluginBase)."""
