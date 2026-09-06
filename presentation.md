# DealFlow360 — Presentation Source

Everything below is organized as slide-sized blocks (`## Slide N — Title`) so it can be
lifted directly into a PPT/Google Slides deck, one section per slide. Bullet depth roughly
maps to slide bullet levels.

---

## Slide 1 — Title

**DealFlow360**
A self-governing B2B sales operations platform

*Quote → Risk → Approval → Fulfillment → Billing → Customer Negotiation — one system, one source of truth.*

---

## Slide 2 — The Problem

- Most sales tools are a **quote-to-invoice form**: a rep types numbers, a PDF comes out.
- Nobody enforces discount discipline consistently across categories, tiers, and reps.
- Approval routing is manual — someone has to remember to ask, and remember who to ask.
- Warehouse allocation, billing, and customer negotiation live in separate disconnected tools (or spreadsheets).
- When a business rule changes (a discount ceiling, an approval threshold), nothing already in flight is re-checked.

---

## Slide 3 — The Pitch

**DealFlow360 governs itself.**

- Enforces pricing discipline per product category and customer tier — automatically.
- Routes approvals without anyone asking — the system decides who must sign off, and why.
- Reacts to live inventory across multiple warehouses.
- Reconciles one-time hardware and recurring subscriptions on a single order.
- Gives the customer a **live negotiable document**, not a static PDF.

**The moment that proves it's real, not a demo trick:**
An admin changes a discount ceiling on a config screen → the system recomputes → an
*already-approved* quotation automatically flips back into the approval queue, with an
audit entry showing the old score vs. the new one side by side. Nobody clicked "resubmit."

---

## Slide 4 — Tech Stack

| Layer | Choice |
|---|---|
| Backend | FastAPI (Python 3.11) |
| ORM / DB | SQLAlchemy 2.x + PostgreSQL 15 |
| Auth | JWT — three audiences: internal / portal / admin |
| Frontend | React 18 + Vite + TypeScript |
| Styling | Tailwind CSS (design tokens as CSS variables, light/dark theme) |
| State/data | TanStack Query — cache invalidation gives "live" recompute for free |
| Realtime | Server-Sent Events (`/api/events/stream`) |
| PDF | ReportLab |
| Testing | pytest (32 tests: unit + API + end-to-end) |
| Infra | Docker Compose (Postgres + backend containerized; frontend via Vite dev server) |

---

## Slide 5 — Architecture: Rules Are Data

**One idea drives every screen:** rules are data, and one set of pure functions computes
every number that appears anywhere in the product. Nothing re-derives a price, a risk
score, or an anomaly independently.

| Engine module | Computes |
|---|---|
| `pricing.py` | Line/order totals, margin, discount overage — **the only place money is computed** |
| `ceilings.py` | Which discount ceiling applies: override → category default → tier base |
| `risk.py` | Blended / peak / erosion risk score + per-line breakdown |
| `routing.py` | Which approval steps are required, from risk + rule rows in the DB |
| `fulfillment.py` | Warehouse allocation splits and backorders |
| `billing.py` | Invoice line items, subscription proration to the day |
| `upsell.py` | Cross-sell ranking by co-purchase score and margin impact |
| `anomaly.py` | Stalled deals, discount anomalies (z-score vs. rep baseline), delivery slippage |

Every engine function is **pure**: dataclasses in, dataclasses out, no DB access, no side
effects — the only way three different callers (API, portal, dashboard) are guaranteed to
agree on the same number, and why every number on screen can show its own explanation.

Config that would normally be a hardcoded constant is instead **a database row**: discount
ceilings, approval thresholds, anomaly thresholds, stalled-deal windows — all editable from
a Settings/Config screen, read at call time.

---

## Slide 6 — Architecture: Three Surfaces, One Core

