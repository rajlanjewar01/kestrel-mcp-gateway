# Reflection

## What Was Built and Why

I built a governed MCP gateway for Kestrel Logistics, a fictional 3PL company with 11 warehouse sites. The gateway sits between four AI agent teams and four backend systems (WMS, TMS, Ticketing, Contracts), providing a single enforcement point for authorisation, rate limiting, audit logging, content sanitisation, and emergency kill switch.

The business problem was straightforward: four teams needed programmatic access to four systems, and each team's access had been reviewed independently. Nobody had asked what a team could do by *combining* their individually-approved access. The gateway exists to answer that question architecturally, not procedurally.

## What Worked Well

**The three-layer authorisation model turned out to be the right abstraction.** Tool ACL, row-level scope, and composition guard each catch a different class of problem. The ACL catches broad access violations (Customer Service calling `rate_card_lookup`). Row scope catches data boundary violations (SITE-01 caller querying SITE-02). Composition guards catch the cross-system assembly patterns that neither of the first two layers can see. I initially considered a two-layer model (ACL + scope), but the composition analysis showed that two individually-permitted calls can produce a result that neither call would produce alone. That required a third layer.

**The decision to not expose four operations was more valuable than any feature I built.** `ticket_delete`, `contract_search`, `wms_stock_adjust`, and `wms_bin_move` are all real API endpoints that exist upstream. The easy path was to expose them all and gate them with authorisation. The better path was to recognise that some operations should not be reachable through an AI agent at all, regardless of authorisation. `contract_search` was the clearest case: there is no way to make free-text search across all customer contracts safe for a customer-scoped team, because the safety violation is in the search results, not the query.

**Content sanitisation as a first-class middleware concern, not an afterthought.** Building `sanitize_search_query` with an allowlist rather than a blocklist was the right call. The ticketing system's search endpoint accepts Lucene syntax, has no input validation, no rate limit, and no audit trail. Trying to block specific dangerous operators (a blocklist approach) would have been a losing game against a creative model or a prompt injection attack. The allowlist approach (`[a-zA-Z0-9\s\-.,']` only) is more restrictive but eliminates the entire attack surface.

## What Failed or Was Harder Than Expected

**The composition guard's ticket filtering is simpler than I wanted.** The current implementation filters `ticket_search` results for Customer Service by checking `customer_id` on each returned ticket. This works when tickets have a `customer_id` field. It does not work when tickets are "internal" (no `customer_id`) — those pass through unfiltered. This is intentional (Customer Service needs to see internal tickets about their customers' shipments), but it creates a data classification dependency on the ticketing system. If the ticketing system misclassifies a customer-specific ticket as "internal" (by omitting the `customer_id`), the composition guard will not catch it.

**The `ticket_comment` cross-site gap is a real vulnerability I did not catch until the composition analysis.** `ticket_comment` takes a `ticket_id`, not a `site`. A Warehouse Ops caller at SITE-01 can comment on a ticket from SITE-02 if they know the ticket_id. The mitigation (ticket_ids from search results are site-scoped, so the agent should not know other sites' ticket_ids) is real but not airtight. I documented the gap and recommended adding site validation, but I did not implement the fix because it requires a round-trip to the ticketing system to look up the ticket's site before allowing the comment.

**Rate limit arithmetic for SYS-3 was surprisingly contentious.** The ticketing system has no upstream rate limit. I had to invent a defensive limit (100 rpm per team, 300 rpm total) based on my estimate of what the ticketing system could handle under agent-driven load. This number has no empirical basis — it is a judgment call. Too low and agents cannot work efficiently during incident spikes. Too high and the ticketing system might degrade under sustained agent load. The right answer is load testing the ticketing system, which was out of scope.

## How Failures Were Fixed

The `ticket_comment` cross-site gap was documented in the composition analysis as a known issue with a recommendation. I chose to document it transparently rather than paper over it because the ADR process is about honest architectural judgment, not about presenting a perfect system. The fix is straightforward (add a ticket lookup before allowing comments), and I included the recommendation in the composition analysis so it would be tracked.

The composition guard's dependency on ticket `customer_id` was addressed by allowing internal tickets (those without `customer_id`) to pass through, and by documenting the assumption that the ticketing system correctly classifies tickets. If this assumption proves wrong in production, the audit trail will show filtered vs. unfiltered results, making the classification gap detectable.

## What I Would Do Differently

**I would start with the composition analysis, not the tool interface.** I designed the tool interface first (which 11 tools to expose, with what parameters), then did the composition analysis to verify it was safe. This meant I discovered the `contract_search` problem late — I had initially planned to expose it with customer scoping, then realised during the composition analysis that free-text search cannot be reliably scoped. Starting with the composition analysis ("what can each team reach by combining calls?") would have surfaced these issues earlier and might have led to a different tool interface from the start.

**I would implement the `ticket_comment` site validation.** I documented it as a recommendation but did not build it. In a production system, a known vulnerability with a known fix should be fixed, not documented. The round-trip to the ticketing system is acceptable latency for a write operation.

**I would add integration tests for the sanitiser against real Lucene injection payloads.** The unit tests verify that the allowlist strips non-permitted characters, but I did not test against a corpus of real-world Lucene injection attempts. The allowlist approach should be resistant by design, but testing against real payloads would increase confidence.

## Business Impact

The gateway consolidates what would have been four separate integration projects into one governed system. The practical business impacts:

- **Credential management drops from 4 credential stores to 1.** Each upstream system has its own authentication scheme (API key, OAuth, bearer token, mTLS). Without the gateway, each team's agent infrastructure would need to manage these credentials independently. With the gateway, credentials exist in one place and are rotated in one operation.
- **Audit is answerable.** When the Commercial Director asks "did any agent access CUST-B's rate card?", the answer is a single query against the audit log. Without the gateway, the answer requires searching four separate systems' logs and correlating timestamps.
- **The kill switch provides a response mechanism.** If an agent begins behaving erratically (hallucinating bookings, mass-commenting on tickets), an operator can disable the specific tool or team in under a second by editing a JSON file. Without the gateway, the response would require disabling the agent's access in each upstream system independently.
- **The composition defense protects the business from a class of risk that was not visible until the analysis was done.** The fact that Customer Service could theoretically assemble cross-customer data from SYS-3 and SYS-4 was not apparent from the per-system access reviews. The gateway makes this impossible at the architecture level, not the policy level.
