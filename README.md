# dealFlow360

A quote-to-cash platform that governs itself: pricing, discount ceilings, approval routing,
warehouse allocation, hybrid billing and deal-health anomaly detection are all driven by one
pricing engine and rules stored as data — not hardcoded thresholds.

## Run it

Requires Docker and Docker Compose.

```bash
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000/api (docs at http://localhost:8000/docs)
- Postgres: localhost:5433 (mapped from container's 5432 to avoid clashing with a local install)

First boot creates the schema automatically (`Base.metadata.create_all`) but does not seed data.
Seed it once the stack is up:

```bash
docker compose exec backend python -m app.seed
```

### Reset to a clean demo state

```bash
docker compose exec backend python -m app.seed --reset
```

Drops every table, recreates the schema, and reseeds ~15–20 historical quotations, products,
customers, warehouses with a deliberately split stock level, subscription plans, product
pairings and approval rules. Takes about 2 seconds. Run this right before a demo.

## Demo credentials

All internal accounts share the password below. Each role sees a different set of screens and
permissions — log in as each to see the full flow.

| Role | Email | Password |
|---|---|---|
| Admin | `admin@dealflow360.com` | `password123` |
| Sales Rep | `rep@dealflow360.com` | `password123` |
| Sales Rep (2) | `rep2@dealflow360.com` | `password123` |
| Sales Rep (3, high-discount outlier) | `rep3@dealflow360.com` | `password123` |
| Sales Manager | `manager@dealflow360.com` | `password123` |
| Finance | `finance@dealflow360.com` | `password123` |

`rep3` is seeded with a consistently higher discount pattern than the other reps, so their
quotes are the ones the anomaly detector on the Deal Health dashboard (`/deal-health`) flags out
of the box.

## Customer portal

The customer-facing negotiation portal has its own route tree, its own schema, and its own
token-based auth — it is not the internal app with a label changed. A rep generates a link by
clicking **Send to Customer** on a quotation detail page, which returns a URL of the form:

```
http://localhost:5173/portal/<opaque-token>
```

Anyone with the link can view and negotiate that one quotation (counter-offer, accept, decline)
with no login. The token is a random secret hashed at rest, scoped to a single quotation, and
expires after 14 days (configurable via `portal_token_expires_days` in Settings). Open the
network tab while using the portal to see that no cost, margin, or risk data is ever sent to it.

## Architecture

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the one-page diagram: the ER model plus the
`/engine` modules as the shared core that the API, the portal, and the dashboard all read
through.

## What we'd build next

- Multi-currency and multi-company support
- ML-ranked upsell trained on real co-purchase history, not seeded pairing scores
- Contract lifecycle and renewal management
- ERP / accounting system connectors
- Approval SLA escalation (auto-escalate a stuck approval after N hours)
- Mobile approvals

## Standing engineering rules

- One pricing function — if a number appears in two places, it came from the same call
  (`app/engine/pricing.py`).
- Every engine function returns its explanation alongside its result.
- Every state change writes an audit event (`app/models/audit.py`).
- Config is data — discount ceilings, approval thresholds, anomaly thresholds and stalled-deal
  windows are all rows in the database, editable from the Settings screen, never Python or
  TypeScript constants.
- Money is `Decimal` throughout the backend; the frontend never does money arithmetic itself.
- Timestamps are stored in UTC and formatted at the edge.
