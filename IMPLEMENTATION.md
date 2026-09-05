DealFlow360 — Implementation Plan

A self-governing B2B sales operations platform. Built in 24 hours, phase-gated, with a verification checkpoint at the end of every phase.

How to use this document

This file is the single source of truth for the build. Work strictly phase by phase.

Rules for the coding agent:

Do not start a phase until the previous phase's verification gate has been signed off by the human.
At the end of each phase, print the Verification Gate checklist and stop. Do not continue.
Every phase must end with something visible in the browser. No phase is allowed to be backend-only.
Business rules live in the database as rows, never as constants in code. If you are about to write a hardcoded percentage, stop and make it a config row.
Never fake a computation for the demo. Every number shown in the UI must be produced by the rule engine.
Keep a running PROGRESS.md — after each phase append what was built, what was skipped, and any known breakage.

Rules for the human (you):

At each gate, actually perform the listed checks in the browser. Do not accept "it's implemented" — click it. If a gate fails, fix before moving on. A broken foundation at Phase 3 costs four hours at Phase 8.

The pitch (keep this in view the whole build)

Most sales tools are a quote-to-invoice form. DealFlow360 is a deal engine that governs itself: it enforces pricing discipline per product category, routes approvals without anyone asking, reacts to live inventory, reconciles subscriptions against one-time hardware on one order, and gives the customer a live negotiable document instead of a PDF.

The moment we win on: a judge changes a discount ceiling in the admin screen, we recompute, and an already-approved quotation immediately flips back into the approval queue with a fresh audit entry. That single interaction proves the logic is real and configurable. Every phase below is in service of that moment being possible.

Screen inventory (from the official mockup)

The organizers published an 18-screen mockup. Screen names, navigation, and layout below are authoritative — build these, not something adjacent. Judges will have seen this mockup.

#	Screen	Phase
1	Login / Signup	0
2	Sales Dashboard / Home	2
3	Quotations List (Kanban + table toggle)	2
4	Quotation Detail	2
5	Approvals List	3
6	Approval Detail	3
7	Fulfillment and Stock (List)	5
8	Fulfillment Detail	5
9	Subscriptions List	6
10	Billing Detail	6
11	Customer Portal Negotiation	7
12	Invoices List	6
13	Invoice Detail	6
14	Deal Health and Anomaly Dashboard	8
15	Admin / Reporting Dashboard (marked optional)	8
16	Product catalog	1
17	Product Details page	1
18	Discount tiers and approval chains	1

Top navigation, exactly as drawn, on every internal screen:

Dashboard · Quotations · Approvals · Fulfillment · Subscriptions · Invoices · Deal Health · Reports · Products

Notes on what this implies:

There is no separate settings or back-office area. Products (16, 17) and discount configuration (18) are top-level destinations. Drop the left-rail settings layout.
Approvals, Subscriptions, and Invoices are each top-level, not sub-tabs of a billing screen.
There is no separate Pipeline nav item. The Quotations List is the Kanban, with a "Switch to Table View" button.
Warehouse stock is administered on screen 7, not on a config screen.
Subscription plans are created from screen 9 via a "+ New Plan (Admin)" button.
The customer portal has its own navigation: My Quotation · Messages · Profile.

Every list screen in the mockup follows the same pattern: status count chips at the top, a table below, a yellow explanatory note strip under the table, and action buttons at the bottom left. Build that as one reusable layout in Phase 0 and every list screen becomes fast.

Stack

Locked in unless the team is faster elsewhere. Do not learn anything new during the hackathon.

Layer	Choice	Note
Backend	FastAPI (Python 3.11)	Pydantic gives free request validation
ORM	SQLAlchemy 2.x + Alembic	Alembic optional; create_all is fine for 24h
DB	PostgreSQL 15	JSONB for audit payloads and rule metadata
Auth	JWT, three token audiences: internal / portal / admin	Portal tokens are scoped to one quotation
Frontend	React 18 + Vite + TypeScript	
Styling	Tailwind CSS	Design tokens in Phase 1
State/data	TanStack Query	Cache invalidation gives us "live" recompute for free
Realtime	Server-Sent Events on /api/events/stream	Simpler than WebSockets, sufficient for our needs
Charts	Recharts	Dashboard only
PDF	WeasyPrint or ReportLab	Quotation export, Phase 8

Repo layout

/backend
  /app
    /models        SQLAlchemy models
    /schemas       Pydantic
    /api           routers, grouped by module
    /engine        pricing.py, risk.py, routing.py, fulfillment.py, billing.py, anomaly.py
    /core          config, security, deps, events
    seed.py
/frontend
  /src
    /api           typed client
    /components    shared primitives
    /features      quotations, approvals, fulfillment, billing, portal, dashboard, admin
    /styles
docker-compose.yml
PROGRESS.md
IMPLEMENTATION.md

The /engine directory is the heart of the project. Every function in it is pure: it takes data in and returns a result plus an explanation. No database calls, no side effects. This is what makes the logic testable, demonstrable, and honest.

Design direction (settle this once, in Phase 1)

The product is a governance tool for people who move money. It should feel like an operations console, not a marketing site. Restraint everywhere, with one loud element: the risk meter.

