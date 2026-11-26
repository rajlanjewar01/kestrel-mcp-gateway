# ADR-002: Authorisation Model

| Field       | Value                                      |
|-------------|--------------------------------------------|
| Status      | Accepted                                   |
| Date        | 2026-11-26                                 |
| Decision-makers | Priya Raghunathan (Platform Lead), Security Engineering |
| Related     | ADR-001 (Gateway Architecture), composition-analysis.md |

---

## 1. Context

Each of the four teams' access to the four backend systems was reviewed and approved independently by Integration Engineering. The individual approvals are reasonable: Warehouse Ops needs stock lookups, Customer Service needs ticket management, Finance Analytics needs contract visibility. No single access grant is alarming.

The problem is *composition*. Integration Engineering admits that cross-system access was reviewed per-team, per-system, not per-team across systems. The question "what can Customer Service reach by combining calls to SYS-3 and SYS-4?" was never asked during the original access reviews.

This ADR documents the three-layer authorisation model that addresses both individual access control and composition risk.

---

## 2. Decision

Authorise every tool call through three sequential layers:

1. **Tool ACL** — static, deterministic, fails closed.
2. **Row-level scope** — restricts which records within a permitted tool a caller can access.
3. **Composition guard** — detects and blocks patterns of calls that would allow data assembly beyond the caller's intended access.

A call must pass all three layers. Each layer logs its decision. If any layer denies, the remaining layers do not execute.

---

## 3. Tool ACL Matrix

The full 11-tool x 4-team matrix, as implemented in `TOOL_ACL` in `config/teams.py`:

| Tool | Warehouse Ops | Transport Planning | Customer Service | Finance Analytics |
|------|:---:|:---:|:---:|:---:|
| `wms_stock_lookup` | ALLOW | ALLOW | ALLOW | ALLOW |
| `tms_dock_schedule` | DENY | ALLOW | DENY | ALLOW |
| `tms_booking_lookup` | DENY | ALLOW | DENY | ALLOW |
| `tms_booking_create` | DENY | ALLOW | DENY | DENY |
| `tms_booking_cancel` | DENY | ALLOW | DENY | DENY |
| `ticket_search` | ALLOW | ALLOW | ALLOW | DENY |
| `ticket_create` | ALLOW | ALLOW | ALLOW | DENY |
| `ticket_comment` | ALLOW | DENY | ALLOW | DENY |
| `ticket_close` | DENY | DENY | ALLOW | DENY |
| `contract_lookup` | DENY | DENY | ALLOW | ALLOW |
| `rate_card_lookup` | DENY | DENY | DENY | ALLOW |

**Matrix properties:**

- **44 cells total.** Every cell is an explicit decision — there is no "inherit" or "default allow."
- **Finance Analytics is read-only.** It has no ALLOW on any write tool (`tms_booking_create`, `tms_booking_cancel`, `ticket_create`, `ticket_comment`, `ticket_close`).
- **Transport Planning cannot comment or close tickets.** It can search and create (for operational exceptions) but cannot add comments to or close tickets it did not create.
- **Customer Service has the broadest write access** (ticket operations + contract reads) but the narrowest data scope (per-customer).
- **`rate_card_lookup` is Finance-only.** This is the Commercial Director's requirement: no team that interacts with individual customers should see negotiated rate schedules.

### 3.1 Operations Not in the Matrix

Four upstream operations are not represented in the matrix because they are not exposed through the gateway at all:

| Operation | System | Reason |
|-----------|--------|--------|
| `ticket_delete` | SYS-3 | Hard delete, unrecoverable, injection risk |
| `contract_search` | SYS-4 | Unscoped free-text across all contracts including rate schedules |
| `wms_stock_adjust` | SYS-1 | Ledger-affecting, no undo, no team request |
| `wms_bin_move` | SYS-1 | Generates physical picker tasks, no team request |

---

## 4. Row-Level Scope Rules

The tool ACL determines *which tools* a team can call. Row-level scope determines *which records* within those tools they can access.

| Team | Scope Field | Mechanism | Implementation |
|------|------------|-----------|----------------|
| Warehouse Ops | `site` | Gateway pins the `site` parameter to the caller's assigned site. If the caller passes a different site, the request is denied. | `enforce_scope()` overwrites `site` argument; `authorize()` validates mismatch |
| Customer Service | `customer_id` | Gateway validates that the `customer_id` argument is in the caller's authorized customer list. | `authorize()` checks `customer_id` against `CallerIdentity.customer_ids` |
| Transport Planning | None (unrestricted) | Intentional — Transport Planning manages cross-site logistics. | No scope enforcement |
| Finance Analytics | None (unrestricted) | Intentional — Finance Analytics needs full visibility for reporting. | No scope enforcement |

### 4.1 Scope Enforcement vs. Validation

For Warehouse Ops, the gateway *enforces* scope by overwriting the `site` parameter. This means a SITE-01 Warehouse Ops caller can submit a request with `site: SITE-02` and the gateway will silently replace it with `site: SITE-01`. This is deliberate: it prevents a confused model from accidentally querying the wrong site, without returning an error that might cause the model to retry with different arguments.

For Customer Service, the gateway *validates* scope by checking the `customer_id` argument against the caller's authorised list. If the customer_id is not in the list, the request is denied with an `AUTHORIZATION_DENIED` error. This is because customer_id is an opaque identifier — the gateway cannot substitute a "correct" value.

---

## 5. Composition Analysis

The full composition analysis is in [composition-analysis.md](composition-analysis.md). This section summarises the key findings and the gateway's response.

