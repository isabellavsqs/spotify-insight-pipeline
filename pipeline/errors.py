"""Shared exceptions."""


class Interrupted(RuntimeError):
    """Raised after saved progress when a run is stopped (--stop-after-jobs, Ctrl+C)."""