Palette: a cool neutral base (slate/graphite), one signal color for risk escalation, one for approved/healthy states, one muted accent for interactive affordances. No gradient washes, no decorative color.
Type: one sans family across the whole app (Inter or IBM Plex Sans), plus tabular figures for all money and percentage columns. Numbers must align vertically in tables — this alone makes the app read as financial software.
Density: tight. Sales operators scan; they don't read. Small row heights, generous whitespace only between functional groups.
Structure: borders and dividers encode grouping. No identical rounded cards for everything, no drop shadow on every surface.
Motion: only in response to an action. When the risk score changes, animate that number and nothing else. The margin indicator ticking in response to an upsell being added is the one motion moment that should be noticeable.
Copy: buttons say what happens. "Route for approval," not "Submit." "Send back for revision," not "Reject." The action keeps its name through the toast and the audit log.

Empty states are instructions, not decoration: "No quotations yet. Create one to see approval routing in action."

PHASE 0 — Foundation

Target: 0:00 → 1:30

Goal

A running full-stack skeleton with auth and roles. Nothing business-specific yet.

Backend
docker-compose.yml: Postgres + backend + frontend.
SQLAlchemy base, session dependency, settings via env.
User model: id, email, password_hash, name, role, created_at.
Roles enum: ADMIN, SALES_REP, SALES_MANAGER, FINANCE. (Customer portal users are not User rows — they authenticate by scoped token in Phase 7.)
POST /api/auth/signup, POST /api/auth/login → JWT with sub, role, aud: "internal".
Dependency require_role(*roles) for route protection.
GET /api/me.
Audit log model now, not later: AuditEvent(id, entity_type, entity_id, actor_user_id, actor_label, action, payload JSONB, created_at). Append-only. A helper log_event(...) that every mutation will call.
GET /api/health.
Frontend
Vite + React + TS + Tailwind, design tokens from the section above committed as CSS variables.
Login and signup screens.
App shell with the mockup's exact top navigation: Dashboard, Quotations, Approvals, Fulfillment, Subscriptions, Invoices, Deal Health, Reports, Products. Active tab highlighted. User badge with role, sign out.
Protected routing — unauthenticated users bounce to login, and nav items hide by role. After login, internal users land on the Sales Dashboard; customers land on their quotation portal.
Shared primitives: Button, Input, Select, Table, Badge, Modal, Toast, EmptyState, Money, Percent.
ListScreen layout component — page title, one-line subtitle, status count chips, table, yellow note strip, footer actions. Every list screen in the mockup uses this shape; build it once here.
Stepper component — horizontal dots with labels. Used by the approval chain (screen 6) and the invoice delivery stages (screen 13).
Verification Gate 0
 docker compose up brings the whole stack up from clean.
 I can sign up, log out, and log back in.
 Four seeded accounts exist, one per internal role, and each sees a different nav set.
 Hitting a protected API route without a token returns 401.
 audit_events table exists and the login action wrote a row to it.
 The shell looks like a deliberate product, not a Tailwind default page.
PHASE 1 — Master data & configuration

Target: 1:30 → 4:30

Goal

Every business rule that later phases will read is now an editable row in the database. This phase is what makes the "judge edits a threshold live" moment possible, so it is not filler.

Backend

Models:

Category(id, name, default_discount_ceiling_pct) — Hardware 15, Services 10, Subscriptions 8.
Product(id, name, sku, category_id, unit, list_price, unit_cost, tax_pct, description, is_promoted, is_active) unit_cost is mandatory — margin math depends on it.
ProductVariant(id, product_id, attribute_name, value, price_delta)
CustomerTier(id, name, rank, base_discount_ceiling_pct) — Bronze 5, Silver 10, Gold 15.
Customer(id, name, email, tier_id, currency)
PriceList(id, name, tier_id, currency) / PriceListItem(id, price_list_id, product_id, price)
CategoryTierCeiling(id, tier_id, category_id, ceiling_pct) — the override matrix. Resolution order: this table → category default → tier base.
ApprovalRule(id, name, level, min_blended, min_peak, min_erosion_amount, required_roles JSONB, sequence, is_active) Seed two: Level 1 → SALES_MANAGER at blended ≥ 2 or peak ≥ 5; Level 2 → FINANCE at blended ≥ 5 or peak ≥ 8 or erosion ≥ 50000.
Warehouse(id, name, code, shipping_cost_weight, is_active)
StockLevel(id, warehouse_id, product_id, on_hand, reserved, reorder_point)
SubscriptionPlan(id, name, interval, interval_count, proration_policy, cancellation_policy) interval in {MONTHLY, QUARTERLY, YEARLY}; proration_policy in {DAILY_PRORATE, FULL_PERIOD, NONE}.
ProductPairing(id, product_id, suggested_product_id, co_purchase_score, min_margin_pct)
SystemSetting(key, value JSONB) — stalled-deal day threshold, anomaly z-score threshold, currency symbol.

Full CRUD routers for all of the above, admin-only for writes. Every write calls log_event.

seed.py — idempotent, and rich enough to demo from:

3 tiers, 3 categories, ~12 products with realistic costs, 4 customers across tiers.
2 warehouses with deliberately partial stock, so a split is forced on at least one demo product.
3 subscription plans, ~8 product pairings, 2 approval rules.
4 internal users.
15–20 historical quotations across various stages and dates, with varied discount levels per rep. These matter — the anomaly detector and the stalled-deal panel in Phase 9 have nothing to say without history. Backdate some to 10+ days ago.
Frontend

Screen 16 — Product catalog (nav: Products). Header buttons "+ New Product" and "Manage Price fields". Three KPI cards: Total Products (active / archived), Pricelists (tiers, currencies), SKUs across all products. Table columns: Product name, Category, Variants, Price, Unit, Tax, Status. Note strip: "Click a product row to open general info, variants and recurring price lists."

