# Tools Not Exposed

This document lists upstream system operations that exist in the backend APIs but are deliberately **not exposed** through the Kestrel MCP Gateway. Each exclusion is an architectural decision, not an oversight.

---

## 1. `ticket_delete` (SYS-3 Ticketing)

**What it does:** Permanently deletes a ticket from the ticketing system. This is a hard delete — the ticket, its comments, its audit trail, and its attachments are removed. There is no soft-delete, no recycle bin, and no undo.

**Why it is not exposed:**

- **Destructive with no recovery.** A deleted ticket cannot be restored. If an agent deletes a ticket in error (hallucinated ticket_id, misunderstood instruction, prompt injection from ticket content), the data loss is permanent.
- **No agent workflow justifies it.** None of the four teams have a legitimate workflow that requires ticket deletion. Tickets are closed (via `ticket_close`), not deleted. The delete endpoint exists for administrative database cleanup, not for operational use.
- **Injection risk.** The ticketing system's search endpoint (used by `ticket_search`) accepts free-text queries. If a prompt-injection attack in a ticket body caused the agent to call `ticket_delete` on the ticket it just found, the attack evidence would be destroyed along with the ticket.
- **No audit trail on the upstream side.** SYS-3's delete endpoint does not log the deletion. The only record would be the gateway's audit log, which would show the call was made but not what was deleted (the ticket content is gone).

**What teams should do instead:** Close tickets with a resolution summary via `ticket_close`. Closed tickets remain in the system for audit and reporting.

---

## 2. `contract_search` (SYS-4 Contracts)

**What it does:** Free-text search across all contracts in the contracts system. Returns matching contracts including their terms, SLA details, and — critically — rate schedules.

**Why it is not exposed:**

- **Unscoped cross-customer disclosure.** A search query like "rate" would return rate schedules for every customer. There is no way to scope a free-text search to a single customer's contracts at the upstream API level. The API was designed for internal contract management, not for customer-scoped agent access.
- **Commercially sensitive data.** Rate cards are negotiated per-customer. Customer A's rate is confidential from Customer B, and from any team that deals directly with customers. The Commercial Director's requirement is that cross-customer rate disclosure must be **architecturally impossible**, not just policy-forbidden.
- **`contract_lookup` is the safe alternative.** `contract_lookup` takes a `customer_id` parameter, which the gateway validates against the caller's authorized customer list. This provides the same functionality (look up a specific customer's contract) without the cross-customer disclosure risk.
- **Finance Analytics can use `rate_card_lookup`.** For teams that legitimately need to see rate cards (Finance Analytics only), the gateway exposes `rate_card_lookup`, which is scoped to a single customer_id per call and rate-limited to 10 rpm.

**What teams should do instead:** Use `contract_lookup` with a specific `customer_id`. Finance Analytics can use `rate_card_lookup` for pricing data.

---

## 3. `wms_stock_adjust` (SYS-1 WMS)

**What it does:** Adjusts the recorded stock quantity for a SKU at a specific bin location. This is a ledger-affecting operation: the adjustment creates an inventory transaction that feeds into financial reporting, order allocation, and replenishment planning.

**Why it is not exposed:**

- **Ledger-affecting with no undo.** A stock adjustment modifies the inventory ledger. Reversing it requires a counter-adjustment, which creates a confusing audit trail and may trigger downstream processes (recount requests, allocation changes, financial reconciliation).
- **No team has requested SYS-1 write access.** When Integration Engineering reviewed each team's access requirements, no team identified a need to adjust stock through the gateway. Warehouse Ops manages stock through the WMS's native interface, where stock adjustments are paired with physical counts and supervisor approval.
- **Physical-world consequences.** An incorrect stock adjustment can cause: (a) order allocation to stock that does not physically exist, (b) replenishment orders for stock that is already on hand, (c) financial discrepancies between the inventory ledger and physical counts. These consequences are difficult to detect and expensive to correct.
- **Agent hallucination risk.** A stock adjustment requires exact SKU, site, bin location, and quantity. An agent hallucinating any of these values would create a ledger entry for a fictional adjustment. The WMS has no way to distinguish a legitimate adjustment from a fabricated one.

**What teams should do instead:** Use `wms_stock_lookup` for read access. Stock adjustments should be performed through the WMS native interface with physical verification.

---

## 4. `wms_bin_move` (SYS-1 WMS)

**What it does:** Initiates a bin-to-bin move for a SKU within a warehouse site. This creates a physical task: a warehouse picker receives an instruction to move stock from one bin location to another.

**Why it is not exposed:**

- **Generates physical picker tasks.** A bin move is not just a database update. It creates a task in the warehouse management system's task queue, which is dispatched to a physical picker with a handheld device. An incorrect bin move means a person walks to the wrong location, picks the wrong stock, and moves it to the wrong place.
- **No team has requested SYS-1 write access.** Same as `wms_stock_adjust`: no team identified a need for warehouse write operations through the gateway.
- **Cascade risk.** Bin moves can trigger downstream processes: pick-face replenishment, put-away reassignment, and cycle count scheduling. An incorrect bin move can cascade into multiple incorrect tasks.
- **Physical safety.** In a 3PL warehouse, bin moves can involve heavy goods, high-rack locations, and forklift operations. Creating phantom tasks in the picker queue wastes physical labour and can create safety risks if pickers are directed to locations that are not set up for the stock being moved.

**What teams should do instead:** Bin moves should be managed through the WMS native interface by warehouse supervisors who can verify the physical feasibility of the move.

---

## Decision Review

These exclusions should be reviewed if:

1. A team articulates a business-justified need for any of these operations through the gateway.
2. The upstream systems add controls that mitigate the identified risks (e.g., SYS-4 adds customer-scoped search, SYS-3 adds soft-delete).
3. The gateway's approval gate and composition guard demonstrate sufficient maturity (per ADR-003's relaxation criteria) to safely gate these higher-risk operations.

Any addition of a currently-excluded tool requires a new ADR, a composition analysis update, and Security Engineering sign-off.
