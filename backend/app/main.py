import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    approval_rules,
    approvals,
    audit,
    auth,
    billing,
    categories,
    ceilings,
    customers,
    events,
    fulfillment,
    health,
    me,
    pairings,
    products,
    quotations,
    settings as settings_api,
    subscription_plans,
    tiers,
    warehouses,
)
from app.core.config import settings
from app.core.events import set_loop
from app.models.base import Base, engine

# Phase 0/1: create_all is fine for a 24h build; Alembic migrations are optional.
import app.models.user  # noqa: F401
import app.models.audit  # noqa: F401
import app.models.catalog  # noqa: F401
import app.models.customer  # noqa: F401
import app.models.pricing_config  # noqa: F401
import app.models.approval_rule  # noqa: F401
import app.models.warehouse  # noqa: F401
import app.models.subscription_plan  # noqa: F401
import app.models.pairing  # noqa: F401
import app.models.setting  # noqa: F401
import app.models.quotation  # noqa: F401
import app.models.approval_request  # noqa: F401
import app.models.fulfillment  # noqa: F401
import app.models.billing  # noqa: F401

Base.metadata.create_all(bind=engine)

app = FastAPI(title="DealFlow360 API")


@app.on_event("startup")
async def _capture_event_loop() -> None:
    set_loop(asyncio.get_running_loop())

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(me.router)
app.include_router(categories.router)
app.include_router(products.router)
app.include_router(tiers.router)
app.include_router(customers.router)
app.include_router(ceilings.router)
app.include_router(approval_rules.router)
app.include_router(warehouses.router)
app.include_router(subscription_plans.router)
app.include_router(pairings.router)
app.include_router(settings_api.router)
app.include_router(quotations.router)
app.include_router(approvals.router)
app.include_router(fulfillment.router)
app.include_router(billing.router)
app.include_router(events.router)
app.include_router(audit.router)