Screen 17 — Product Details. Three fieldset groups exactly as drawn:

General info — left column: Product name, Category, Price, Unit, Description. Right column: Tax %, Subscription (Yes/No), and when Yes, a Recurring selector (Monthly / Yearly / Weekly), plus Quantity on hand.
Product Variants — table of Attribute, Values, Extra price (e.g. Color / Blue, Black / 0; RAM / 4GB, 8GB / +$30).
Pricelists — table of Tier, Currency, Price Rule. Rules are expressions like "Price minus 10 percent base", not just fixed per-item prices.
Note strip: "Product details should be filled. Recurring order with this product will be invoiced at the beginning of the period."

Screen 18 — Discount tiers and approval chains. One page, one "Save configuration" button. Four blocks:

Tier Discount Ceilings — Tier / Max Discount (Bronze 5%, Silver 10%, Gold 15%)
Category Discount Ceilings — Category / Max Discount (Hardware 15%, Services 10%)
Approval mapping — Discount range / Required approval: within tier or category limit → no approval; over limit, blended risk medium → Sales Manager; over limit, blended risk high → Sales Manager then Finance
Note strip: "When a quote mixes categories with different ceilings, the system must compute a blended risk score and route to the highest required level. All approvals, rejections and edits must be logged with user, timestamp and reason."

Keep our tier × category override matrix as an additional block on screen 18 — it is a superset of what the mockup draws and it is what makes the live-edit demo land.

Warehouse stock editing lives on screen 7 (Phase 5). Subscription plan creation lives on screen 9 (Phase 6). Product pairings and system settings have no drawn screen — put them behind a small "Manage Price fields"-style secondary panel on the Products screen and do not spend design time there.

Verification Gate 1
 I can create a product with a cost and see it appear in the list.
 Product Details shows the Subscription Yes/No toggle, and choosing Yes reveals the Recurring cycle selector.
 Screen 18 renders all four blocks on one page and "Save configuration" persists every one of them.
 I can change Gold/Services from 10% to 6% in the ceiling matrix and it persists after refresh.
 The approval mapping shows the three bands (none / Sales Manager / Manager then Finance) and I can edit the thresholds behind them.
 Warehouse stock is editable and at least one seeded product has stock split across two warehouses with neither holding enough alone.
 python seed.py twice in a row does not duplicate data.
 Seeded historical quotations exist, spread across reps and dates, with at least three older than the stalled threshold.
 Every config edit I just made appears in audit_events.
PHASE 2 — Quotation builder & live pricing

Target: 4:30 → 7:30

Goal

A rep can build a quotation and watch margin move in real time. The pricing engine exists as one pure module used by both the preview and the save path.

Backend
Quotation(id, number, customer_id, owner_user_id, status, currency, subtotal, discount_total, tax_total, grand_total, margin_amount, margin_pct, blended_score, peak_overage, erosion_amount, created_at, updated_at, last_activity_at)
QuotationLine(id, quotation_id, product_id, variant_id, line_type, qty, unit_price, unit_cost, discount_pct, subscription_plan_id, start_date, computed JSONB) line_type in {ONE_TIME, RECURRING}.
Status enum: DRAFT, PENDING_APPROVAL, APPROVED, SENT, UNDER_NEGOTIATION, CONFIRMED, FULFILLING, INVOICED, REJECTED, CANCELLED.

engine/pricing.py — pure function:

price_quotation(lines, customer_tier, ceilings, price_list) -> QuotationPricing

Returns per line: effective unit price, gross, discount amount, net, cost, margin amount, margin %, applicable ceiling, overage points. Returns per order: subtotal, discount total, tax, grand total, blended margin %, and a human-readable explanations[] list. Nothing else in the codebase may compute money.

POST /api/quotations/preview — takes a draft payload, returns full pricing without persisting. This is what the builder calls on every keystroke (debounced).
Standard CRUD: create, list with filters, get, update lines, delete.
last_activity_at bumps on every mutation (Phase 9 depends on it).
Frontend

Screen 2 — Sales Dashboard / Home. The landing page after internal login. Subtitle: "Central hub, links out to every module below." Three KPI cards: Pending Approvals (n quotations waiting), Open Quotations (n active deals), At-Risk Deals (n flagged by Deal Health). Two buttons: "+ New Quotation" and "View Approvals". Below, a Recent Activity feed of the latest audit events in plain sentences — "Acme Corp quotation approved by Finance", "Beta Industries requested a discount change", "East Depot stock updated for Order #2291". The feed is a direct read of audit_events, which is why we built that table in Phase 0.

Screen 3 — Quotations List. Kanban by default, one card per quotation, columns: Draft, Pending Approval, Approved, Negotiation, Confirmed. Cards show customer and amount ("Acme Corp — $12,450"). Footer: "+ New Quotation" and "Switch to Table View" which toggles to a filterable table (number, customer, tier, owner, amount, margin, status, age). Subtitle: "Every quotation in the system, one row per quotation, click a row to open it."

Screen 4 — Quotation Detail. A single scrolling page, not a three-pane builder:

Customer and Price List selectors at the top.
Order lines table with columns Product, Qty, Price, Discount, Limit, Status. The Status cell reads OK or OVER (+8pt) and is the per-line enforcement signal.
Note strip, verbatim in spirit: "Discount is checked against each line's own limit, as soon as it is entered, not only at submit time."
Upsell and Cross-Sell Suggestions as a row of cards below the lines table (Phase 4 fills these): "+ Wireless Mouse — Margin +$18", "+ Docking Station — Promo: 12% off", "+ Care Plan 2yr — Margin +$46".
Footer buttons: "Save Draft" and "Submit for Approval".

