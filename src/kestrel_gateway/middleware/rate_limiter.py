"""Token-bucket rate limiter with per-team, per-system budgets.

Uses a sliding window counter approach: each (team, system) pair gets a
bucket that refills every 60 seconds.  An additional per-tool limit is
applied for ``rate_card_lookup`` via RATE_CARD_LOOKUP_LIMIT.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from kestrel_gateway.config.teams import (
    RATE_CARD_LOOKUP_LIMIT,
    RATE_LIMITS,
    TOOL_TO_SYSTEM,
    Team,
)


@dataclass
class _Bucket:
    """Sliding-window counter for a single (team, system) or (team, tool) pair."""

    limit: int
    window_seconds: float = 60.0
    count: int = 0
    window_start: float = field(default_factory=time.monotonic)

    def _maybe_reset(self, now: float) -> None:
        if now - self.window_start >= self.window_seconds:
            self.count = 0
            self.window_start = now

    def allow(self) -> bool:
        now = time.monotonic()
        self._maybe_reset(now)
        if self.count >= self.limit:
            return False
        self.count += 1
        return True

    def remaining(self) -> int:
        now = time.monotonic()
        self._maybe_reset(now)
        return max(0, self.limit - self.count)


class RateLimiter:
    """Per-(team, system) and per-(team, tool) rate limiter."""

    def __init__(self) -> None:
        # Keyed by (team_value, system)
        self._system_buckets: dict[tuple[str, str], _Bucket] = {}
        # Keyed by (team_value, tool_name)
        self._tool_buckets: dict[tuple[str, str], _Bucket] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_system_bucket(self, team: str, system: str) -> Optional[_Bucket]:
        key = (team, system)
        if key not in self._system_buckets:
            system_limits = RATE_LIMITS.get(system)
            if system_limits is None:
                return None
            # Try matching the team enum value
            team_enum = _resolve_team(team)
            if team_enum is None or team_enum not in system_limits:
                return None
            self._system_buckets[key] = _Bucket(limit=system_limits[team_enum])
        return self._system_buckets[key]

    def _get_tool_bucket(self, team: str, tool_name: str) -> Optional[_Bucket]:
        key = (team, tool_name)
        if key not in self._tool_buckets:
            if tool_name != "rate_card_lookup":
                return None
            team_enum = _resolve_team(team)
            if team_enum is None or team_enum not in RATE_CARD_LOOKUP_LIMIT:
                return None
            self._tool_buckets[key] = _Bucket(limit=RATE_CARD_LOOKUP_LIMIT[team_enum])
        return self._tool_buckets[key]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, team: str, system: str, tool_name: str | None = None) -> bool:
        """Return ``True`` if the request is allowed, ``False`` if rate-limited."""
        bucket = self._get_system_bucket(team, system)
        if bucket is not None and not bucket.allow():
            return False

        # Additional per-tool limit (currently only rate_card_lookup)
        if tool_name is not None:
            tool_bucket = self._get_tool_bucket(team, tool_name)
            if tool_bucket is not None and not tool_bucket.allow():
                return False

        return True

    def get_remaining(self, team: str, system: str) -> int:
        """Return remaining requests in the current window for a (team, system) pair."""
        bucket = self._get_system_bucket(team, system)
        if bucket is None:
            return 0
        return bucket.remaining()

    def reset(self) -> None:
        """Clear all buckets (useful in tests)."""
        self._system_buckets.clear()
        self._tool_buckets.clear()


def _resolve_team(value: str) -> Optional[Team]:
    """Resolve a string to a ``Team`` enum member, or ``None``."""
    try:
        return Team(value)
    except ValueError:
        return None
