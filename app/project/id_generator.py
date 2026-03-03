"""
OpenPipeFlow — Auto-ID generator.
Produces human-readable IDs like PIPE-001, VLV-003, SRC-001, etc.
"""

from app.utils.constants import ID_PREFIX


class IDGenerator:
    """Maintains per-type counters and generates the next available ID."""

    def __init__(self):
        # Maps element_type -> next integer counter
        self._counters: dict[str, int] = {}

    def next_id(self, element_type: str) -> str:
        """Return the next unused ID for *element_type*, e.g. 'PIPE-007'."""
        prefix = ID_PREFIX.get(element_type, element_type.upper()[:3])
        n = self._counters.get(element_type, 1)
        self._counters[element_type] = n + 1
        return f"{prefix}-{n:03d}"

    def reset(self):
        """Reset all counters (called on New Project)."""
        self._counters.clear()

    def load_state(self, state: dict):
        """Restore counter state from a saved project (so new IDs won't clash)."""
        self._counters = {k: v for k, v in state.items()}

    def save_state(self) -> dict:
        """Serialise counter state for project save."""
        return dict(self._counters)


# Module-level singleton shared across the whole app
_generator = IDGenerator()


def next_id(element_type: str) -> str:
    return _generator.next_id(element_type)


def reset():
    _generator.reset()


def load_state(state: dict):
    _generator.load_state(state)


def save_state() -> dict:
    return _generator.save_state()