Add our live totals and margin summary as a compact strip above the footer. The mockup doesn't draw one, but per-line status alone can't show the order-level picture, and the blended risk meter lands here in Phase 3.

Every edit debounces into /preview. The Limit and Status cells update as the discount is typed.

Verification Gate 2
 I can create a quotation, add lines from three categories, and change quantities.
 The totals and margin update within ~300ms of typing, without a page reload.
 The Limit column shows the correct resolved ceiling per line, and Status flips to OVER (+Npt) the moment the discount is typed — not on submit.
 I change Gold/Hardware ceiling on screen 18, return to the quotation, and the Limit and Status cells change accordingly.
 The Sales Dashboard's three KPI cards show real counts, and Recent Activity is reading actual audit events.
 Quotations List opens as a Kanban with seeded cards in the right columns, and "Switch to Table View" works both ways.
 Deleting a line recomputes correctly and margin returns to its prior value.
PHASE 3 — Blended risk score & approval routing

Target: 7:30 → 11:00

This is the centerpiece. Assign your strongest backend person. Do not let this phase get squeezed.

Goal

The system decides, by itself, who must approve a quotation — and can explain exactly why.

The formula (implement precisely)

For each line i:

ceiling_i  = resolve_ceiling(tier, category)      # matrix → category default → tier base
overage_i  = max(0, discount_pct_i - ceiling_i)   # in percentage points
weight_i   = line_net_value_i / order_net_total

Order-level metrics:

blended  = Σ (overage_i × weight_i)               # value-weighted average points over
peak     = max(overage_i)                          # worst single line
erosion  = Σ (overage_i / 100 × line_gross_i)      # currency actually given away past policy

Routing: evaluate ApprovalRule rows in sequence order. A rule triggers if any of its non-null thresholds is met. The required chain is every triggered rule, in sequence. No rules triggered → auto-approve, straight to fulfillment.

Why blended, and say this in the pitch: one line 8 points over is obvious and any tool catches it. Four lines each 2–3 points over is the same margin loss and looks innocent line by line. Peak catches the first, blended catches the second. Erosion catches a small percentage on a very large line.

Backend
engine/risk.py → compute_risk(priced_quotation, ceilings) -> RiskResult with blended, peak, erosion, and per_line_breakdown[] where each entry carries the ceiling, the given discount, the overage, the weight, and its contribution to the blended figure. The breakdown is not optional — it is what we show on screen to prove the number is real.
engine/routing.py → determine_chain(risk_result, rules) -> [ApprovalStep], plus explain() returning sentences like "Finance required: peak overage 8.0 points meets the 8.0 threshold on rule 'High risk'."
ApprovalRequest(id, quotation_id, level, required_role, status, sequence, acted_by_user_id, acted_at, comment, snapshot JSONB) The snapshot freezes the risk numbers at request time — needed to prove that recomputation genuinely changed things.
POST /api/quotations/{id}/submit — prices, computes risk, determines chain, creates approval requests, sets status. The rep is never asked whether to request approval. It happens or it doesn't.
POST /api/approvals/{id}/act — body {action: approve|reject|return_for_revision, comment}. Role-checked. Approving step n activates step n+1; the final approval moves the quotation to APPROVED. Reject → REJECTED. Return → back to DRAFT with the comment attached.
POST /api/quotations/{id}/recompute — reprices against current config. If the required chain now differs from the approved chain, invalidate the approval and re-enter routing. This endpoint is the live-config demo.
Every action writes an audit event with before/after risk numbers.
Emit SSE on every approval state change.
Risk banding

The mockup labels risk as LOW / MEDIUM / HIGH, not as raw numbers. Compute the numbers, then band them for display: no rule triggered → LOW, Level 1 triggered → MEDIUM, Level 2 triggered → HIGH. The band is what appears in badges and list columns; the numbers appear in the breakdown. Both must be visible somewhere — the band for scanning, the numbers for proof.

Frontend

Screen 5 — Approvals List. Subtitle: "Every quotation that needed, needs, or is going through discount approval." Count chips across the top in three colors: Pending / Returned / Approved. Table columns: Quotation, Customer, Blended Risk (LOW/MEDIUM/HIGH), Stage, Assigned To. Note strip: "Click any row to open the full approval detail, risk breakdown and audit trail." Footer: a "Filter: Pending Only" toggle.

Screen 6 — Approval Detail. Top row: a Blended Risk: HIGH badge in the risk color plus a Customer Tier: Gold badge. Then, in order down the page:

"Why This Quote Was Flagged" — table with columns Line, Discount Given, Limit Allowed, Over By. Rows read like "Laptop (Hardware) / 12% / 15% / 0 pt — OK" and "Setup Service (Services) / 18% / 10% / 8 pt OVER". Add our weight and contribution columns to the right; this is the same breakdown, extended.
Note strip: "Worst single line (8pt over) plus overall pattern across the order sets the blended score. One bad line is enough to require approval."
Horizontal stepper: Submitted → Sales Manager → Finance → Confirmed, with completed, active and pending states.
Audit table: User, Action, Date, Note. Rows like "J. Rao / Submitted / Aug 20 / Initial 12% discount", "M. Shah / Returned / Aug 21 / Requested justification", "J. Rao / Resubmitted / Aug 22 / Added margin note".
Footer buttons in the mockup's colors: Approve (green), Return for Revision (amber), Reject (red). Use these exact labels everywhere, including toasts.

