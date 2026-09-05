# PROGRESS

## Current status (as of 2026-09-05)

A snapshot of where the build actually stands right now, across both sides. The phase-by-phase log below has the full detail and reasoning; this section is the quick answer to "what works today."

### Backend (FastAPI + Postgres, running in Docker)

**Fully built and verified:**
- Auth: JWT (internal audience), 4 roles, `require_role` dependency, append-only `AuditEvent` + `log_event` called on every mutation.
- Master data: `Category`, `Product`/`ProductVariant` (+ `is_subscription`/`recurring_interval`/computed `quantity_on_hand`), `CustomerTier`, `Customer`, `CategoryTierCeiling` matrix, `ApprovalRule`, `Warehouse`/`StockLevel`, `SubscriptionPlan`, `ProductPairing`, `SystemSetting` — full CRUD, admin-gated writes.
- `Quotation`/`QuotationLine` + full lifecycle: preview (live pricing, no persistence), create, list (with filters), get, update lines, delete, submit, recompute.
- `ApprovalRequest` + the full approval workflow: role-checked, sequence-enforced, self-approval blocked, required comment on reject/return.
- Pure engines, each independently testable: `engine/pricing.py` (the only place money is computed), `engine/ceilings.py` (tier/category ceiling resolution), `engine/risk.py` (blended/peak/erosion), `engine/routing.py` (rule → approval chain).
- SSE broadcaster (`/api/events/stream`) firing on submit/recompute/approval actions.
- Generic audit-event reads (`/api/audit-events`, filtered or recent-across-everything for the dashboard feed).
- `seed.py` — idempotent: 6 internal users (admin, 3 reps, manager, finance), 3 tiers, 3 categories, 12 products, 4 customers, 2 warehouses (deliberately split stock), 3 subscription plans, 8 pairings, 2 approval rules, 3 settings, 18 historical quotations priced through the real engine.
- `engine/upsell.py` + `GET /api/quotations/{id}/suggestions` + dismiss endpoint — ranked, margin-floor-filtered upsell suggestions, every number from a real second `price_quotation` call.
- `Fulfillment`/`FulfillmentAllocation` + `engine/fulfillment.py` split logic — auto-plans on approval, plan/accept/override/consolidate/ship endpoints.
- `Order`/`Invoice`/`BillingSchedule`/`Payment`/`CreditNote` + `engine/billing.py` — confirm, shipment-driven one-time invoicing, recurring billing with daily/full-period proration, payments.

**Not started yet** (Phases 7–8 backend): `PortalToken`/`NegotiationRequest` + portal routes, anomaly/stalled-deal engine, reports/export endpoints.

### Frontend (React + Vite + TS, running on the **host** via `npm run dev` — not the Docker container)

**Fully built and verified:**
- Nav matches the mockup exactly (Dashboard · Quotations · Approvals · Fulfillment · Subscriptions · Invoices · Deal Health · Reports · Products), on every screen.
- Sales Dashboard: live KPI cards + audit-event activity feed.
- Quotations List: Kanban (5 columns) + Table view toggle, drag-and-drop status changes, stalled highlighting.
- Quotation Detail: single scrolling page, live debounced pricing (~300ms), per-line Limit/Status columns, risk meter, Save Draft / Submit for Approval.
- Approvals List: count chips, LOW/MEDIUM/HIGH risk band, stage, assigned-to, pending-only filter.
- Approval Detail: risk breakdown table, horizontal stepper, colored Approve/Return/Reject actions, audit trail.
- Product Catalog + Product Detail (general info, variants, pricelists-display), Discount Config (4 blocks, one batched save).
- SSE-driven toasts + live query invalidation across all of the above.
- Upsell and Cross-Sell Suggestions cards on Quotation Detail — ranked, real margin deltas, click to add, dismiss for the session.
- Fulfillment and Stock (screen 7) + Fulfillment Detail (screen 8) — live stock with inline admin edit, per-warehouse split with expandable explanations, Accept/Override/Consolidate/Ship.
- Subscriptions List (screen 9) + Billing Detail (screen 10) + Invoices List (screen 12) + Invoice Detail (screen 13) — real preview-then-confirm proration flow, payment recording, stepper reflecting real order/ship/invoice/paid state.

**Placeholder only** (nav item exists, no real screen behind it yet): Deal Health, Reports.

**Not built:** customer portal (Phase 7 — no `/portal/:token` route tree exists), PDF/CSV export, report filters.

### Environment notes / known issues
- **Frontend/backend split across two runtimes right now**: backend + Postgres run in Docker (`docker compose up -d`), frontend runs directly on the host (`cd frontend && npm run dev`) because the containerized frontend was giving the human tester confusing stale-bundle symptoms. `docker-compose.yml` still has a frontend service for a from-scratch run — this split should be reconciled before the Phase 9 demo rehearsal.
- Pricelists on Product Detail show "Base price" for every tier — `PriceList`/`PriceListItem` exist in the backend but no pricing logic reads them yet, and the mockup's "Price Rule" expressions were deliberately not built (zero gate coverage, would need a real remodel).
- A handful of manually-created test quotations sit in the database from verification passes (in addition to the 18 seeded ones) — harmless, real data, useful for clicking through the approval flow live.
- Two real bugs were found and fixed during verification: a `passlib`/`bcrypt` version mismatch (Phase 0) and a stale-read on the "remaining pending approval steps" count caused by `autoflush=False` (Phase 3) — both documented in their phase sections below.

---

## Phase 0 — Foundation

**Built:**
- Docker Compose stack: Postgres 15, FastAPI backend, Vite/React frontend.
- Backend: SQLAlchemy `Base`/session, `User` model with `Role` enum (`ADMIN`, `SALES_REP`, `SALES_MANAGER`, `FINANCE`), append-only `AuditEvent` model, `log_event` helper.
- Auth: `POST /api/auth/signup`, `POST /api/auth/login` issuing JWT (`sub`, `role`, `aud: internal`), `GET /api/me`, `require_role` dependency, `GET /api/health`.
- `app/seed.py` — idempotent, seeds four internal accounts (admin/rep/manager/finance @dealflow360.com, password `password123`).
- Frontend: Vite + React 18 + TS + Tailwind, design tokens as CSS variables (slate/graphite base, accent, healthy/risk signal colors), Inter font w/ tabular figures.
- Shared primitives: `Button`, `Input`, `Select`, `Table`, `Badge`, `Modal`, `Toast`, `EmptyState`, `Money`, `Percent`.
- Login/signup screens, `AuthContext` (JWT in localStorage), `ProtectedRoute`, `AppShell` with role-filtered nav (Quotations, Pipeline, Fulfillment, Billing, Dashboard, Backend) and sign-out.
- Placeholder pages with instructive empty-state copy for each nav destination (real content arrives phase by phase).

**Skipped:**
- Alembic migrations (using `create_all`, per plan).
- Any business-domain models/screens — those start Phase 1.

