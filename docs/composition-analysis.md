# Composition Analysis

## Purpose

This document analyses what each team can reach by *combining* their individually-permitted tool calls. The question is not "can team X call tool Y" (that is the ACL matrix in ADR-002) but "can team X assemble data or trigger effects beyond their intended access by calling tools Y and Z in sequence?"

This is the key security deliverable of the gateway design. The tool ACL was designed per-team, per-system. This analysis was done per-team, across systems.

---

## 1. Customer Service — The Primary Composition Risk

### 1.1 Permitted Tools

| Tool | System | Access Type |
|------|--------|------------|
| `wms_stock_lookup` | SYS-1 | READ |
| `ticket_search` | SYS-3 | READ |
| `ticket_create` | SYS-3 | WRITE |
| `ticket_comment` | SYS-3 | WRITE |
| `ticket_close` | SYS-3 | WRITE (approval-gated) |
| `contract_lookup` | SYS-4 | READ |

### 1.2 Reachable Data

By combining these tools, a Customer Service agent scoped to CUST-A can reach:

- Stock levels at any site (via `wms_stock_lookup` — customer scope does not apply to stock, as customers do not own stock positions). This is intentional: Customer Service needs to tell a customer "your order is in stock at SITE-03."
- Ticket search results (via `ticket_search` — but filtered by the composition guard to only show tickets matching the caller's customer scope).
- Contract terms for CUST-A (via `contract_lookup` — `customer_id` validated against caller scope).

### 1.3 Composition Attack Scenarios

**Scenario 1: Cross-customer rate disclosure via contract_search**

| Step | Tool | Intent |
|------|------|--------|
| 1 | `contract_search` with query "rate" | Find all contracts mentioning rates |

**Risk:** Unscoped free-text search across all contracts would return CUST-B, CUST-C, etc. rate schedules alongside CUST-A's.

**Gateway defense:** `contract_search` is **not exposed through the gateway**. The tool does not exist in the tool definitions. There is no way for any team to perform a free-text search across contracts.

**Scenario 2: Cross-customer data assembly via ticket_search + contract_lookup**

| Step | Tool | Intent |
|------|------|--------|
| 1 | `contract_lookup` for customer_id=CUST-A | Read CUST-A's contract terms |
| 2 | `ticket_search` with query "CUST-B" | Search for tickets mentioning CUST-B |

**Risk:** If ticket_search returns CUST-B's tickets, the agent now has CUST-A's contract terms and CUST-B's operational issues in the same context. While each piece is from a different system, the combination reveals CUST-B's service quality to someone authorised only for CUST-A.

**Gateway defense:** The `CompositionGuard.filter_results()` method filters `ticket_search` results for Customer Service callers. Only tickets whose `customer_id` matches the caller's authorized customer list are returned. Tickets belonging to other customers are silently removed. The `result_filtered` flag is set to `true` in the audit record so the filtering is visible in logs.

**Scenario 3: Rate card access via rate_card_lookup**

| Step | Tool | Intent |
|------|------|--------|
| 1 | `rate_card_lookup` for customer_id=CUST-B | Read CUST-B's negotiated rates |

**Risk:** Customer Service seeing CUST-B's rates would violate commercial confidentiality. A Customer Service agent managing CUST-A should never see what CUST-B pays.

**Gateway defense:** `rate_card_lookup` is **ACL-denied** for Customer Service (only Finance Analytics has access). This is a first-layer block — the composition guard does not need to handle this case because it never reaches the composition layer. Additionally, as defense-in-depth, the composition guard explicitly checks for Customer Service calling `rate_card_lookup` and returns a `cross_customer_rate_disclosure` violation.

**Scenario 4: Ticket search operator injection**

| Step | Tool | Intent |
|------|------|--------|
| 1 | `ticket_search` with query "* OR customer_id:CUST-B" | Use Lucene operators to bypass customer filter |

**Risk:** If the ticketing system's search endpoint accepts Lucene syntax, a crafted query could bypass the gateway's customer filtering by returning results before the composition guard can filter them (e.g., using `_source` includes or aggregation queries that return counts rather than documents).

**Gateway defense:** `sanitize_search_query` strips all characters not matching `[a-zA-Z0-9\s\-.,']` from the query before it reaches the ticketing system. Lucene boolean operators (`AND`, `OR`, `NOT`) are stripped as whole words. The query `* OR customer_id:CUST-B` becomes `customer CUST-B` (a plain text search), which the composition guard then filters normally.

### 1.4 Residual Risk

Customer Service can see stock levels at all sites without customer scoping. This is accepted because stock positions are not customer-specific data — they represent Kestrel's inventory, not a customer's information. If a customer's stock is held in a dedicated area (e.g., bonded storage), the WMS should scope its response by customer. This is an upstream system responsibility, not a gateway responsibility.

---

## 2. Finance Analytics — Legitimate Broad Access, Rate-Controlled

### 2.1 Permitted Tools

| Tool | System | Access Type |
|------|--------|------------|
| `wms_stock_lookup` | SYS-1 | READ |
| `tms_dock_schedule` | SYS-2 | READ |
| `tms_booking_lookup` | SYS-2 | READ |
| `contract_lookup` | SYS-4 | READ |
| `rate_card_lookup` | SYS-4 | READ |

### 2.2 Reachable Data

Finance Analytics can read:

- Stock levels at all 11 sites.
- Dock schedules and bookings at all sites.
- Contract terms for all customers.
- Rate cards (negotiated pricing) for all customers.

This is the broadest data access of any team. It is also **entirely intentional**: Finance Analytics performs financial reporting, margin analysis, and cost optimization. They need full visibility.

### 2.3 Composition Attack Scenarios

**Scenario 1: Bulk rate card extraction**

| Step | Tool | Intent |
|------|------|--------|
| 1 | `contract_lookup` for all known customer_ids | Build a list of all customers |
| 2 | `rate_card_lookup` for each customer_id | Extract every customer's negotiated rates |

**Risk:** Even though Finance Analytics has legitimate access to rate cards, bulk extraction creates a data-at-rest risk. If the agent transcript is logged, stored, or transmitted, all customer rate cards are in one place.

**Gateway defense:** `rate_card_lookup` is capped at **10 requests per minute** for Finance Analytics. At this rate, extracting rate cards for 500 customers would take 50 minutes of continuous querying — visible in the audit trail and slow enough to trigger operational review. The rate limit makes bulk extraction impractical without making legitimate analytical work impossible (a Finance analyst querying 5-10 rate cards for a margin analysis is unaffected).

**Scenario 2: Cross-system financial intelligence**

| Step | Tool | Intent |
|------|------|--------|
| 1 | `tms_booking_lookup` for a carrier booking | See carrier costs |
| 2 | `rate_card_lookup` for the customer on that load | See what the customer pays |
| 3 | Compute margin | (In-context, not a tool call) |

**Risk:** This is not an attack — it is exactly what Finance Analytics is supposed to do. Including it here to document that this combination was reviewed and is intentional.

**Gateway defense:** None needed. All calls are logged.

### 2.4 Residual Risk

Finance Analytics has no write tools. The risk is data exfiltration through the agent transcript, not data modification. The rate limit on `rate_card_lookup` and the audit trail are the controls. If transcript storage becomes a concern, consider transcript retention policies or redaction of rate card data in stored transcripts.

---

## 3. Transport Planning — Cross-Site by Design

### 3.1 Permitted Tools

| Tool | System | Access Type |
|------|--------|------------|
| `wms_stock_lookup` | SYS-1 | READ |
| `tms_dock_schedule` | SYS-2 | READ |
| `tms_booking_lookup` | SYS-2 | READ |
| `tms_booking_create` | SYS-2 | WRITE (approval-gated) |
| `tms_booking_cancel` | SYS-2 | WRITE (approval-gated) |
| `ticket_search` | SYS-3 | READ |
| `ticket_create` | SYS-3 | WRITE |

### 3.2 Reachable Data

Transport Planning can:

- Read stock levels at all 11 sites.
- Read dock schedules and bookings at all sites.
- Create and cancel carrier bookings at any site (with human approval).
- Search and create exception tickets (without customer-scope restriction).

### 3.3 Composition Attack Scenarios

**Scenario 1: Stock arbitrage via stock lookups + booking creation**

| Step | Tool | Intent |
|------|------|--------|
| 1 | `wms_stock_lookup` at SITE-01 through SITE-11 | Build inventory picture |
| 2 | `tms_booking_create` at the cheapest available site | Optimise transport cost |

**Risk:** This is not an attack — it is Transport Planning's core function. They manage cross-site logistics and need to see all stock positions to make routing decisions.

**Gateway defense:** No composition block needed. `tms_booking_create` requires human approval, which provides a checkpoint for unusual routing decisions.

**Scenario 2: Ticket data mining**

| Step | Tool | Intent |
|------|------|--------|
| 1 | `ticket_search` with various queries | Search for operational exceptions across all sites |

**Risk:** Transport Planning can see tickets for all sites and all customers (they have no customer scope restriction). If tickets contain commercially sensitive information (e.g., a customer complaint about pricing), Transport Planning would see it.

**Gateway defense:** Transport Planning does not have `contract_lookup` or `rate_card_lookup` access, so they cannot correlate ticket data with contract or rate information. Ticket bodies are sanitised for injection patterns before reaching the agent. The residual risk is that ticket text may contain information that Transport Planning should not see (customer complaints about competitors, internal operational failures at specific sites). This is a data classification issue in the ticketing system, not a gateway composition issue.

### 3.4 Residual Risk

Transport Planning's combination of broad read access + booking write access is by design. The human approval gate on booking operations is the primary control. If Transport Planning's booking patterns become a concern (e.g., consistently booking at one carrier), the audit trail supports pattern analysis.

---

## 4. Warehouse Ops — Naturally Isolated

### 4.1 Permitted Tools

| Tool | System | Access Type |
|------|--------|------------|
| `wms_stock_lookup` | SYS-1 | READ |
| `ticket_search` | SYS-3 | READ |
| `ticket_create` | SYS-3 | WRITE |
| `ticket_comment` | SYS-3 | WRITE |

### 4.2 Reachable Data

A Warehouse Ops caller at SITE-01 can:

- Read stock levels at SITE-01 only (site parameter is enforced).
- Search tickets scoped to SITE-01 (site parameter is enforced where applicable).
- Create tickets at SITE-01 only.
- Add comments to tickets (ticket_id is not site-scoped — see residual risk).

### 4.3 Composition Attack Scenarios

**Scenario 1: Cross-site data via ticket_search**

| Step | Tool | Intent |
|------|------|--------|
| 1 | `ticket_search` with query "SITE-02 damaged goods" | Search for tickets at another site |

**Risk:** If the search query mentions another site's code, the ticketing system might return tickets from that site.

**Gateway defense:** The gateway's `enforce_scope` function pins the `site` parameter for Warehouse Ops callers. The search is sent to the upstream system with `site=SITE-01` regardless of what the agent requested. However, the free-text query itself is not site-filtered — the query "SITE-02 damaged goods" would be sent as the query text with `site=SITE-01` as a filter parameter. The upstream system's response depends on how it handles the combination of query text and site filter.

**Scenario 2: Cross-site comment via ticket_comment**

| Step | Tool | Intent |
|------|------|--------|
| 1 | `ticket_comment` on a ticket_id belonging to SITE-02 | Add a comment to another site's ticket |

**Risk:** `ticket_comment` takes a `ticket_id`, not a `site`. If the agent knows or guesses a ticket_id from another site, it can add a comment to that ticket.

**Gateway defense:** The current implementation does not validate that a ticket_id belongs to the caller's site before allowing a comment. This is a known gap. The mitigation is that ticket_ids are opaque identifiers that the agent would not know unless they appeared in a previous search result, and search results are site-scoped.

**Recommendation:** Add server-side validation that the ticket's site matches the caller's site before allowing `ticket_comment`. This requires the gateway to look up the ticket's site, which adds a round-trip to the ticketing system. This is acceptable latency for a write operation and should be implemented.

### 4.4 Residual Risk

The `ticket_comment` cross-site gap is the primary residual risk for Warehouse Ops. It is mitigated by:

1. Ticket_ids are not predictable or enumerable.
2. The agent only sees ticket_ids from site-scoped search results.
3. All comments are logged in the audit trail with the full caller identity.

The recommendation to add site validation on `ticket_comment` should be prioritised.

---

## Summary Matrix

| Team | Can Reach | Cannot Reach | Key Control |
|------|-----------|-------------|-------------|
| Customer Service | Own-customer tickets, own-customer contracts, all-site stock | Other customers' tickets, any rate cards, contract search | ACL + row scope + composition filter |
| Finance Analytics | All stock, all bookings, all contracts, all rate cards | No write operations | ACL (read-only) + rate limit on rate_card_lookup |
| Transport Planning | All stock, all bookings, all tickets, booking create/cancel | Contracts, rate cards, ticket close | ACL + approval gate on booking writes |
| Warehouse Ops | Own-site stock, own-site tickets, ticket comment* | Other sites' stock, any contracts, bookings | Row scope enforcement |

\* `ticket_comment` has a known cross-site gap documented in section 4.3. Recommendation: add site validation.