In the Quotation Detail (screen 4): a compact risk meter showing the band plus blended, peak and erosion, updating live as the rep discounts. The "Submit for Approval" button label stays as drawn, but add a line of helper text underneath stating where it will route — "Will route to Sales Manager and Finance."

Toast plus live list refresh when an approval lands, driven by SSE.

Verification Gate 3

This gate is the project. Be strict.

 A quote with all lines under ceiling submits with no approval and lands in APPROVED.
 One line 8 points over its ceiling routes to Manager and Finance.
 Four lines each ~2–3 points over — none individually dramatic — still trigger Manager via the blended figure. Confirm the arithmetic by hand against the breakdown table.
 The breakdown table's contributions sum to the displayed blended score.
 The Approvals List shows the LOW/MEDIUM/HIGH band, the current stage, and who it is assigned to.
 Manager approving moves the stepper to Finance, not to Confirmed. Finance approving completes it.
 "Return for Revision" sends the quote back to draft with the comment visible to the rep and a row in the audit table.
 A rep account cannot approve their own quotation (403 from the API, not just a hidden button).
 The money shot: approve a quotation. Change Gold/Services ceiling from 10% to 6% in the backend. Call recompute. The quotation returns to pending approval, and the audit trail shows the old and new scores side by side.
 Every one of the above wrote an audit event.
PHASE 4 — Upsell / cross-sell panel

Target: 11:00 → 12:30

Short phase, high demo value. It's the visible "the system is helping me" beat.

Goal

Ranked suggestions with honest margin math, added in one click.

Backend
engine/upsell.py → suggest(quotation, pairings, products, min_margin) -> [Suggestion]. Rank by co_purchase_score, boost promoted products, and filter out anything whose margin falls below the pairing's min_margin_pct — we do not suggest deals that hurt us. Each suggestion carries the projected margin delta and new order total, computed by calling price_quotation on the hypothetical line set. No estimates.
GET /api/quotations/{id}/suggestions.
Record dismissals so a dismissed item doesn't return in the session.
Frontend
The "Upsell and Cross-Sell Suggestions" card row sits below the order lines table on screen 4, as drawn. Three cards side by side. Each card: "+ Product name" as the heading, then either a margin figure ("Margin +$18") or a promo tag ("Promo: 12% off"). Clicking the card adds the line; a small dismiss control sits in the corner.
On add: the line appears in the table, totals and margin animate, the risk meter re-evaluates. The whole chain reacting to one click is the point.
Verification Gate 4
 Adding a laptop surfaces relevant accessories, not random products.
 Promoted items rank above equal-scored non-promoted ones.
 A pairing whose margin is below its floor never appears — verify by lowering a product's price in admin until it drops off the list.
 The stated margin delta exactly matches the actual margin change after adding.
 Adding a suggestion can push the quote over a threshold and the risk meter reflects it immediately.
 Dismiss removes it for the session.
PHASE 5 — Multi-warehouse fulfillment split

Target: 12:30 → 15:00

Goal

Real allocation against real stock, with backorders and manual override.

Backend
Fulfillment(id, quotation_id, status, total_shipments, estimated_cost, is_manual_override, created_at)
FulfillmentAllocation(id, fulfillment_id, quotation_line_id, warehouse_id, qty, is_backorder)
engine/fulfillment.py → plan_split(lines, stock_levels, warehouses) -> FulfillmentPlan. Greedy, and state the objective plainly in the pitch: minimize shipment count first, then weighted shipping cost. Try to satisfy the whole order from the fewest warehouses; prefer warehouses that can cover the most lines completely; break ties on shipping_cost_weight. Anything unsatisfiable becomes a backorder allocation. Return explanations[] per line — "12 of 20 from Main Warehouse (all available), 8 backordered."
POST /api/quotations/{id}/fulfillment/plan — plan only, no writes.
POST /api/quotations/{id}/fulfillment/accept — persists, reserves stock (StockLevel.reserved += qty).
POST /api/fulfillment/{id}/override — accepts a manual allocation set, validates it against available stock and rejects impossible allocations with a clear error.
POST /api/fulfillment/{id}/consolidate — when stock has arrived, re-plan open backorders and offer consolidation.
Fulfillment planning triggers automatically on quotation approval.
Frontend

Screen 7 — Fulfillment and Stock (List). Subtitle: "Live stock per warehouse, plus every order that still needs fulfilling." Two tables stacked:

Stock — Warehouse, Product, In Stock, Reserved, Available. This doubles as the warehouse stock admin surface, so make the on-hand figure editable here for admins. There is no separate warehouse config screen.
Orders Awaiting Fulfillment — Order, Customer, Status (Split Pending / Backorder), Warehouse ("Main + East Depot").
Note strip: "Click an order row to open its warehouse split detail."

Screen 8 — Fulfillment Detail, titled "Fulfillment Detail: Q-1042 (Acme Corp)". Table columns: Warehouse, Qty Fulfilled, Est. Shipments, Cost — rows like "Main Warehouse / 18 units / 1 / $12" and "East Depot / 6 units / 1 / $29". Below it, the yellow prompt: "'Consolidate Remaining Backorder' prompt appears automatically once East Depot restocks." Footer buttons: Accept Suggested Split (primary) and Manual Override (secondary). Override mode makes qty-per-warehouse editable with live validation against Available.