```
┌─────────────────┐     ┌──────────────────┐     ┌────────────────────┐
│   Internal app   │     │  Customer portal  │     │   Deal Health /     │
│ (reps, manager,  │     │ (own schema, own  │     │  Reports dashboard  │
│  finance, admin) │     │  token auth, own  │     │                     │
│                   │     │  route tree)      │     │                     │
└─────────┬─────────┘     └─────────┬─────────┘     └──────────┬──────────┘
          │                          │                          │
          └──────────────┬───────────┴──────────────┬───────────┘
                          ▼                          ▼
                 backend/app/engine/*       backend/app/models/audit.py
                 (pricing, risk, routing,    (append-only AuditEvent —
                  fulfillment, billing,       every state change writes
                  upsell, anomaly)            here; audit trail, dashboard,
                                               and anomaly detector all
                                               read from it)
                          │
                          ▼
                     PostgreSQL
```

- The customer portal never imports internal API code — separate Pydantic schemas, separate router. Structurally incapable of leaking cost/margin/risk data.
- The append-only `audit_events` table is the single source of truth for three separate features: the quotation audit trail, the Deal Health "last action" column, and the before/after comparison when a live config change flips an approved quote back into review.

---

## Slide 7 — Entity Model (high level)

- **Master data**: Category, Product/ProductVariant, CustomerTier, Customer, CategoryTierCeiling, ApprovalRule, Warehouse/StockLevel, SubscriptionPlan, ProductPairing, SystemSetting
- **Quoting**: Quotation, QuotationLine (status lifecycle: Draft → Pending Approval → Approved → Sent → Under Negotiation → Confirmed → Fulfilling → Invoiced / Rejected / Cancelled)
- **Approval**: ApprovalRequest (role-checked, sequence-enforced, self-approval blocked)
- **Fulfillment**: Fulfillment, FulfillmentAllocation (per-warehouse split, backorders)
- **Billing**: Order, Invoice, BillingSchedule, Payment, CreditNote
- **Portal**: PortalToken, NegotiationRequest
- **Notifications**: Notification (in-app, per-user)
- **Audit**: AuditEvent (append-only, actor + action + payload on every mutation)

---

## Slide 8 — Feature: The Pricing & Risk Engine (centerpiece)

For each order line:

```
ceiling_i  = resolve_ceiling(tier, category)        # override → category default → tier base
overage_i  = max(0, discount_pct_i − ceiling_i)      # in percentage points
weight_i   = line_net_value_i / order_net_total
```

Order-level:

```
blended  = Σ (overage_i × weight_i)      # value-weighted average points over
peak     = max(overage_i)                 # worst single line
erosion  = Σ (overage_i / 100 × gross_i)  # actual currency given away past policy
```

**Why three numbers, not one:**
- *Peak* catches one dramatic line (8 points over) — any tool catches this.
- *Blended* catches four lines each 2–3 points over — same total margin loss, looks innocent line-by-line, missed by peak alone.
- *Erosion* catches a small percentage discount on a very large line.

Every number ships with a **per-line breakdown** (ceiling, discount given, overage, weight, contribution) — proof, not a black box.

---

## Slide 9 — Feature: Automatic Approval Routing

