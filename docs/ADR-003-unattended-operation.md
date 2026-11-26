# ADR-003: Unattended Operation

| Field       | Value                                      |
|-------------|--------------------------------------------|
| Status      | Accepted                                   |
| Date        | 2026-11-26                                 |
| Decision-makers | Priya Raghunathan (Platform Lead), Security Engineering |
| Related     | ADR-001 (Gateway Architecture), ADR-002 (Authorisation Model) |

---

## 1. Context

Two teams have requested "end-to-end without a person in the loop" operation for their AI agents:

- **Transport Planning** wants agents to autonomously create and cancel carrier bookings based on dock availability and load schedules.
- **Customer Service** wants agents to autonomously search tickets, add comments, and close resolved tickets without waiting for human review of each action.

Nobody has formally denied these requests. The current state is that the requests were made, acknowledged by Integration Engineering, and have not received a go/no-go decision. This ADR provides that decision.

### 1.1 What "Unattended" Means Here

Unattended operation means the agent executes a multi-step workflow — including write operations — without a human reviewing or approving each individual step. The agent receives a goal ("book a carrier for load LD-4821 at SITE-03"), plans the steps, and executes them autonomously.

### 1.2 The Operations Inventory

The gateway exposes three categories of write operations, each with different risk profiles:

| Category | Operations | Risk |
|----------|-----------|------|
| **Financially committing** | `tms_booking_create`, `tms_booking_cancel` | GBP 180-450 penalty per late cancellation. Real money leaves Kestrel's account. |
| **Customer-visible** | `ticket_comment` | Comments on customer-facing tickets are visible to the customer. An incorrect or inappropriate comment damages the customer relationship. |
| **State-changing with audit trail** | `ticket_close` | Closing a ticket creates a resolution record. Reopening is possible but audited. Premature closure means a customer issue is marked resolved when it is not. |
| **Additive (lower risk)** | `ticket_create` | Creates a new ticket. No data is lost or committed. The worst outcome is an unnecessary ticket, which can be closed. |

### 1.3 The Composition Surface

Unattended operation expands the composition attack surface. When a human is in the loop, they can spot when an agent is assembling data in unexpected ways (e.g., reading contracts for one customer and then searching tickets for a different customer). Without the human check, the composition guard is the only defense.

The composition guard has been tested against known attack scenarios (see [composition-analysis.md](composition-analysis.md)), but the attack surface is not fully characterised. We know what we have tested; we do not know what we have not thought of.

---

## 2. Decision

**DENY unattended write operations.** All write tools (`tms_booking_create`, `tms_booking_cancel`, `ticket_create`, `ticket_comment`, `ticket_close`) require a human in the loop.

**ALLOW unattended read operations within rate limits.** Read-only tools (`wms_stock_lookup`, `tms_dock_schedule`, `tms_booking_lookup`, `ticket_search`, `contract_lookup`, `rate_card_lookup`) may execute without per-call human approval, subject to the existing authorisation model, rate limits, and composition guards.

### 2.1 How This Is Enforced

The approval gate (`ApprovalGate`) is the enforcement mechanism for the three highest-risk write operations:

- `tms_booking_create` — returns `APPROVAL_REQUIRED` with an `approval_id`
- `tms_booking_cancel` — returns `APPROVAL_REQUIRED` with an `approval_id`
- `ticket_close` — returns `APPROVAL_REQUIRED` with an `approval_id`

For `ticket_create` and `ticket_comment`, the enforcement is at the operational level: teams are instructed that these tools must be used with human-in-the-loop agent configurations. The gateway does not currently gate these operations because they are additive (ticket_create) or append-only (ticket_comment), and gating them would make the agent workflow unusable for basic exception management.

This is a risk acceptance: `ticket_comment` in particular is customer-visible and could cause harm if the agent produces an inappropriate comment. The mitigation is that Customer Service agents are expected to operate in a human-supervised mode where the human reviews agent outputs before they are sent.

---

## 3. Rationale

### 3.1 Why Not Now