Keep our per-line explanation text as an expandable row under each warehouse — it is what proves the split is computed rather than hardcoded.

Verification Gate 5
 An order fully covered by one warehouse produces a single-warehouse, single-shipment plan.
 An order exceeding any single warehouse's stock splits across two, and the quantities sum exactly to the ordered quantity.
 An order exceeding total stock creates a backorder row with the correct shortfall.
 Accepting the split increments reserved on the right stock rows — verify in the admin stock screen.
 Manual override with an impossible quantity is refused with a readable message.
 Raising stock in admin makes the consolidate prompt appear, and consolidating clears the backorder.
 Each allocation row carries a plain-English explanation.
PHASE 6 — Hybrid billing: one-time + recurring

Target: 15:00 → 17:30

Goal

One order carrying hardware and subscriptions, billed correctly and separately, with real proration.

Backend
Order(id, quotation_id, number, status, confirmed_at)
Invoice(id, order_id, type, amount, tax, status, issue_date, due_date, period_start, period_end) — type in {ONE_TIME, RECURRING}, status in {DRAFT, ISSUED, PAID, PARTIAL, CREDITED}.
BillingSchedule(id, order_id, quotation_line_id, plan_id, next_billing_date, interval, amount, status) — subscription status in {ACTIVE, PAUSED, CANCELLED}; the mockup's Subscriptions List counts all three.
Payment(id, invoice_id, amount, method, reference, received_at)
CreditNote(id, invoice_id, amount, reason, created_at) Rule correction from the mockup, screen 13: "Partial invoicing stays reconciled with partial delivery, nothing is billed before it ships." One-time lines are not invoiced on order confirmation — they are invoiced when their allocation ships. A split order that ships 18 units from Main and backorders 6 produces an invoice for 18 units now and a second invoice when the backorder ships. Recurring lines are invoiced at the start of their period regardless, per the note on screen 17. This couples Phase 6 to Phase 5, so implement mark_shipped(allocation) as the event that triggers one-time invoicing.
engine/billing.py:
build_schedule(order) — recurring lines produce a schedule of the next 12 periods with dates and amounts, first charge at period start. One-time lines produce pending invoice intents that materialize on shipment.
invoice_shipment(allocation) — creates or extends the one-time invoice for the units that actually shipped.
prorate(line, change_date, old_qty, new_qty, plan) — daily proration by default: delta_amount × (days_remaining / days_in_period). Increase → prorated charge; decrease → prorated credit note. Honors the plan's proration_policy.
cancel(subscription, date, policy) → refund or credit per policy.
POST /api/quotations/{id}/confirm → creates order, invoices, and schedules.
POST /api/invoices/{id}/payments → records payment, updates status to PAID or PARTIAL.
POST /api/subscriptions/{id}/change → applies proration, emits the credit note or charge.
Frontend

Four screens, two nav entries (Subscriptions, Invoices).

Screen 9 — Subscriptions List. Subtitle: "Every recurring plan across every customer, regardless of which order it came from." This is a global view, not per-order. Count chips: Active / Paused / Cancelled. Table: Customer, Plan, Cycle, Next Bill, Status. Footer: "+ New Plan (Admin)" — this is where subscription plans get created, admin-only.

Screen 10 — Billing Detail, titled "Billing Detail: Acme Corp — Care Plan 2yr". Two labelled tables:

One-Time Lines (from originating order) — Product, Qty, Amount.
Recurring Lines — Plan, Cycle, Next Bill Date, Amount.
Footer: Modify Subscription and Cancel Subscription (red outline).
Modify opens our proration preview before confirming: "Increasing 5 → 8 seats with 14 of 30 days remaining: charge $X now, then $Y per month."

Screen 12 — Invoices List. Subtitle: "Every invoice generated from one-time and recurring lines." Count chips: Unpaid / Paid. Table: Invoice #, Customer, Amount, Status, Due Date — recurring invoices appear here alongside one-time ones. Note strip: "Click an invoice row to open its full payment and delivery reconciliation detail."

Screen 13 — Invoice Detail. Top: a horizontal stepper — Order Confirmed → Shipped → Invoiced → Paid — showing where this invoice sits. Table of invoice rows including the recurring one, marked as such ("INV-1043 (Recurring)"). Footer: Record Payment (green) and Download Summary. Note strip: "Partial invoicing stays reconciled with partial delivery, nothing is billed before it ships."

Verification Gate 6
 An order with hardware and a subscription produces exactly two billing groups, not one merged total.
 Nothing is invoiced before it ships. Confirming a split order creates no one-time invoice until I mark an allocation shipped; shipping 18 of 24 units invoices exactly 18, and shipping the backorder later produces the second invoice.
 The Subscriptions List shows plans from multiple customers and multiple orders, with Active, Paused and Cancelled counts.
 The Invoice Detail stepper reflects the real stage of that order, not a fixed picture.
 The recurring schedule shows correct dates for monthly, quarterly, and yearly plans.
 Increasing quantity mid-cycle produces a prorated charge I can verify by hand against days remaining.
 Decreasing quantity mid-cycle produces a credit note, not a negative invoice.
 Recording a partial payment sets PARTIAL; paying the remainder sets PAID.
 Cancelling a subscription applies the configured policy and the refund or credit appears.
 Every billing action is in the audit trail.
PHASE 7 — Customer portal & negotiation

Target: 17:30 → 20:00

