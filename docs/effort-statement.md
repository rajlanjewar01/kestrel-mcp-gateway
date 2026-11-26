# Effort Statement

**Total declared effort:** Approximately 20-25 hours

---

## Phase Breakdown

### Phase 1: Research & Design (5-6 hours)

- Read the platform requirements (CR-1 through CR-8) and the brief's system descriptions.
- Mapped each team's access needs against each system's capabilities.
- Identified the composition risk as the central design challenge: individually-approved access combining to leak data.
- Decided on the three-layer authorisation model (tool ACL, row scope, composition guard).
- Documented the four tools that would not be exposed, and the reasoning for each.
- Decided on the unattended operation position (deny writes, allow reads).

### Phase 2: Implementation — Core Gateway (6-8 hours)

- Built the MCP server skeleton (`server.py`), including tool definitions with `[READ]`/`[WRITE]` prefixes, enum-constrained parameters, and the 12-step `_handle_tool_call` pipeline.
- Implemented the authorisation model: `policy.py` (tool ACL + row scope), `composition_guard.py` (session tracking + result filtering), `approval.py` (approval gate for state-changing operations).
- Implemented the middleware chain: `rate_limiter.py` (sliding-window per-team/per-system/per-tool), `sanitizer.py` (allowlist search filter, injection stripping, content boundary wrapping), `audit.py` (JSON-lines logger), `kill_switch.py` (file-based with mtime check).
- Built the `BaseClient` with credential stripping and the four system-specific clients.
- Configuration: `GatewaySettings` via Pydantic BaseSettings, `teams.py` for the ACL matrix and rate limit tables.

### Phase 3: Implementation — Stubs & Testing (4-5 hours)

- Built FastAPI stub servers for all four upstream systems with seed data.
- Built the test infrastructure: `conftest.py` with in-process ASGI transport (no network), fixtures for all four caller identities.
- Wrote authorization tests covering the full tool x team matrix (positive and negative).
- Wrote rate limiting, sanitisation, kill switch, and approval gate tests.

### Phase 4: Documentation & ADRs (4-5 hours)

- ADR-001: Gateway architecture (the main decision document).
- ADR-002: Authorisation model (the deep dive on the three-layer model and the full ACL matrix).
- ADR-003: Unattended operation (the position on autonomous writes).
- Composition analysis (the key security deliverable, per-team).
- Tools not exposed (the four excluded operations with reasoning).
- Reflection, effort statement, and PMAT report.

### Phase 5: Integration & Polish (1-2 hours)

- Docker Compose setup for gateway + stubs.
- README with quick-start instructions.
- Cross-reference checks between ADRs and code.
- Final review of composition analysis against implementation.

---

## What Was Cut or Simplified

- **Streamable HTTP transport** was not fully implemented; the gateway runs on stdio for testing. The production transport path is documented in ADR-001 but would require additional work (HTTP server wrapper, header extraction middleware).
- **Approval gate workflow** is simplified: the gate returns `APPROVAL_REQUIRED` and the calling system must resubmit. A production system would need a callback mechanism or polling endpoint. The current implementation supports a test mode (`auto_approve`) for integration testing.
- **Composition guard session tracking** uses an in-memory dictionary. A production system would need persistence (Redis or similar) to survive gateway restarts and to support multiple gateway instances.
- **Load testing** of the ticketing system rate limit was not performed. The 100 rpm per team limit is a judgment call, not an empirically-derived number.
- **The `ticket_comment` site validation** was identified as a gap in the composition analysis but not implemented. The fix requires a round-trip to the ticketing system.
- **Cross-session composition analysis** was identified as a future need in ADR-002 but not implemented. The current guard tracks within a single user session only.
