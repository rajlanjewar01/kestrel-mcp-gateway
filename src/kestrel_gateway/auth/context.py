from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from kestrel_gateway.config.teams import Team


class CallerIdentity(BaseModel):
    team: Team
    user_id: str
    site: Optional[str] = None
    customer_ids: Optional[list[str]] = None

    @property
    def scope_label(self) -> str:
        if self.site:
            return f"site={self.site}"
        if self.customer_ids:
            return f"customers={','.join(self.customer_ids)}"
        return "unrestricted"