Goal

A genuinely separate, restricted customer experience. The spec calls this out explicitly, and a re-labelled internal screen loses points. Build the isolation properly and say so in the pitch.

Backend
PortalToken(id, quotation_id, customer_id, token_hash, expires_at, used_at) — signed, scoped to one quotation, aud: "portal".
Routes live under /api/portal/* with their own dependency. A portal token authenticates to exactly one quotation ID; any other ID returns 404, not 403 — do not leak existence.
Portal responses are a reduced DTO: no cost, no margin, no risk score, no internal comments, no rep notes. Build a separate Pydantic schema; do not filter an internal schema, or something will leak.
NegotiationRequest(id, quotation_id, line_id nullable, type, message, proposed_discount_pct, status, created_at, responded_at, responder_user_id, response_message) — type in {COMMENT, CHANGE_REQUEST, COUNTER_DISCOUNT}.
POST /api/quotations/{id}/send — generates the token and the shareable link, sets status SENT.
GET /api/portal/quotation — customer view.
POST /api/portal/negotiate — sets status UNDER_NEGOTIATION, notifies the rep by SSE.
POST /api/portal/confirm — the automatic re-entry rule: re-price and re-run risk against the final agreed terms. If a chain is now required, status goes back to PENDING_APPROVAL and the customer sees "Sent for internal review." If not, it moves to CONFIRMED and straight to fulfillment.
POST /api/negotiations/{id}/respond — the rep accepts, counters, or declines; accepting applies the discount and re-runs risk.
Frontend
Separate route tree at /portal/:token with its own navigation — My Quotation · Messages · Profile — and none of the internal nav. Same brand bar, entirely different destinations.
Titled "Customer Portal Negotiation Screen", subtitle "Customer reviews and negotiates the quote directly, no email needed."
A prominent status chip: Sent / Under Negotiation / Confirmed.
Table with columns Line and Customer Comment, one row per quotation line, comment editable inline — the mockup's examples are "Can this be 15% off instead of 10%?" and "Can we push this to next month?". Never margin, cost, or risk.
Two fields below: Counter Discount % and Requested Delivery Date (we did not have the date field; add it, and surface it to the rep alongside the counter).
Footer: Submit Request (secondary) and Confirm Quotation (green primary).
Note strip: "If final terms exceed thresholds, the quote automatically re-enters approval (Screen 6)."
After confirm: a status page reflecting the real outcome — confirmed, or under internal review.
Internal side: negotiation inbox on the quotation, threaded, with accept/counter/decline. Accepting a counter visibly moves the risk meter.
Verification Gate 7
 The portal link opens in a private browser window with no login and shows the right quotation.
 The portal API response, inspected in the network tab, contains no cost, margin, or risk fields. Check the raw JSON, not the UI.
 Changing the quotation ID in the portal URL returns 404.
 A portal token cannot call any /api/quotations/* internal route.
 A customer counter-offer appears in the rep's inbox live, without a refresh.
 Key check: customer counters to a discount above threshold, rep accepts, customer confirms → the quote automatically re-enters approval with the correct chain. Nobody clicked "request approval."
 A customer confirming within-threshold terms goes straight to fulfillment.
 An expired token is refused with a clear message.
PHASE 8 — Deal health, anomalies & reporting

Target: 20:00 → 22:00

Goal

The manager's view. Everything here is a read over data we already have — no new sources of truth.

Backend
engine/anomaly.py:
Stalled deals: quotations not in a terminal state with last_activity_at older than the configured threshold. Ranked by value at risk.
Discount anomaly: for each rep, rolling mean and standard deviation of order-level discount % across their history. Flag any quote where z = (discount - mean) / stddev exceeds the configured threshold. Falls back to a fixed-delta rule when a rep has too few historical quotes. State the method in the pitch — "z-score against the rep's own baseline," not "unusual discount."
Delivery slippage: fulfillments with open backorders past their promised date.
GET /api/dashboard/health — the three alert lists with drill-through IDs.
GET /api/dashboard/metrics — pipeline value by stage, approval cycle time, average discount by rep and by category, win rate, margin trend.
GET /api/reports with filters: period, rep/team, approval status, product/category.
POST /api/quotations/{id}/nudge — logs a nudge and posts an escalation entry to the audit trail.
PDF export of a quotation, and CSV export of a report.
Frontend

Screen 14 — Deal Health and Anomaly Dashboard. Subtitle: "Real-time flags for stalled deals and unusual discount patterns." Three cards across the top: Stalled Deals ("5 quotes idle 7+ days"), Discount Anomalies ("2 above rep average"), Delivery Slippage ("3 promise dates at risk"). Below, one table: Deal, Issue, Flagged, Action — rows like "Zenith Co / Idle 9 days / Aug 24 / Nudge sent" and "Delta LLC / Discount 22% vs avg 8% / Aug 25 / Escalated to Manager". Footer buttons: Escalate (red) and Nudge Rep (blue). Note the Issue column phrasing — state the anomaly as "22% vs avg 8%", which reads better than a z-score to a judge while still being computed from one.

Add our two charts (discount distribution by rep with outliers marked, margin trend) below the table. The mockup doesn't draw them, but the problem statement asks for real-time dashboards and they cost little once the data is there.

Screen 15 — Admin / Reporting Dashboard, explicitly labelled (Optional) in the mockup. Subtitle: "Sales trends, approval bottlenecks and platform usage." Four filter fields in a row: Period, Sales Team, Approval Status, Product. Three KPI cards: Quotes Created ("148 this month"), Avg Approval Time ("6.4 hours"), Top Upsold Product ("Care Plan 2yr"). Footer: Export PDF and Export XLS. Because the mockup marks it optional, this is the first thing to cut if Phase 8 runs long.

Verification Gate 8
 Stalled deals panel is populated from seeded backdated quotations, and lowering the day threshold in settings adds more.
 The anomaly panel flags a rep's outlier quote and states the z-score and their baseline.
 Creating a fresh high-discount quote as that rep makes it appear in the anomaly list.
 Clicking any alert opens the correct quotation.
 Nudge Rep and Escalate each write an audit entry, update the Action column, and show a toast.
 All four report filters change the results, including in combination.
 Avg Approval Time is computed from real approval timestamps, not a constant.
 Quotation PDF exports and looks presentable.
 Every dashboard number is live — no static arrays anywhere in the frontend.
PHASE 9 — Harden, seed, rehearse

Target: 22:00 → 24:00

Freeze features at hour 22. No exceptions. From here, only fixing, seeding, and rehearsing.

Tasks
Run the full happy path end to end three times from a clean database. Fix anything that breaks.
Error states everywhere: failed requests show a readable message, not a blank screen or a raw stack trace.
Every empty state has instructive copy.
Loading states on all async actions; disable buttons while in flight to prevent double submission.
Responsive check — the demo may be on an unfamiliar screen.
Keyboard focus visible; reduced motion respected.
Reset script: python seed.py --reset restores demo-ready state in one command. Have this bound to a single terminal command during the demo.
README.md: run instructions, demo credentials for all four roles, and the portal link.
Architecture diagram (one page): the ER model, plus the /engine modules shown as the shared core that the API, the portal, and the dashboard all read through. Emphasize that rules are data.
"What we'd build next": multi-currency and multi-company, ML-ranked upsell trained on actual co-purchase history, contract lifecycle and renewals, ERP/accounting connectors, approval SLA escalation, mobile approvals.
The demo script (rehearse with a timer — five minutes)

0:00 — Frame it, 20 seconds. "Most sales tools are a quote-to-invoice form. Ours governs itself. Watch what the rep never has to do."

0:20 — Flow one: governance. Build a quote for a Gold customer. Add a laptop at 12% — fine. Add a setup service at 18% against a 10% ceiling. The risk meter moves as you type. Open the breakdown: this line, this ceiling, this overage, this weight. Submit — the button already reads "Route to Manager and Finance." The rep never requested approval.

1:20 — The blended point. Second quote: four lines, each 2–3 points over. "Nothing here looks alarming. But weighted across the order this rep has given away real margin, and the system catches it." Show the blended figure and the routing.

1:50 — The judge moment. As admin, change Gold/Services from 10% to 6%. Recompute. The approved quote flips back into the queue, and the audit trail shows old score versus new. "Every rule in this system is a database row, not a constant."

2:30 — Upsell. Back in the builder, accept a suggestion. Margin, totals, and risk all move together on one click.

2:50 — Approve and fulfill. Manager approves, Finance approves. The split screen shows 12 units from Main, 8 from East Depot, one backorder, with the reasoning per line.

3:20 — Hybrid billing. One order, two billing groups. Show the 12-period schedule. Change subscription quantity mid-cycle and show the prorated credit note computed to the day.

3:50 — Flow two: portal. Open the customer link in a private window. Point at the network tab: "No cost, no margin, no risk score — this is a separate token-scoped surface, not our screen with a label changed." Counter for a bigger discount. Rep accepts. Customer confirms. The quote re-enters approval automatically.

4:30 — Dashboard. Stalled deals, the flagged anomaly with its z-score and the rep's baseline, and one nudge.

4:50 — Close. "Rules as data, one pricing engine behind every screen, and an append-only event log that powers the audit trail, the dashboard, and the anomaly detector from a single source of truth."

Verification Gate 9
 The full demo runs clean, twice, in under five minutes, from a reset database.
 Reset is one command and takes under ten seconds.
 No console errors during the demo path.
 All four role logins work and are written down.
 Architecture diagram is done and exported.
 Every presenter has run their own section at least once.
 There is a fallback plan if the network dies — everything runs locally.
Cut list, in the order things get dropped

If you are behind, cut from the top. Do not cut from the bottom.

Multi-currency and multi-company (explicitly a bonus in the spec)
Screen 15, Admin Reporting — the mockup itself marks it optional, so cutting it costs nothing with judges
Product variants beyond a single attribute
XLS export — PDF and CSV are enough
Bulk email delivery of quotations — show the copyable link instead
Kanban drag-and-drop — a status dropdown works
Charts beyond two
Consolidate-backorder prompt
Subscription cancellation policy (keep proration on quantity change)

Never cut, at any cost: the risk engine and its per-line breakdown, automatic routing, the append-only audit trail, the separately-tokenized portal with its own DTO, rules stored as data, and automatic re-entry into approval after negotiation. These six are the entire differentiation.

Standing engineering rules
One pricing function. If a number appears in two places, it came from the same call.
Every engine function returns its explanation alongside its result. If we can't explain a number on screen, a judge won't believe it.
Every state change writes an audit event, no exceptions.
Config is data. Zero business thresholds in Python or TypeScript.
Money as Decimal in Python and integer minor units over the wire. Never float.
The portal has its own schema, its own dependency, and its own route tree.
Timestamps in UTC, formatted at the edge.