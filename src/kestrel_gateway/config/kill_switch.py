from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

from pydantic import BaseModel


class KillSwitchState(BaseModel):
    gateway_enabled: bool = True
    teams_disabled: list[str] = []
    tools_disabled: list[str] = []


class KillSwitch:
    def __init__(self, path: str):
        self._path = Path(path)
        self._state = KillSwitchState()
        self._last_mtime: float = 0
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            mtime = os.path.getmtime(self._path)
            if mtime != self._last_mtime:
                raw = json.loads(self._path.read_text())
                self._state = KillSwitchState(**raw)
                self._last_mtime = mtime
        else:
            self._state = KillSwitchState()

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._state.model_dump(), indent=2))
        self._last_mtime = os.path.getmtime(self._path)

    def check(self, tool_name: str, team: str) -> Optional[str]:
        self._load()
        if not self._state.gateway_enabled:
            return "Gateway is disabled"
        if team in self._state.teams_disabled:
            return f"Team '{team}' is disabled"
        if tool_name in self._state.tools_disabled:
            return f"Tool '{tool_name}' is disabled"
        return None

    def disable_gateway(self) -> None:
        self._state.gateway_enabled = False
        self._save()

    def enable_gateway(self) -> None:
        self._state.gateway_enabled = True
        self._save()

    def disable_team(self, team: str) -> None:
        if team not in self._state.teams_disabled:
            self._state.teams_disabled.append(team)
            self._save()

    def enable_team(self, team: str) -> None:
        if team in self._state.teams_disabled:
            self._state.teams_disabled.remove(team)
            self._save()

    def disable_tool(self, tool: str) -> None:
        if tool not in self._state.tools_disabled:
            self._state.tools_disabled.append(tool)
            self._save()

    def enable_tool(self, tool: str) -> None:
        if tool in self._state.tools_disabled:
            self._state.tools_disabled.remove(tool)
            self._save()
