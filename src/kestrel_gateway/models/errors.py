from pydantic import BaseModel


class GatewayError(BaseModel):
    error: str
    code: str
    tool: str
    retriable: bool = False


def authorization_error(tool: str, reason: str) -> GatewayError:
    return GatewayError(error=reason, code="AUTHORIZATION_DENIED", tool=tool)


def kill_switch_error(tool: str, reason: str) -> GatewayError:
    return GatewayError(error=reason, code="KILL_SWITCH_ACTIVE", tool=tool)


def rate_limit_error(tool: str, team: str) -> GatewayError:
    return GatewayError(
        error=f"Rate limit exceeded for team '{team}' on tool '{tool}'. Try again shortly.",
        code="RATE_LIMIT_EXCEEDED",
        tool=tool,
        retriable=True,
    )


def approval_required_error(tool: str, approval_id: str) -> GatewayError:
    return GatewayError(
        error=f"Human approval required. Approval ID: {approval_id}. This operation is irreversible or financially committing.",
        code="APPROVAL_REQUIRED",
        tool=tool,
    )


def upstream_error(tool: str, status: int, message: str) -> GatewayError:
    return GatewayError(
        error=f"Upstream system returned status {status}: {message}",
        code="UPSTREAM_ERROR",
        tool=tool,
        retriable=status >= 500,
    )


def validation_error(tool: str, message: str) -> GatewayError:
    return GatewayError(error=message, code="VALIDATION_ERROR", tool=tool)