| Factor | Assessment |
|--------|-----------|
| **Financial risk** | `tms_booking_create` commits real money. A model hallucinating a carrier name or dock window could create a binding booking that costs GBP 180-450 to cancel. At scale (Transport Planning manages bookings across 11 sites), the aggregate financial exposure is significant. |
| **Customer relationship risk** | `ticket_comment` on customer-facing tickets is visible to the customer. A model generating an incorrect status update, an inappropriate tone, or a factually wrong statement damages the customer relationship in a way that is difficult to reverse. |
| **Composition uncertainty** | The composition guard addresses known attack scenarios. Unattended operation means the guard is the *only* defense. We have not yet accumulated enough production data to be confident the guard covers all practical attack vectors. |
| **Audit maturity** | The audit system is new. We have not yet validated that the logs are being reviewed, that alerts are configured for anomalous patterns, or that the operational team can respond to a composition guard failure in real time. |
| **Irreversibility** | `ticket_close` creates a resolution record. While tickets can be reopened, the resolution record persists and is visible to customers. An agent prematurely closing tickets at scale could create a cascade of "why was my ticket closed?" complaints. |

### 3.2 Why Read-Only Is Different

Read-only operations cannot commit money, change customer-visible state, or create irrecoverable data changes. The worst outcome of an unattended read is:

- **Data leakage** — mitigated by the ACL, row-level scope, and composition guard.
- **Rate limit exhaustion** — mitigated by per-team rate limits.
- **Cost** — read operations do not incur financial commitments.

The existing authorization model, rate limiting, and composition guards are sufficient controls for read-only unattended operation.

---

## 4. Path to Relaxation

Unattended write access is not permanently denied. It is denied *until the evidence justifies relaxation*. The conditions for reconsideration:

### 4.1 Prerequisites (All Required)

1. **6 months of clean audit logs.** The gateway must have been in production for at least 6 months with no authorization bypass, no composition guard failure, and no data leakage incident. "Clean" means zero security-relevant incidents, not zero errors.

2. **Formal Security Engineering sign-off.** Security Engineering must review the composition analysis, the audit logs, and the operational response procedures, and provide written sign-off that the controls are sufficient for unattended write operations on a per-tool basis.

3. **Per-tool opt-in.** Relaxation is per-tool, not per-team or gateway-wide. `tms_booking_create` might be approved for unattended operation before `ticket_comment` (or vice versa), depending on the risk profile and the evidence.

### 4.2 Relaxation Process

For each tool being considered for unattended operation:

1. The requesting team submits a business justification with expected call volumes and error tolerance.
2. Security Engineering reviews the audit data for that tool: approval rejection rate, composition guard trigger rate, error rate.
3. If the approval gate shows zero rejections over 6 months for that tool (meaning every request was eventually approved by a human), the evidence supports that human approval is not adding value for that tool.
4. A time-limited pilot (30 days) with enhanced monitoring and a lower rate limit.
5. Full rollout if the pilot produces no incidents.

---

## 5. Consequences

### Positive

- Financial risk from autonomous booking creation is eliminated.
- Customer relationship risk from autonomous comments is mitigated (human reviews before sending).
- The composition guard has time to prove itself in production before becoming the sole defense.
- Security Engineering can point to a documented, evidence-based decision rather than an implicit acceptance of risk.

### Negative

- **Teams must keep a human in the loop for writes.** This adds friction to every write workflow. For Transport Planning, it means a human must approve each booking, which may slow down the booking process during peak periods.
- **Agents cannot complete multi-step write workflows autonomously.** A workflow like "find available dock slot, create booking, update ticket" requires human approval at the booking creation step, breaking the autonomous flow.
- **Teams may perceive this as a lack of trust.** The decision should be communicated as risk management, not distrust. The path to relaxation is real and evidence-based.

---

## 6. Revisit If...

- **Approval gate shows zero rejections over 6 months for a specific tool.** If every human-approved request for `tms_booking_create` was approved (no rejections), the approval step is adding latency without adding value. This is the strongest signal that unattended operation is safe for that tool.
- **A competing business need makes the friction unacceptable.** If peak-period booking volumes make human-in-the-loop operation a bottleneck (e.g., Transport Planning cannot process enough bookings in the available dock windows), the business case may override the risk assessment. This should be a formal risk acceptance, not a workaround.
- **The composition guard demonstrates coverage beyond initial scenarios.** If audit log analysis reveals that the composition guard is catching novel attack patterns (not just the ones in the initial analysis), confidence in the guard as a standalone defense increases.