- `ApprovalRule` rows define thresholds (min blended / min peak / min erosion, required role, sequence) — **data, not code**.
- A rule triggers if *any* of its non-null thresholds is met.
- The required chain is every triggered rule, in sequence order.
- No rule triggered → **auto-approved**, straight to fulfillment.
- Role-checked, sequence-enforced (can't approve step 2 before step 1), self-approval blocked, required comment on reject/return.
- Every action — submit, approve, reject, return — writes an audit event with before/after risk numbers.
- **Live recompute**: change a ceiling, call recompute, an already-approved quote can flip straight back into `PENDING_APPROVAL`.

---

## Slide 10 — Feature: Multi-Warehouse Fulfillment

- Auto-plans a warehouse split the moment a quotation reaches `APPROVED`.
- Objective: minimize shipment count first, then weighted shipping cost.
- Satisfies from the fewest warehouses possible; unsatisfiable quantity becomes a **backorder** allocation.
- Every allocation carries a plain-English explanation ("12 of 20 from Main Warehouse (all available), 8 backordered.") — not hardcoded text, computed.
- Manual override available (role-gated), validated live against actual available stock.
- **Consolidate**: re-plans an open backorder once stock arrives.
- Ship action is the trigger billing hangs off (see next slide).

---

## Slide 11 — Feature: Hybrid Billing (One-Time + Recurring)

- One order can carry hardware (one-time) and a subscription (recurring) — billed correctly and **separately**.
- **Nothing is invoiced before it ships.** Confirming an order creates zero one-time invoices; shipping 18 of 24 units invoices exactly 18 units' worth. Shipping the rest later produces a second invoice.
- Recurring lines are invoiced at the start of their period, independent of shipment.
- Real calendar-month proration (`add_period`/`subtract_period`) — Jan 31 + 1 month correctly lands on Feb 28/29, periods survive year boundaries.
- Mid-cycle quantity increase → prorated charge to the day; decrease → a **credit note**, never a negative invoice.
- Payments: partial → `PARTIAL`; full → `PAID`. Cancellation applies the plan's configured policy (credit / no-refund).

---

## Slide 12 — Feature: Customer Portal & Negotiation

**A genuinely separate, restricted surface — not the internal screen with a label changed.**

- Own route tree (`/portal/:token`), own navigation (My Quotation · Messages · Profile), own API client that never touches the internal JWT.
- Auth: an opaque random secret, hashed at rest — not a JWT. Structurally can't be accepted by any internal route.
- Any auth failure (missing / garbage / expired token) → **404**, uniformly — never leaks whether a quotation exists.
- Response schema is hand-written, separate from internal schemas: **zero** cost, margin, or risk fields anywhere in the payload.
- Customer can comment per line, propose a counter-discount, request a delivery date.
- Rep can Accept / Counter / Decline — accepting re-prices the order live and the internal risk band visibly moves immediately.
- **The automatic re-entry rule**: when the customer clicks Confirm, the system re-prices and re-runs risk against final terms.
  - Over threshold → automatically routed back into internal approval (Manager/Finance) — the customer sees "sent for internal review." Nobody clicked "submit for approval."
  - Within threshold → goes straight to `CONFIRMED` + fulfillment planning.

---

## Slide 13 — Feature: Upsell & Cross-Sell

- Ranked by real co-purchase score, filtered by a **margin floor** — never suggests a deal that hurts the business.
- Every suggestion's margin delta comes from a real second call to the same pricing engine — no estimates.
- Promoted products break ties at equal score.
- Adding a suggestion reacts through the whole chain live: totals, margin, and the risk meter all move on one click.
- Dismiss is per-session, doesn't resurface.

---

## Slide 14 — Feature: Deal Health & Anomaly Detection

- **Stalled deals**: non-terminal quotations idle past a configurable day threshold, ranked by value at risk.
- **Discount anomalies**: z-score of a rep's discount % against *their own* historical baseline — not one global number. Falls back to a fixed-delta-vs-org-average rule for reps with too little history.
- **Delivery slippage**: fulfillments with an open backorder past a derived promise date.
- Manager actions — **Nudge Rep** / **Escalate** — write to the audit trail (role-gated: only Manager/Finance/Admin, not the rep themselves).
- Reports screen: filterable by period/owner/status/product, CSV export, PDF quotation export.

---

## Slide 15 — Feature: In-App Notifications

- Centralized rule-based dispatcher (`core/notifications.py`) — one `RULES` table maps event type → (who gets notified, what the message says). Routers never contain recipient logic themselves.
- Wired into every meaningful workflow event: submitted for approval, routed to next approver, approved, rejected, returned for revision, recomputed/re-entered approval, customer negotiation submitted.
- Delivered live over the **existing SSE stream** — no new transport.
- Bell icon: unread badge, click-to-mark-read, mark-all-read, click-through to the linked quotation.
- Backed by 32 automated tests (recipient resolution, notification creation, read/unread, end-to-end router wiring).

---

## Slide 16 — Roles & Permissions

| Role | Can do |
|---|---|
| **Sales Rep** | Build/submit quotations, create customers (auto-owns them), negotiate, view everything |
| **Sales Manager** | Approve/reject/return quotations, reassign customer ownership, nudge/escalate deals, override fulfillment splits |
| **Finance** | Second-level approval on high-risk quotes, record payments, view reports |
| **Admin** | Full master-data control (products, categories, ceilings, approval rules), user management |
| **Shipment Manager** | Edit warehouse stock levels, manual fulfillment override — scoped exactly to warehouse operations |

- Account ownership on customers: a rep automatically owns any customer they create; only Manager/Admin can reassign. Another rep working the same customer gets a **non-blocking warning**, never a hard lock — surfaces the conflict, lets humans decide.

---

## Slide 17 — Security & Data Integrity Highlights

- JWT with three distinct audiences (internal / portal / admin) — a portal token is structurally invalid on internal routes.
- Append-only audit log — every mutation, no exceptions, actor + timestamp + before/after payload.
- Self-approval blocked at the API level, not just hidden in the UI.
- Money is `Decimal` throughout the backend — never floating point.
- Every role restriction enforced server-side first; the frontend only *reflects* it (hides controls that would 403) — never the other way around.

---

## Slide 18 — The 5-Minute Demo Script

1. **Governance** (0:20) — Build a Gold-tier quote, add a line over its category ceiling. Watch the risk meter move as you type. Submit — the button already says "Route to Manager and Finance." Nobody asked for approval.
2. **The blended catch** (1:20) — Four lines each 2–3 points over, nothing individually alarming — blended catches it, peak alone would have missed it.
3. **The judge moment** (1:50) — Lower a discount ceiling live as admin. Recompute. An approved quote flips back to Pending Approval, audit trail shows old score vs. new.
4. **Upsell** (2:30) — Accept a suggestion; margin, totals, and risk move together in one click.
5. **Fulfillment** (2:50) — Approve through Manager + Finance, watch the warehouse split compute (12 from Main, 8 from East, one backorder) with real per-line reasoning.
6. **Hybrid billing** (3:20) — One order, two billing groups. Change a subscription quantity mid-cycle, see the exact-to-the-day prorated credit note.
7. **The portal** (3:50) — Open the customer link in a private window. Inspect the network tab — no cost, margin, or risk anywhere. Counter for a bigger discount, rep accepts, customer confirms → automatic re-entry into approval.
8. **Dashboard** (4:30) — Stalled deals, a flagged anomaly with its z-score, one nudge.
9. **Close** (4:50) — "One pricing engine behind every screen, rules as data, and an append-only event log powering the audit trail, the dashboard, and the anomaly detector from a single source of truth."

---

## Slide 19 — Demo Credentials

| Role | Email | Password |
|---|---|---|
| Admin | `admin@dealflow360.com` | `password123` |
| Sales Rep | `rep@dealflow360.com` | `password123` |
| Sales Rep (high-discount outlier) | `rep3@dealflow360.com` | `password123` |
| Sales Manager | `manager@dealflow360.com` | `password123` |
| Finance | `finance@dealflow360.com` | `password123` |
| Shipment Manager | `shipping@dealflow360.com` | `password123` |

Reset to a clean demo state anytime: `docker compose exec backend python -m app.seed --reset` (~2 seconds).

---

## Slide 20 — What We'd Build Next

- Multi-currency and multi-company support
- ML-ranked upsell trained on real co-purchase history, not seeded scores
- Contract lifecycle and renewal management
- ERP / accounting system connectors
- Approval SLA escalation (auto-escalate a stuck approval after N hours)
- Mobile approvals
- Email notifications alongside the existing in-app system

---

## Slide 21 — Closing

**DealFlow360 isn't a quote-to-invoice form. It's a deal engine that governs itself.**

- One pricing function — every number on screen traces back to the same call.
- Rules are database rows — a judge can change policy live and watch the system react.
- An append-only audit log powers the audit trail, the dashboard, and the anomaly detector from one source of truth.
- A customer gets a live negotiable document, not a PDF — and the negotiation automatically re-enters governance when terms change.