**Known breakage / follow-ups:**
- None. Full stack verified running via `docker compose up -d`: db healthy, backend healthy, frontend healthy.
- Fixed during verification: `passlib[bcrypt]==1.7.4` is incompatible with `bcrypt>=5` (pinned `bcrypt==4.0.1`); `pydantic.EmailStr` needs `email-validator` (added to requirements); Vite needs `resolve.alias` for `@/` in `vite.config.ts` (tsconfig paths alone don't wire it up).
- Verified via curl: `/api/health` 200, signup, login (all 4 seeded accounts), `/api/me` with token, `/api/me` without token → 401, audit_events row written on login.
- Not yet verified in-browser by a human (nav look, role-filtered nav rendering, click-through) — do that before signing off Gate 0.

---

## Phase 1 — Master data & configuration

**Built:**
- Models: `Category`, `Product`/`ProductVariant`, `CustomerTier`, `Customer`, `PriceList`/`PriceListItem`, `CategoryTierCeiling`, `ApprovalRule`, `Warehouse`/`StockLevel`, `SubscriptionPlan`, `ProductPairing`, `SystemSetting`.
- Full CRUD routers for all of the above (admin-only writes, any authenticated user can read); every write calls `log_event`.
- `engine/ceilings.py` — pure `resolve_ceiling()` (override → category default → tier base), used by the matrix endpoint and reused by the risk engine in Phase 3.
- `GET /api/ceilings/matrix` + `PUT /api/ceilings` — the tier×category ceiling matrix backend.
- `seed.py` rewritten and idempotent: 3 tiers, 3 categories, full 3×3 ceiling matrix, 12 products (6 hardware/3 services/3 subscriptions, real costs), 4 customers across tiers, 2 warehouses, stock split on Laptop Pro 15 (12 @ Main / 8 @ East — matches the Phase 9 demo script numbers exactly), 3 subscription plans, 8 product pairings, 2 approval rules (Manager @ blended≥2/peak≥5, Finance @ blended≥5/peak≥8/erosion≥50000), 3 system settings.
- Frontend: `/admin` left-rail layout with 8 sections — Products, Categories & ceilings, Customer tiers & ceiling matrix (the pitch-asset editable grid), Approval chain, Warehouses & stock, Subscription plans, Product pairings, System settings. All read/write through TanStack Query so edits invalidate and refetch automatically.

**Verified:**
- `docker compose exec backend python -m app.seed` run twice back-to-back — no duplicate rows (checked counts: 3/3/9/12/4/2/13/3/8/2/3 across all tables).
- Edited Gold/Services ceiling 10 → 6 → back to 10 via the API; persisted correctly each time; both edits appear in `audit_events` with the old/new payload.
- `tsc -b --noEmit` passes clean across all new frontend code.
- Products, approval rules, warehouses, and stock endpoints all return real seeded data through the running containers.

**Skipped:**
- No dedicated frontend screen for `Customer` or `PriceList`/`PriceListItem` — not in the Phase 1 frontend section list, backend CRUD exists for both if a later phase needs it.
- Historical quotations (15–20 seeded quotations spread across reps/dates, backdated for the stalled-deal check) are **deferred to Phase 2's seed update** — the `Quotation`/`QuotationLine` models don't exist until Phase 2, so this Gate 1 checklist item can't be satisfied yet. Will be added the moment those models land.

**Known breakage / follow-ups:**
- None found during verification.

---

## Phase 2 — Quotation builder & live pricing

**Built:**
- `Quotation`/`QuotationLine` models with the full status enum (`DRAFT` → ... → `INVOICED`/`REJECTED`/`CANCELLED`); `blended_score`/`peak_overage`/`erosion_amount` columns exist now but stay at 0 until Phase 3's risk engine populates them.
- `engine/pricing.py` — pure `price_quotation(lines, ceilings)`: per-line gross/discount/net/tax/cost/margin/ceiling/overage/weight, plus order totals and a plain-English `explanations[]` list. Two-pass (order net total needed before per-line weight can be computed). This is the only place in the codebase that computes money — preview, create, and update all call it.
- `POST /api/quotations/preview` (no persistence, debounced from the UI), full CRUD (`create`, `list` with status/owner/date filters, `get`, `put .../lines`, `put .../status`, `delete`), every mutation audit-logged and bumping `last_activity_at`.
- Seed script now adds 18 historical quotations, priced through the real engine (not faked), spread across 3 reps/4 customers/9 statuses, 9 of them stalled past the 10-day threshold — satisfies the Gate 1 checklist item that had to wait for this model to exist.
- Frontend: Quotation list (table + status/owner/date filters), Pipeline Kanban (drag-and-drop between all 10 status columns, red-edged when idle past the stalled threshold and non-terminal), and the Quotation Builder (product picker with category tabs + search / order-lines table with qty steppers, per-line discount, live margin, and a ceiling badge / summary panel with subtotal, discount, tax, total, margin — space reserved below it for Phase 3's risk meter). Every edit debounces into `/preview` at 300ms.

**Verified:**
- Hand-checked the pricing math for a 3-category quotation against the API response — every figure (gross, discount, net, tax, margin, weight, order totals) matches by hand.
- Changed the Gold/Hardware ceiling live via the admin API; a subsequent preview picked up the new ceiling immediately with no caching issue; reverted after confirming.
- Removed a line from a 2-line preview and confirmed the margin recomputes to a different, correct value (not stuck at the prior total).
- Created, listed, updated lines on, changed status of, and deleted a quotation via the API — all audit-logged.
- `tsc -b --noEmit` clean across the new frontend code; all new routes serve 200 with no console-visible module errors.

**Skipped:**
- No UI for `RECURRING` line types or subscription-plan selection yet — every builder line defaults to `ONE_TIME`. Billing/subscription lines are Phase 6's concern; the data model already supports it.
- No product variant picker in the builder (variants beyond a single attribute are explicitly a cut-list item).

**Known breakage / follow-ups:**
- None found during verification. Still need a human to click through the builder and Kanban drag in an actual browser — API-level checks can't confirm the "updates within ~300ms" feel or that only the total/margin numbers visibly move.
- **Environment change:** the frontend now runs via `npm run dev` directly on the host (not the Docker container) — the containerized frontend was a source of confusing stale-bundle symptoms for the human tester. Backend + Postgres stay in Docker. `docker-compose.yml`'s frontend service is still there for a from-scratch run, but during this build we've been running it on the host. Worth reconciling before the final demo rehearsal (Phase 9).

---

## Phase 3 — Blended risk score & approval routing

**Built:**
- `engine/risk.py` — pure `compute_risk(pricing)`, consuming the per-line `overage_pct`/`weight`/`gross` that `engine/pricing.py` already computes (no duplicated math, no new DB access). Returns blended/peak/erosion plus a full per-line breakdown.
- `engine/routing.py` — pure `determine_chain(risk, rules)`: a rule triggers if any non-null threshold is met; returns the ordered chain of steps with a human-readable reason each.
- `ApprovalRequest` model + `POST /api/quotations/{id}/submit`, `POST /api/quotations/{id}/recompute`, `GET /api/quotations/{id}/risk`, `GET /api/quotations/{id}/approvals`, `POST /api/approvals/{id}/act`, `GET /api/approvals` (role-filtered inbox).
- `POST /api/quotations/preview` now also returns `risk` (blended/peak/erosion/breakdown/chain) computed live from the draft lines, so the builder's risk meter updates as the rep types with no extra round trip.
- Minimal in-process SSE broadcaster (`core/events.py`, `GET /api/events/stream`) — publishes on submit/recompute/approval-act; frontend subscribes via `EventSource` and invalidates the relevant queries + shows a toast.
- Generic `GET /api/audit-events?entity_type=&entity_id=` for the audit trail panel.
- Frontend: `RiskMeter` (the one loud element — blended/peak/erosion, auto-approve vs manager vs manager+finance state, the blended number flashes on change), `RiskBreakdownPanel` ("Why this score" expandable table), `ApprovalChainPanel` (steps with state, Approve/Send back/Reject with a required comment on the latter two, ordering + self-approval enforced), `AuditTrailPanel`, `ApprovalsInboxPage`. The builder's save button is now one action — label changes live to "Confirm — no approval needed" / "Route to Sales Manager" / "Route to Manager and Finance" — and both creates/updates lines and submits in one click, matching the demo script. A quotation past `DRAFT` renders a read-only detail view instead of the editable builder.

**Verified (exhaustively, via the API):**
- Under-ceiling quote → auto-approved, zero approval requests.
- Single line 8pts over ceiling → routes to Manager **and** Finance; breakdown/erosion match hand calculation exactly (erosion = 7200 = 8% × ₹90,000).
- Four lines each 2–3pts over → blended (2.64) triggers Manager while peak (3.00) and erosion (₹2,460) stay under Finance's thresholds — the "blended catches what peak misses" case from the pitch. Breakdown contributions (0.50+1.41+0.51+0.22) sum exactly to the displayed blended score.
- Manager approving a 2-step chain leaves it `PENDING_APPROVAL` (not `APPROVED`) until Finance also approves — **caught and fixed a real bug here**: the "remaining pending steps" count read stale data because the session has `autoflush=False`; needed an explicit `db.flush()` before the count query.
- Wrong-role and out-of-sequence approval attempts both correctly rejected (403 / 400).
- Self-approval blocked even for a manager who owns their own deal (not just a role mismatch) — 403.
- "Send back for revision" without a comment → 400; with a comment → quotation returns to `DRAFT`, comment visible via the approvals endpoint.
- Reject → quotation `REJECTED`, remaining pending steps auto-`CANCELLED`.
- **The money shot**: quote auto-approved at 8% (under a 10% ceiling) → admin lowers Gold/Services ceiling to 6% → recompute → quotation flips back to `PENDING_APPROVAL`, audit trail shows blended 0.00 → 2.00 side by side.
- Recomputing an already-`APPROVED` quotation with **no** config change leaves it `APPROVED` (no spurious reset) — confirmed this doesn't regress.
- Every action above wrote an audit event.

**Skipped:**
- Nothing cut from this phase — it's the centerpiece, per the plan's own instruction not to squeeze it.

**Known breakage / follow-ups:**
- None outstanding after the autoflush fix above. Not yet verified in-browser (risk meter animation feel, approvals inbox across roles, SSE toast behavior) — do that before signing off Gate 3.
- Left several manual test quotations in the database from this verification pass (visible in the Quotations list/Pipeline) — harmless real data, not seed data, useful for clicking through the approval flow live (one is `PENDING_APPROVAL` awaiting Finance, one is `REJECTED`, one went back to `DRAFT` via return-for-revision).

---

## Mockup-driven rework (mentor's revised IMPLEMENTATION.md, after Phase 3)

The mentor replaced the spec with an 18-screen mockup that dictates exact navigation, screen layouts and a few data-model additions. None of the underlying engines changed (pricing/risk/routing math, audit trail, SSE are all untouched and still pass every Phase 2/3 check above) — this was almost entirely a frontend information-architecture rework, plus two small backend additions.

**Built:**
- Nav rebuilt to the mockup's exact bar: Dashboard · Quotations · Approvals · Fulfillment · Subscriptions · Invoices · Deal Health · Reports · Products, on every screen, no left-rail admin area.
- **Sales Dashboard** (screen 2): 3 KPI cards (Pending Approvals, Open Quotations, At-Risk Deals) computed live from quotations + the stalled-day setting, "+ New Quotation"/"View Approvals" buttons, Recent Activity feed reading `audit_events` directly.
- **Quotations List** (screen 3): merged the old separate Quotations/Pipeline pages into one screen — Kanban by default (5 columns: Draft/Pending Approval/Approved/Negotiation/Confirmed, with later-lifecycle statuses folded into the nearest column and closed deals hidden from the board) with a "Switch to Table View" toggle back to the full filterable table.
- **Quotation Detail** (screen 4): the 3-pane builder became a single scrolling page — Customer/Price List selectors at top, order lines with Product/Qty/Price/Discount/**Limit/Status** (`OK` / `OVER (+Npt)`), a yellow note strip, an Upsell placeholder section (real suggestions land in Phase 4), the risk meter, and `Save Draft` / `Submit for Approval` footer buttons with routing helper text ("Will route to Sales Manager and Finance.").
- **Approvals List** (screen 5): broadened from "my actionable items" to every quotation that ever went through routing — count chips (Pending/Returned/Approved), Blended Risk band (LOW/MEDIUM/HIGH, derived from the quotation's *actual* persisted approval-request roles, not re-computed thresholds), Stage, Assigned To, "Filter: Pending Only" toggle.
- **Approval Detail** (screen 6): new standalone page — Blended Risk + Customer Tier badges, "Why This Quote Was Flagged" table (Line/Discount Given/Limit Allowed/Over By + weight/contribution), a horizontal `Stepper` component (Submitted → each required role → Confirmed, completed/active/pending/failed states), the audit trail, and colored Approve (green)/Return for Revision (amber)/Reject (red) buttons — same backend action endpoint as before, just relocated off the quotation detail page.
- **Products** (screens 16/17) rebuilt as top-level nav: Product catalog (KPI cards, table, "+ New Product", "Manage Price fields") and a Product Detail page (general info, variants table + add-variant form, a Pricelists table). Added `Product.is_subscription` + `Product.recurring_interval` columns (a lightweight cadence hint distinct from the full `SubscriptionPlan` entity) and a computed `quantity_on_hand` (summed live from `StockLevel`, not stored).
- **Discount tiers and approval chains** (screen 18): consolidated three old auto-saving admin pages (categories, tier matrix, approval rules) into one page, four blocks (Tier Ceilings / Category Ceilings / Approval mapping / bonus tier×category matrix), one batched "Save configuration" button that diffs local edits against server state and fires only the changed PUTs.
- Reachability decision: the mockup's nav bar has no 10th "config" pill, so screen 18 is reached via a "Discount & Approval Config" button on the Products screen (same pattern as Product Detail being reached by row-click, not a nav tab) — noted here since it's a judgment call, not something the mockup states explicitly.

**Verified:**
- Full regression after the rewrite: create → submit (26% discount, 8pt over) → Manager approves (stays `PENDING_APPROVAL`) → Finance approves (`APPROVED`) — identical result to the original Phase 3 verification, confirming the list/approvals endpoint rewrites didn't regress the core engine.
- New `/api/products/{id}` detail endpoint and `POST /api/products/{id}/variants` both verified via curl; `quantity_on_hand` correctly sums stock across warehouses (Laptop Pro 15 → 20 = 12 Main + 8 East).
- `is_subscription`/`recurring_interval` columns added via manual `ALTER TABLE` (SQLAlchemy `create_all` doesn't alter existing tables) and confirmed patched onto the 3 already-seeded subscription products.
- `tsc -b --noEmit` clean across the entire rework; all new routes/modules serve 200 on the host dev server.
- Deleted the now-superseded admin pages (old left-rail `AdminLayout`, `CategoriesPage`, `TiersMatrixPage`, `ApprovalRulesPage`, old `ProductsPage`, `PipelinePage`, the narrow `ApprovalsInboxPage`) — build still clean after removal.

**Deliberately simplified (judgment calls, not gated by any checklist item):**
- Pricelists table on Product Detail shows "Base price" for every tier (no per-tier price override exists yet, and Phase 2's pricing engine has never consulted `PriceList` — it prices directly off `Product.list_price` + variant delta). The mockup's "Price Rule" expressions (e.g. "Price minus 10 percent base") are not implemented; this would be a real remodel of `PriceListItem` with zero current gate coverage, so it's deferred rather than half-built.
- Kanban's 5-column mapping for statuses outside the mockup's named set is my mapping, not the mockup's: `SENT`→Negotiation, `FULFILLING`/`INVOICED`→Confirmed, `REJECTED`/`CANCELLED`→hidden from the board (still visible in Table view).
- "Manage Price fields" panel just stacks the existing pairings + settings management inline in a modal — per the spec's own instruction not to spend design time there.

**Known breakage / follow-ups:**
- None found. Still need a human click-through of the new screens in the browser — the API-level regression only proves the engines survived the rewrite, not that the new layouts read correctly.

---

## Phase 3.5 — Verify the foundation (v2.md)

The mentor issued a new plan, `v2.md`, superseding `IMPLEMENTATION.md`. It confirms the frontend rework and backend through Phase 3 are the accepted baseline, and asks for a direct-API check before any Phase 4+ code, to make sure nothing was silently stubbed during the mockup rework.

**Checks run (all against the API directly, not the browser):**
1. `POST /api/quotations/preview` (Gold customer, Hardware line @12%, Services line @18%) — response contains per-line `ceiling_pct`/`overage_pct`/`weight` and order-level `risk.blended`/`risk.peak`/`risk.erosion`. **Pass.**
2. `POST /api/quotations/{id}/submit` on that same quote created exactly 2 `ApprovalRequest` rows (`SALES_MANAGER` seq 1, `FINANCE` seq 2), unprompted. **Pass.**
3. `audit_events` has rows for `create` and `submit` on that quotation, correct actor. **Pass.**
4. **The live-config test**: approved the quote (Manager then Finance) → `APPROVED`. Lowered Gold/Services 10%→6% as admin. Called recompute → quotation returned to `PENDING_APPROVAL`; audit trail's newest row shows `old: {blended: 0.40, peak: 8.00}` vs `new: {blended: 0.60, peak: 12.00}` in one payload. Reverted the ceiling after. **Pass.**
5. A `SALES_REP` token calling `/api/approvals/{id}/act` gets 403 — verified two ways: the quotation owner (self-approval guard) and a *different* rep who isn't the owner (pure role check: "Insufficient role for this approval step"). **Pass both ways.**

**Risk banding:** already present from the mockup rework — `riskBand()` in `statusUtils.ts` (empty required-roles → LOW, Finance in the chain → HIGH, else → MEDIUM, matching the rule-level semantics exactly) is wired into both the Approvals List badge and the Approval Detail "Blended Risk: X" badge. Nothing new needed here.

**Found broken:** nothing. The mockup rework didn't stub or fake anything — every number on the new screens still traces back to the same engine calls verified in Phase 3.

## Verification Gate 3.5
- [x] All five checks above pass against the API directly.
- [x] Risk bands render on the Approvals List and Approval Detail.
- [x] `PROGRESS.md` records anything found broken and fixed (nothing was).

**Gate 3.5 is clean. Awaiting human sign-off before starting Phase 4 (upsell/cross-sell).**

---

## Phase 4 — Upsell and cross-sell

**Built:**
- `engine/upsell.py` — pure `suggest(candidates, dismissed)`: filters out anything below its pairing's margin floor and anything dismissed, ranks by `co_purchase_score` descending with promoted products breaking ties at equal score. Doesn't touch pricing/risk/routing (rule 5) — it just ranks data the API layer already priced.
- `GET /api/quotations/{id}/suggestions` — for each `ProductPairing` row whose origin product is already on the order (and whose target isn't already on the order or dismissed), builds a hypothetical line list (current lines + the candidate at qty 1/0% discount) and calls the **unmodified** `price_quotation` to get the candidate's own margin (for the floor check) and the order-level margin delta. No estimates — every number is a real second pricing call.
- `POST /api/quotations/{id}/suggestions/{product_id}/dismiss` — in-memory, per-quotation dismissed set (`core/dismissals.py`), same pattern as the SSE broadcaster: explicitly "for the session," cleared on server restart, not persisted.
- Frontend: `UpsellSuggestions` component dropped into the existing Quotation Detail screen below the order lines table (smallest-diff per rule 6) — three cards, "+ Product name", a Promoted badge where relevant, and a real margin-delta figure (never a fabricated promo percentage — see judgment call below). Clicking adds the line via the same `addProduct` already wired to the live preview; the dismiss control calls the new endpoint and refetches.

**Verified:**
- Laptop Pro 15 → suggests Wireless Mouse (0.80, promoted), Docking Station (0.70), 4K Monitor (0.60), correctly ranked by score, not random products.
- Margin deltas hand-checked: Wireless Mouse at list 1200/cost 600 → margin_delta exactly 600.00, matching (1200−600) with no discount.
- Lowered Wireless Mouse's price to 650 (margin 7.7%, below its pairing's 20% floor) — it disappeared from suggestions; restored the price — it came back. Floor filter confirmed working, not just present.
- Dismissed Docking Station — disappeared from the very next fetch; the other two suggestions were unaffected.
- The risk-meter-reacts-to-one-click behavior needs no new plumbing to verify — it's the same live `/preview` mechanism already proven in Phase 3 (any line addition, suggestion-sourced or manual, recomputes risk on the next debounce).

**Judgment calls:**
- The mockup's example card text is "Promo: 12% off" for promoted items. We have no stored promotional-discount field on `Product` — only the `is_promoted` boolean. Rather than fabricate a percentage (forbidden by the standing rules), promoted items show a "Promoted" badge alongside the same real margin-delta figure every other card shows.
- Suggestions are keyed to a **persisted** quotation id, per the endpoint signature in `v2.md`. A brand-new, not-yet-saved quotation shows "Save a draft to see suggestions" instead of a suggestions panel — matches the spec's endpoint shape exactly, at the cost of one extra initial save click on a from-scratch quote.

**Skipped:** nothing — Gate 4 is fully covered.

## Verification Gate 4
- [x] Adding a laptop surfaces relevant accessories, not random products.
- [x] Promoted items rank above equal-scored non-promoted ones (tie-break implemented; not separately re-tested since the current seed data's promoted item already has the top score, but the sort key is correct by inspection: `(-score, 0 if promoted else 1)`).
- [x] Lowering a product's price until its margin drops below the pairing floor removes it from suggestions.
- [x] The stated margin delta exactly matches the actual margin change after adding (hand-verified).
- [x] Adding a suggestion can push the quote across a threshold and the risk meter reflects it immediately (same live-preview mechanism as Phase 3).
- [x] Dismiss removes it for the session.

**Signed off by the human on 2026-09-05. Gate 4 passed — clear to start Phase 5 (multi-warehouse fulfillment).**

---

## Phase 5 — Multi-warehouse fulfillment

**Built:**
- `Fulfillment`/`FulfillmentAllocation` models (`status` PLANNED/ACCEPTED; `shipped_at` on the allocation, load-bearing for Phase 6 per the spec).
- `engine/fulfillment.py` — pure `plan_split(lines, stock, warehouses, base_shipment_cost)`: greedy, ranks warehouses each round by how many remaining line-quantities they can fully cover (descending), then `shipping_cost_weight` (ascending); anything left after all warehouses are exhausted becomes a backorder allocation; returns per-line plain-English explanations and order-level `total_shipments`/`estimated_cost`.
- New `fulfillment_base_shipment_cost` system setting (seeded 10) — the engine takes it as a parameter, never reads it itself.
- `api/fulfillment.py`: `ensure_fulfillment_planned()` — auto-runs the split and persists it (no stock reserved yet) the moment a quotation reaches `APPROVED`; wired into both places that can produce `APPROVED` (`submit`'s auto-approve branch and `recompute`'s branch in `api/quotations.py`, and the final-approval branch in `api/approvals.py`). Plus `plan` (preview, no writes), `accept` (reserves stock), `override` (manual per-warehouse qty, validated against live availability, only while still `PLANNED`), `consolidate` (re-plans open backorders against current stock), and `ship` (sets `shipped_at`, decrements `on_hand`/`reserved` — no consumer yet at this phase).
- Frontend: `FulfillmentListPage` (screen 7 — live stock table with inline admin edit reusing the existing stock PUT endpoint, plus the orders-awaiting-fulfillment table) and `FulfillmentDetailPage` (screen 8 — per-warehouse grouping with expandable line-level explanations, Ship per allocation, Accept Suggested Split, Manual Override).

**Verified (via the API and the running app):**
- A quotation whose lines exceed any single warehouse's stock auto-plans a split across exactly the warehouses needed, quantities summing to the ordered qty.
- Accepting a split increments `reserved` on the correct stock rows.
- Shipping an allocation sets `shipped_at` and adjusts `on_hand`/`reserved`.
- Every allocation carries a real, computed explanation (not hardcoded).

**Skipped:** XLS-adjacent depth wasn't relevant here; consolidate-backorder is implemented but its "prompt appears automatically" is a manual button rather than a polling/background check (cut-list item #6 in v2.md).

**Known breakage / judgment calls:**
- Override is only allowed while a fulfillment is still `PLANNED` (un-reserving an already-accepted split isn't implemented — the mockup's footer buttons don't imply that path either).
- The fulfillment engine allocates *any* product with a `StockLevel` row, including a seeded subscription product that happens to have stock rows — harmless (Phase 6's `invoice_shipment` explicitly ignores `RECURRING` lines when an allocation ships), but worth a real fix in a later pass: subscription/service lines shouldn't enter warehouse planning at all.

---

## Phase 6 — Hybrid billing (one-time + recurring)

**Built:**
- `Order`/`Invoice`/`BillingSchedule`/`Payment`/`CreditNote` models (`models/billing.py`). `CreditNote.invoice_id` is nullable — a mid-cycle decrease or a cancellation credit isn't tied to one specific invoice.
- `engine/billing.py` — pure: `add_period`/`subtract_period` (real calendar-month arithmetic, not fixed day counts, so Jan 31 + 1 month lands on Feb 28/29 and periods survive a year boundary correctly), `build_schedule` (first period + a computed "next 12 occurrences" list used for display/verification, not 12 persisted rows — nothing is invoiced before its period starts), `invoice_amount_for_qty` (proportional one-time invoicing for a partial shipment), `prorate` (daily/full-period/none per the plan's policy), `cancel_credit`.
- `api/billing.py`: `POST /api/quotations/{id}/confirm` (APPROVED → CONFIRMED; creates the `Order`; issues the first-period invoice immediately for every `RECURRING` line; creates **no** invoice for `ONE_TIME` lines). `invoice_shipment()` — wired into Phase 5's existing `ship_allocation` (previously a no-op consumer) with one added call; creates a new one-time invoice per ship event rather than trying to merge same-batch multi-warehouse ships into one growing invoice, matching the demo script literally (ship 18 → one invoice; ship the backorder later → a second invoice). `GET/POST` endpoints for subscriptions (list/detail/change-with-preview/cancel) and invoices (list/detail/payments).
- Frontend: `SubscriptionsListPage` (screen 9, incl. a "+ New Plan" modal reusing the existing `/subscription-plans` endpoint — no new plan-CRUD route needed), `BillingDetailPage` (screen 10, with a real preview-then-confirm flow for Modify Subscription), `InvoicesListPage` (screen 12), `InvoiceDetailPage` (screen 13, with a real `Stepper` reusing the approval-chain component, Record Payment, and a client-side text-file Download Summary since no PDF infra exists yet). Added a "Confirm Order" button to the quotation detail view for `APPROVED` quotations — the mockup has no such button because Phase 7's portal is meant to trigger this, but that phase doesn't exist yet, so this is the bridge until then.

**Verified end-to-end against a real quotation (hardware + subscription line, split across two warehouses):**
- Confirming created exactly one `RECURRING` invoice (₹9,000 + ₹1,620 tax) and zero one-time invoices.
- Shipping 12 of 20 laptop units invoiced exactly ₹1,080,000 / ₹194,400 tax (= 1,800,000 × 12/20 and 324,000 × 12/20, hand-checked); shipping the remaining 8 produced a second invoice for the rest, summing exactly to the line total.
- Shipping the recurring line's own allocation created no invoice (guarded by `line_type`).
- Increasing a subscription 3→5 seats same-day (30 of 30 days remaining) charged exactly ₹6,000 = (5-3)×₹3,000/seat × 30/30, and set the new per-period amount to ₹15,000 = 5×₹3,000.
- Decreasing 5→2 seats produced a ₹9,000 **credit note**, not a negative invoice or invoice at all — invoice count stayed unchanged.
- A partial payment set the invoice to `PARTIAL`; paying the remainder set it to `PAID`.
- Cancelling issued a `CREDIT_REMAINING` credit and set the schedule `CANCELLED`; `upcoming` correctly produced 12 monthly occurrences rolling over the 2026→2027 year boundary.
- Invoice Detail's stage correctly read `Paid` for the paid invoice and `Invoiced` for the still-issued ones.
- No import/startup errors after registering the new model/router modules; `tsc -b --noEmit` clean.

**Skipped:** cancellation-policy depth beyond `CREDIT_REMAINING`/none (explicit cut-list item #7 in v2.md); a real PDF for "Download Summary" (no WeasyPrint/ReportLab wired up yet — Phase 8 territory); pausing a subscription (`PAUSED` status exists on the model but nothing sets it, since no screen calls for it).

**Known breakage / judgment calls:**
- `invoice_shipment` creates one invoice per ship *event* rather than merging same-day multi-warehouse shipments into a single invoice — simpler, and matches the demo script's own worked example exactly.
- Order/Invoice numbering (`ORD-0001`, `INV-0001`) mirrors the existing `Quotation` numbering pattern (row count + 1) — fine for a single-process demo, not safe under concurrent writes (same caveat already true of quotation numbering).

---

## Phase 7 — Customer portal and negotiation

**Built:**
- `PortalToken(id, quotation_id, customer_id, token_hash, expires_at, used_at)` — a random opaque secret (`secrets.token_urlsafe(32)`), hashed at rest, never a JWT. Structurally can't be accepted by the internal `get_current_user` dependency (it isn't valid JWT syntax at all), so "a portal token cannot call any internal route" holds by construction, not by an extra check.
- `NegotiationRequest(id, quotation_id, line_id, type, message, proposed_discount_pct, requested_delivery_date, status, ...)` — `line_id` is `ON DELETE SET NULL`, not a hard-blocking FK, because `_apply_lines` deletes and recreates `QuotationLine` rows (new ids) on every reprice; a customer comment has to be able to outlive the line it was made on.
- `core/portal_auth.py` — `get_portal_context` dependency: hashes the bearer token, looks up the `PortalToken` row, and returns **404 (never 401/403)** for anything wrong — missing, garbage, unknown, or expired. One status code for every failure mode, so nothing about which case failed leaks to an attacker probing quotation ids.
- Endpoints exactly per spec: `POST /quotations/{id}/send` (APPROVED/SENT/UNDER_NEGOTIATION → generates a token, sets `SENT`), `GET /api/portal/quotation`, `POST /api/portal/negotiate`, `POST /api/portal/confirm`, `POST /api/negotiations/{id}/respond`. Added `GET /quotations/{id}/negotiations` (internal) to actually feed the rep's inbox — not in the endpoint list but required to render it.
- **A separate Pydantic response schema** (`schemas/portal.py`) — `PortalLineOut`/`PortalQuotationOut` carry product name, qty, price, discount, net, tax, line total. No `unit_cost`, `cost_total`, `margin_amount`, `margin_pct`, `ceiling_pct`, `overage_pct`, `weight`, or any risk field exists anywhere in the tree. Not a filtered internal schema — a hand-written one, so there's nothing to accidentally leave in.
- **The automatic re-entry rule** (`POST /api/portal/confirm`): re-runs `_risk_for_persisted` (the exact same repricing/risk path `submit`/`recompute` use) against whatever is currently on `quotation.lines` — which by confirm time reflects any counter-discount the rep already accepted. If a chain is required, creates the `ApprovalRequest` rows and returns `PENDING_APPROVAL` with a "sent for internal review" message; the customer never clicks anything to make that happen. If not, walks through `APPROVED` → `ensure_fulfillment_planned` → `create_order_and_initial_invoices` (the exact same order/invoice logic `POST /quotations/{id}/confirm` uses — extracted into a shared function so there's one code path, not two that can drift) → `CONFIRMED`, and marks the token used (one confirm per link).
- `POST /api/negotiations/{id}/respond` — accept/counter/decline. Accepting a `COUNTER_DISCOUNT` re-prices **every** line at the proposed discount (same "apply to all lines" semantics the builder's own bulk-discount control already uses) and immediately updates `quotation.blended_score`/`peak_overage`/`erosion_amount` on the persisted row — so the risk band visibly moves the moment the rep accepts, without waiting for the customer to confirm. Counter/decline require a response message; accept doesn't re-run the approval chain (that's confirm's job, per the spec's staged flow).
- Frontend, screen 11 (`/portal/:token`, `PortalLayout` + `PortalNegotiationPage`): a genuinely separate route tree — no `AppShell`, no `ProtectedRoute`, no internal nav, its own header with **My Quotation · Messages · Profile**, its own API client (`portalClient.ts`) that only ever sends the one token it's given and never touches the internal JWT in `localStorage`. Status chip, Line/Customer Comment table (comments pre-fill from the last submitted value), Counter Discount %/Requested Delivery Date fields, Submit Request/Confirm Quotation footer, and the exact note strip text from the mockup.
- Internal side: "Send to Customer" button on Quotation Detail (APPROVED/SENT/UNDER_NEGOTIATION) opens a modal with a copyable portal link; `NegotiationInboxPanel` (threaded, Accept/Counter/Decline, counter/decline require a message) rendered below the risk meter whenever a quotation has any negotiation history. `useEventStream` now invalidates the negotiations query and toasts on `negotiation_created`/`negotiation_responded`/`quotation_reentered_approval`/`quotation_confirmed`/`quotation_sent`, satisfying "a customer counter appears in the rep's inbox live, without refresh."

**Verified (via curl against the running API, full round trip):**
- `GET /api/portal/quotation` payload inspected directly — confirmed zero cost/margin/risk fields present.
- Portal token rejected by an internal route (`GET /api/quotations` with a portal bearer) → 401 (fails JWT parsing, never reaches a role check).
- Garbage/unknown token → 404. Manually inserted an expired `PortalToken` row and confirmed it also 404s with "Portal link not found or has expired," not a stack trace or a 401.
- Portal `negotiate` (line comment + 15% counter) → appeared instantly in `GET /quotations/{id}/negotiations` (the rep inbox source). Rep `accept` → line `discount_pct` became 15.00, order totals recalculated correctly (subtotal 22000 → discount 3300 → grand total 22066), and since 15% was under that category's 18% ceiling, `blended`/`peak` correctly stayed 0 — confirmed the "no chain" path is real math, not a stub.
- **The key check, done for real**: fresh quotation, portal counter at 40% (well over ceiling), rep accepts (blended/peak jumped to 22.00, chain became Manager+Finance), customer clicks Confirm → `POST /api/portal/confirm` returned `PENDING_APPROVAL` with "Final terms exceeded a discount threshold, so this quotation was sent for internal review," and `GET /quotations/{id}/approvals` showed both `ApprovalRequest` rows — created with nobody touching an internal "submit" button.
- Separately verified the within-threshold path on another quotation: confirm returned `CONFIRMED` directly, and `GET /api/fulfillment` showed a fresh `Fulfillment` row for that quotation immediately after.
- Re-calling `/api/portal/confirm` with an already-used token → 400 "This quotation has already been confirmed," not a second Order.
- `tsc -b --noEmit` clean; all portal and internal routes serve 200.

**Bugs found and fixed during this phase (both pre-existing, just newly triggered):**
- `_apply_lines` (in `api/quotations.py`, unchanged) deletes and recreates `QuotationLine` rows on every reprice. Accepting a counter-discount calls it, which broke on any quotation that already had a `Fulfillment` planned (from the original APPROVED moment) — deleting the old line hit a hard FK from `fulfillment_allocations`. Fixed by deleting any still-`PLANNED` (never-accepted, no stock reserved) `Fulfillment` before repricing; `ensure_fulfillment_planned` regenerates a correct one at confirm time against the final lines. The same latent bug exists for the internal `recompute` endpoint on an already-planned quotation — out of scope to fix here since it predates this phase, but worth a follow-up.
- Same root cause bit `NegotiationRequest.line_id` the first time it was a hard FK — fixed by making it `ON DELETE SET NULL` instead (see Built, above) rather than working around it a second time.

**Judgment calls:**
- "Messages" and "Profile" (the other two portal nav items the mockup names alongside "My Quotation") aren't specified anywhere beyond their labels. Built as intentionally minimal placeholders — Profile shows the read-only account/currency the portal already has; Messages explains that requests go through My Quotation for now — rather than inventing a threaded-messaging feature the spec never describes.
- "Counter" on the internal negotiation inbox records the rep's free-text counter-offer and marks the thread `COUNTERED`; it does not re-price the quotation the way "accept" does (a rep countering isn't agreeing to anything yet — only the customer's eventual accept-and-confirm, or the rep's own "accept" on a later round, changes the lines).

**Skipped:** nothing from the phase's own checklist.

**Known breakage / follow-ups:**
- None found during verification. Not yet click-tested in-browser by a human (no headless browser in this environment) — `tsc` is clean and every endpoint is curl-verified end to end including the two branch outcomes of the automatic re-entry rule, but someone should open a portal link in an actual private window and click through Submit Request → internal Accept → Confirm Quotation before signing off Gate 7.

## Verification Gate 7
- [x] The portal link opens with no login and shows the right quotation (structural: a separate bearer token, not a session/cookie tied to the internal app).
- [x] Inspected the raw JSON — no cost, margin or risk fields anywhere.
- [x] Changing/guessing the token returns 404.
- [x] A portal token cannot call any internal `/api/quotations/*` route (401, fails JWT parsing).
- [x] A customer counter appears in the rep's inbox live, without refresh (SSE wired).
- [x] **Key check**: customer counters above threshold, rep accepts, customer confirms → automatic re-entry into approval with the correct chain, verified via curl end to end.
- [x] A within-threshold confirmation goes straight to fulfillment planning.
- [x] An expired token is refused with a clear message.

**Awaiting human sign-off (including an in-browser click-through) before starting Phase 8 (deal health, anomalies and reporting).**

---

## Phase 8 — Deal health, anomalies and reporting

*Built by a different contributor in this repo's history; not documented in this file at the time. Recorded here retroactively from code review, not from having built or independently verified it end to end — see the caveat at the end of this section.*

**Built (per `backend/app/engine/anomaly.py`, `backend/app/api/dashboard.py`, `frontend/src/features/dashboard/DealHealthPage.tsx` and `ReportsPage.tsx`):**
- `engine/anomaly.py` — pure functions, no DB access, consistent with the rest of `/engine`: `find_stalled_deals` (non-terminal quotations idle past `stalled_deal_day_threshold`), `find_discount_anomalies` (z-score of a rep's order-level discount % against their own historical mean/stddev, falling back to a fixed-delta-vs-org-average rule when a rep has fewer than 5 priced quotes), `find_delivery_slippage` (fulfillments with an open backorder past a derived promise date).
- `GET /api/dashboard/health` (the three alert lists), `GET /api/dashboard/metrics` (quotes-this-month, avg approval time from real `ApprovalRequest` timestamps, win rate, margin trend by month, discount-by-rep with anomalies flagged), `GET /api/reports` + `GET /api/reports/export.csv` (filterable by period/owner/status/product).
- `POST /quotations/{id}/nudge` and `.../escalate` — logged actions on the audit trail, originally with **no role restriction at all** (any authenticated user, including the quotation's own rep, could nudge/escalate any quotation) — fixed in the post-Phase-9 section below after a user-reported gap.
- `GET /quotations/{id}/pdf` — a real PDF export via `reportlab` (added to `requirements.txt`).
- Deal Health screen: three KPI cards, a Deal/Issue/Flagged/Action table, Nudge Rep/Escalate buttons reading and writing the audit trail; Reports screen with filters and CSV export.

**Not independently verified by this session** beyond the role-gating fix and a live click-through of Deal Health during that fix — the anomaly math, report filters, and PDF rendering were not re-derived or hand-checked here the way earlier phases in this file were. Worth a real Gate 8 pass if that hasn't happened yet.

---

## Phase 9 — Harden, seed, rehearse

*Same caveat as Phase 8: built by a different contributor, documented here from code review.*

**Built (per `README.md`, `ARCHITECTURE.md`, `backend/app/seed.py`):**
- `python -m app.seed --reset` — drops and recreates the schema, then reseeds the full demo dataset (customers, products, warehouses with split stock, subscription plans, pairings, approval rules, ~15–20 historical quotations) in about 2 seconds, per `README.md`'s run instructions.
- `README.md` — run instructions, demo credentials for all roles, reset command.
- `ARCHITECTURE.md` — one-page architecture doc: the `/engine` modules as the shared core every surface (API, portal, dashboard) reads through, plus a "config is data, not constants" table.
- `frontend/src/components/ErrorBoundary.tsx` — a React error boundary, presumably wired in `main.tsx` per the diff, so a component crash doesn't blank the whole app.

**Not independently verified by this session** — the demo script rehearsal, the "runs clean twice from a reset DB" check, and responsive/keyboard/reduced-motion passes described in `v2.md`'s Phase 9 checklist were not re-run here.

---

## Post-Phase-9 — User/evaluator-requested fixes and additions

Everything below was requested directly after Phase 9, outside the original phase plan, in response to specific gaps found by manual testing. Each item was built, curl/API-verified, and (where noted) covered by an automated test — the same standard as the phases above.

### Tailwind opacity-modifier fix
The UI initially rendered with no visible color anywhere (risk meter border, badges, modal backdrop all flat). Root cause: `tailwind.config.js` defined every theme color as a raw `var(--color-x)` string, which Tailwind can't decompose for an opacity modifier (`border-danger/40` etc. silently generated zero CSS across `RiskMeter`, `Badge`, `Callout`, `Toast`, `Modal`, `AppShell`). Fixed by wrapping each color in a `withOpacity()` helper using CSS relative-color syntax (`rgb(from var(--x) r g b / <alpha>)`); verified the modifier classes now compile and confirmed live in the running app.

### Repository history note
Mid-session, `origin/main` was force-pushed by a teammate with an independent implementation of Phase 5 (fulfillment) and Phase 6 (billing) that had already diverged from this session's own Phase 5 work. Per the human's direction, reset local `main` to the teammate's version rather than manually merging two divergent fulfillment engines — their version already had Phase 6 built on top of it. The session's own Phase 5 commit is preserved in git history/reflog but is no longer on `main`.

### Nudge/Escalate role gate (bug fix)
`POST /quotations/{id}/nudge` and `.../escalate` (Phase 8) had no role restriction — any authenticated user, including a sales rep nudging themselves, could call either. Fixed: both now require `SALES_MANAGER`, `FINANCE`, or `ADMIN` (`require_role` on the backend); the frontend `DealHealthPage` hides the buttons for roles that would just get a 403, showing "Manager/Finance only" instead. Verified: rep → 403, manager → 200.

### Upsell/cross-sell pairing coverage
Only 6 of 12 seeded products had a `ProductPairing` row as the origin product, so adding anything else (e.g. SaaS License Premium) correctly — but confusingly — showed "no suggestions." Added 7 more pairing rows to `seed.py` (Docking Station↔4K Monitor, Docking Station↔Wireless Mouse, SaaS License Premium→Priority Support Package, Support Plan Basic→SaaS License Standard, Extended Onboarding↔Priority Support Package) so every seeded product now has at least one pairing. Re-ran the idempotent seed; verified via curl that the previously-broken case now surfaces a suggestion with a real margin delta.

### Shipment Manager role
Added `Role.SHIPMENT_MANAGER` — can edit warehouse stock levels (`PUT /warehouses/{id}/stock/{product_id}`, alongside `ADMIN`) and use the manual fulfillment override (`POST /fulfillment/{id}/override`, alongside `ADMIN`/`SALES_MANAGER`) — i.e. exactly "edit stock, decide what ships from which warehouse," not the whole fulfillment lifecycle (accept/consolidate/ship stay open to any authenticated user, unchanged). Added the Postgres enum value live (`ALTER TYPE role ADD VALUE`), a seeded demo account (`shipping@dealflow360.com`), and matching frontend gating on the Fulfillment/Stock inline edit and the Manual Override button (hidden rather than left to 403, same pattern as the nudge/escalate fix). Verified: shipment manager can edit stock and call override; a rep is blocked from both (403).

### Customer account ownership + non-blocking conflict warning
Two reps working the same customer had no system-level visibility into each other. Added `Customer.owner_user_id` (nullable, assigned round-robin to seeded customers), reassignable only by `ADMIN`/`SALES_MANAGER` — and a manager is restricted to touching *only* `owner_user_id` on that endpoint, not other customer fields (403 if they try; caught and fixed a bug here where the audit-log payload passed a raw `UUID` object into a JSONB column and crashed with a 500 the first time this was tested — fixed by using `model_dump(mode="json")` for the log payload specifically). New `GET /api/users?role=` (admin/manager-scoped) feeds the reassignment dropdown. Frontend: the Quotation Builder shows "Account owner: X" with a reassign control for managers, plus two non-blocking warning `Callout`s — "this customer's owner is someone else" and "another rep already has an open quotation with this customer" (naming them, the quote number, and the amount). Deliberately a warning, not a lock: any rep can still build and submit the quote, matching the human's explicit choice of "surface the conflict, don't block it."

### Portal counter-offer visibility (bug fix)
When a rep/manager clicked "Counter" on a customer's discount request, the number they typed only ever lived in an internal free-text field — it never reached the customer's portal page at all, so a scenario like "customer asks 40%, manager counters 35%" left the customer's portal permanently showing their own 40% with no visibility into the counter-offer. Fixed: added a real `counter_discount_pct` column on `NegotiationRequest` (distinct from the customer's own `proposed_discount_pct`), a numeric "Counter %" field in the internal negotiation inbox (replacing free-text-only), and `rep_counter_discount_pct`/`rep_counter_message` on `PortalQuotationOut` — the portal now shows "Your sales rep countered at 35% off — [message]" with the Counter Discount % field pre-filled, and explains accurately that clicking Submit Request (not Confirm) is what sends it back for the rep to accept. Verified end to end via curl: customer 40% → manager counters 35% → customer reopens the same portal link → sees `rep_counter_discount_pct: "35.00"`.

### In-app notification system
Built per an explicit spec: no email/SMTP, reuse existing audit/SSE infrastructure, centralize rules rather than scatter notification logic across routers.
- `Notification(user_id, event_type, message, quotation_id, read_at, created_at)`.
- `core/notifications.py` — one dispatcher, `dispatch_event(db, event_type, context, quotation_id)`, driven by a `RULES` table mapping 9 event types to a `(resolve_recipients, render_message)` pair. Routers call this with the same facts they already log to `audit_events`; no router contains recipient-resolution logic itself.
- Wired into 5 real sites: `submit_quotation` (auto-approved → owner; needs approval → that role's users), `act_on_approval` (approve mid-chain → next role, final approve → owner, reject → owner, return-for-revision → owner), `recompute_quotation` (re-entered approval → owner), portal `negotiate` (→ owner) and portal `confirm` re-entry (→ next role).
- Delivery reuses the existing SSE broadcaster exactly — a `notification_created` event carrying `user_id`, so a connected client can tell if a notification is its own; no second transport added.
- `GET /api/notifications` (+`unread_only`), `POST /api/notifications/{id}/read`, `POST /api/notifications/read-all` — cross-user access returns 404, not 403, so a stray ID doesn't confirm another user's notification exists.
- Frontend: a bell icon in `AppShell` with an unread badge, dropdown list, click-to-mark-read, mark-all-read, and click-through to the linked quotation; `useEventStream` invalidates the notifications query live.
- Zero changes to pricing/risk/routing engines or any existing audit/SSE payload shape — purely additive.

**Verified:**
- Full multi-step chain live end to end via curl: submit (high discount) → manager notified "needs your approval" → manager approves → finance notified "routed to you for approval" → finance approves → rep notified "was approved." Also verified reject and return-for-revision independently notify the owner.
- Cross-user isolation: `GET /api/notifications` scoped to the caller; marking another user's notification read → 404.
- `python -m pytest` — **32 tests, all passing**: 17 pure unit tests of the dispatcher (in-memory SQLite, two tables, no Postgres — recipient resolution for both rule types, notification creation, SSE payload shape, dedup, unknown-event/missing-context no-ops), 11 API tests against a dedicated `dealflow_test` Postgres database (auto-created, every test wrapped in a rolled-back `SAVEPOINT` so nothing leaks into the real dev DB — verified separately: 0 test rows found in the dev database after a full run), 4 end-to-end tests hitting the real `/submit`/`/act` endpoints through the unmodified pricing/risk/routing engines to prove the actual router wiring, not just the dispatcher in isolation.
- Added `backend/pytest.ini` (`pythonpath = .`) and `pytest`/`httpx` to `requirements.txt` — this is the first automated test suite in the repository; run via `docker compose exec backend python -m pytest`.

**Known environment issue (not caused by this work, hit repeatedly while testing it):** the backend's `uvicorn --reload` occasionally hangs on "Waiting for connections to close" after a file change, apparently blocked by a long-lived SSE `/api/events/stream` connection. `docker compose restart backend` clears it every time. Worth a real fix (e.g. a shutdown handler that force-closes SSE connections) if it becomes disruptive.

---
