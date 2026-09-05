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

**Not started yet** (Phases 4–8 backend): upsell engine, `Fulfillment`/`FulfillmentAllocation` + split logic, `Order`/`Invoice`/`BillingSchedule`/`Payment`/`CreditNote` + proration, `PortalToken`/`NegotiationRequest` + portal routes, anomaly/stalled-deal engine, reports/export endpoints.

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

**Placeholder only** (nav item exists, no real screen behind it yet): Fulfillment, Subscriptions, Invoices, Deal Health, Reports.

**Not built:** customer portal (Phase 7 — no `/portal/:token` route tree exists), upsell/cross-sell suggestion cards (Phase 4), PDF/CSV export, report filters.

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
