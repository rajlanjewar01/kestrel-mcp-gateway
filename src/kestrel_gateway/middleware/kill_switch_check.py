"""Thin wrapper around :class:`KillSwitch` for use in the middleware pipeline."""

from __future__ import annotations

from typing import Optional

from kestrel_gateway.config.kill_switch import KillSwitch


def check_kill_switch(kill_switch: KillSwitch, tool_name: str, team: str) -> Optional[str]:
    """Return ``None`` if the call is permitted, or an error message if blocked."""
    return kill_switch.check(tool_name, team)