### 5.1 Customer Service — The Primary Composition Risk

**Permitted tools:** `wms_stock_lookup`, `ticket_search`, `ticket_create`, `ticket_comment`, `ticket_close`, `contract_lookup`

**Composition scenario:** An agent acting for Customer Service could call `contract_lookup` for customer CUST-A, then call `ticket_search` without customer filtering. If the ticketing system returns tickets belonging to CUST-B, the agent now has cross-customer data: CUST-A's contract terms alongside CUST-B's operational issues.

**Gateway response:**
- `contract_search` is **not exposed** — there is no way to free-text search across contracts.
- `contract_lookup` requires a `customer_id` argument, which is validated against the caller's scope.
- `ticket_search` results are **filtered by the composition guard**: `CompositionGuard.filter_results()` removes tickets whose `customer_id` does not match the caller's authorized customers.
- `rate_card_lookup` is **ACL-denied** for Customer Service, so there is no path to commercially sensitive pricing through any tool combination.

### 5.2 Finance Analytics — Legitimate Broad Access, Rate-Controlled

**Permitted tools:** `wms_stock_lookup`, `tms_dock_schedule`, `tms_booking_lookup`, `contract_lookup`, `rate_card_lookup`

**Composition scenario:** Finance Analytics can read stock levels at all sites, all dock schedules, all bookings, all contracts, and all rate cards. This is *intended* — their role requires full visibility for financial reporting.

**Gateway response:** No composition block needed. Controls are:
- Read-only (no write tools in their ACL).
- `rate_card_lookup` is additionally capped at 10 rpm to prevent bulk extraction.
- All calls are logged, so bulk data access patterns are visible in the audit trail.

### 5.3 Transport Planning — Cross-Site by Design

**Permitted tools:** `wms_stock_lookup`, `tms_dock_schedule`, `tms_booking_lookup`, `tms_booking_create`, `tms_booking_cancel`, `ticket_search`, `ticket_create`

**Composition scenario:** Transport Planning can see stock at all sites and create bookings at any site. By combining stock lookups with booking creation, they could theoretically optimise routing. This is exactly their job.

**Gateway response:** No composition block needed. This team has the widest write access (booking create/cancel) but it is scoped to their operational domain (transport management). They cannot see contracts, rate cards, or close tickets.

### 5.4 Warehouse Ops — Naturally Isolated

**Permitted tools:** `wms_stock_lookup`, `ticket_search`, `ticket_create`, `ticket_comment`

**Composition scenario:** A Warehouse Ops caller at SITE-01 could try to search tickets at SITE-02 to gather information about another site's operational issues.

**Gateway response:** The `site` parameter is enforced by scope. All tool calls from a SITE-01 caller have their `site` argument pinned to `SITE-01`. There is no way to reach another site's data, even by combining tools.

---

## 6. What Is Blocked

| Blocked | Mechanism | Reason |
|---------|-----------|--------|
| `contract_search` for all teams | Not exposed | Unscoped free-text search across all contracts would allow cross-customer rate disclosure |
| `rate_card_lookup` for Customer Service | ACL DENY | Customer Service agents interact with individual customers; seeing other customers' rates violates commercial confidentiality |
| `rate_card_lookup` for Warehouse Ops | ACL DENY | No business need; Warehouse Ops has no commercial role |
| `rate_card_lookup` for Transport Planning | ACL DENY | Transport Planning books carriers, not customer rates |
| `ticket_delete` for all teams | Not exposed | Hard delete with no recovery |
| `wms_stock_adjust` for all teams | Not exposed | Ledger-affecting with no undo |
| `wms_bin_move` for all teams | Not exposed | Generates physical picker tasks |
| Cross-site queries for Warehouse Ops | Row scope enforcement | SITE-01 caller cannot query SITE-02 |
| Cross-customer queries for Customer Service | Row scope validation + composition filter | CUST-A caller cannot query CUST-B data |

---

## 7. Consequences

### Positive

- Every access path is explicitly decided, not inherited or defaulted.
- Composition risks are addressed at the architecture level, not left to agent prompting.
- The audit trail records which layer allowed or denied each call, making policy debugging tractable.

### Negative

- **Some legitimate queries may be blocked.** A Customer Service agent scoped to CUST-A cannot search contracts across all their assigned customers in a single call. They must call `contract_lookup` for each `customer_id` individually. This is a friction cost of per-customer scoping.
- **The composition guard adds latency.** The session history check and result filtering add processing time, though it is small (sub-millisecond for the current implementation).
- **Policy changes require code changes.** The ACL matrix is defined in Python (`config/teams.py`), not in a configuration file. Adding a team or changing permissions requires a code change, review, and redeployment. This is intentional (policy changes should be reviewed) but adds friction.

---

## 8. Revisit If...

- **Customer Service requests cross-customer contract search.** If there is a legitimate business case for a Customer Service agent to search contracts across multiple assigned customers (e.g., a multi-brand customer with separate IDs), consider a `contract_search_scoped` tool that accepts a list of customer_ids and validates all of them against the caller's scope.
- **A fifth team is onboarded.** Each new team requires a full row in the ACL matrix, a scope rule, and a composition analysis. The current model scales to around 10 teams before the matrix becomes unwieldy.
- **Session-based composition tracking proves insufficient.** The current composition guard tracks within a single user session. If attacks span multiple sessions (e.g., agent A fetches contracts, agent B fetches tickets, results are combined outside the gateway), consider cross-session composition analysis based on audit log correlation.
