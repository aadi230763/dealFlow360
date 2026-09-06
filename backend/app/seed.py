"""Idempotent seed script. Run with `python -m app.seed` (add `--reset` to wipe and reseed)."""

import argparse
import random
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.api.billing import _generate_number, create_order_and_initial_invoices
from app.core.security import hash_password
from app.engine.ceilings import resolve_ceiling
from app.engine.pricing import LineInput, price_quotation
from app.models.approval_rule import ApprovalRule
from app.models.base import Base, SessionLocal, engine
from app.models.billing import CreditNote, Invoice, InvoiceStatus, InvoiceType, Order, Payment
from app.models.catalog import Category, Product
from app.models.customer import Customer, CustomerTier
from app.models.fulfillment import Fulfillment, FulfillmentAllocation, FulfillmentStatus
from app.models.pairing import ProductPairing
from app.models.pricing_config import CategoryTierCeiling
from app.models.quotation import LineType, Quotation, QuotationLine, QuotationStatus
from app.models.setting import SystemSetting
from app.models.subscription_plan import Interval, ProrationPolicy, SubscriptionPlan
from app.models.user import Role, User
from app.models.warehouse import StockLevel, Warehouse

import app.models.audit  # noqa: F401
import app.models.approval_request  # noqa: F401
import app.models.billing  # noqa: F401
import app.models.portal  # noqa: F401
import app.models.notification  # noqa: F401

SEED_USERS = [
    ("admin@dealflow360.com", "Ada Admin", Role.ADMIN),
    ("rep@dealflow360.com", "Rita Rep", Role.SALES_REP),
    ("rep2@dealflow360.com", "Raj Rep2", Role.SALES_REP),
    ("rep3@dealflow360.com", "Priya Rep3", Role.SALES_REP),
    ("manager@dealflow360.com", "Marco Manager", Role.SALES_MANAGER),
    ("finance@dealflow360.com", "Fiona Finance", Role.FINANCE),
    ("shipping@dealflow360.com", "Sam Shipping", Role.SHIPMENT_MANAGER),
]
SEED_PASSWORD = "password123"

CATEGORIES = [
    ("Hardware", Decimal("15")),
    ("Services", Decimal("10")),
    ("Subscriptions", Decimal("8")),
]

TIERS = [
    ("Bronze", 1, Decimal("5")),
    ("Silver", 2, Decimal("10")),
    ("Gold", 3, Decimal("15")),
]

# (tier_name, category_name, ceiling_pct) overrides for the full 3x3 matrix.
CEILING_MATRIX = [
    ("Bronze", "Hardware", Decimal("8")),
    ("Bronze", "Services", Decimal("5")),
    ("Bronze", "Subscriptions", Decimal("4")),
    ("Silver", "Hardware", Decimal("12")),
    ("Silver", "Services", Decimal("8")),
    ("Silver", "Subscriptions", Decimal("6")),
    ("Gold", "Hardware", Decimal("18")),
    ("Gold", "Services", Decimal("10")),
    ("Gold", "Subscriptions", Decimal("8")),
]

# (name, sku, category, unit_cost, list_price, is_promoted)
PRODUCTS = [
    ("Laptop Pro 15", "HW-LAP-15", "Hardware", Decimal("65000"), Decimal("90000"), False),
    ("Office Chair Ergo", "HW-CHR-ERG", "Hardware", Decimal("5000"), Decimal("8000"), False),
    ("Standing Desk", "HW-DSK-STD", "Hardware", Decimal("9000"), Decimal("15000"), False),
    ("Wireless Mouse", "HW-MOU-WL", "Hardware", Decimal("600"), Decimal("1200"), True),
    ("4K Monitor", "HW-MON-4K", "Hardware", Decimal("15000"), Decimal("22000"), False),
    ("Docking Station", "HW-DOCK-01", "Hardware", Decimal("3500"), Decimal("6000"), False),
    ("Onsite Setup Service", "SV-SETUP-01", "Services", Decimal("1500"), Decimal("5000"), False),
    ("Extended Onboarding", "SV-ONB-EXT", "Services", Decimal("3000"), Decimal("10000"), False),
    ("Priority Support Package", "SV-SUP-PRI", "Services", Decimal("4000"), Decimal("12000"), False),
    ("SaaS License Standard", "SB-LIC-STD", "Subscriptions", Decimal("1000"), Decimal("3000"), False),
    ("SaaS License Premium", "SB-LIC-PREM", "Subscriptions", Decimal("2000"), Decimal("6000"), True),
    ("Support Plan Basic", "SB-SUP-BASIC", "Subscriptions", Decimal("400"), Decimal("1500"), False),
    # Additional dummy catalog depth (Hardware)
    ("Mechanical Keyboard", "HW-KEY-MECH", "Hardware", Decimal("2200"), Decimal("4000"), False),
    ("Webcam HD", "HW-CAM-HD", "Hardware", Decimal("1200"), Decimal("2200"), False),
    ("Noise Cancelling Headset", "HW-HDS-NC", "Hardware", Decimal("3800"), Decimal("6500"), True),
    ("USB-C Hub", "HW-HUB-USBC", "Hardware", Decimal("900"), Decimal("1800"), False),
    ("Laptop Stand", "HW-STND-LAP", "Hardware", Decimal("700"), Decimal("1400"), False),
    ("External SSD 1TB", "HW-SSD-1TB", "Hardware", Decimal("4500"), Decimal("7500"), False),
    ("Conference Room Camera", "HW-CAM-CONF", "Hardware", Decimal("18000"), Decimal("28000"), False),
    ("Network Switch 24-Port", "HW-SW-24P", "Hardware", Decimal("12000"), Decimal("19000"), False),
    ("Wireless Access Point", "HW-WAP-01", "Hardware", Decimal("6000"), Decimal("10000"), False),
    ("Printer LaserJet", "HW-PRN-LSR", "Hardware", Decimal("14000"), Decimal("22000"), False),
    ("UPS Backup 1500VA", "HW-UPS-1500", "Hardware", Decimal("8000"), Decimal("13000"), False),
    ("Server Rack 12U", "HW-RACK-12U", "Hardware", Decimal("22000"), Decimal("34000"), False),
    # Additional dummy catalog depth (Services)
    ("Data Migration Service", "SV-MIG-DATA", "Services", Decimal("6000"), Decimal("18000"), False),
    ("Custom Integration Build", "SV-INT-CUST", "Services", Decimal("8000"), Decimal("25000"), False),
    ("Annual Health Check", "SV-HLTH-ANN", "Services", Decimal("2500"), Decimal("8000"), False),
    ("Dedicated Account Manager", "SV-AM-DED", "Services", Decimal("5000"), Decimal("15000"), True),
    ("Security Audit", "SV-SEC-AUD", "Services", Decimal("7000"), Decimal("20000"), False),
    ("Staff Training Workshop", "SV-TRN-WKS", "Services", Decimal("3500"), Decimal("11000"), False),
    # Additional dummy catalog depth (Subscriptions)
    ("SaaS License Enterprise", "SB-LIC-ENT", "Subscriptions", Decimal("3500"), Decimal("9500"), True),
    ("Support Plan Premium", "SB-SUP-PREM", "Subscriptions", Decimal("900"), Decimal("2800"), False),
    ("Analytics Add-on", "SB-ADDON-ANLY", "Subscriptions", Decimal("600"), Decimal("2000"), False),
    ("API Access Plan", "SB-API-PLAN", "Subscriptions", Decimal("500"), Decimal("1800"), False),
]

CUSTOMERS = [
    ("Acme Corp", "buyer@acmecorp.example", "Gold"),
    ("Beta Industries", "procurement@betaindustries.example", "Silver"),
    ("Gamma Retail", "purchasing@gammaretail.example", "Bronze"),
    ("Delta Manufacturing", "orders@deltamfg.example", "Gold"),
    ("Epsilon Logistics", "orders@epsilonlogistics.example", "Silver"),
    ("Zenith Pharma", "purchasing@zenithpharma.example", "Gold"),
    ("Orion Textiles", "buyer@oriontextiles.example", "Bronze"),
    ("Nimbus Cloud Services", "procurement@nimbuscloud.example", "Gold"),
    ("Cascade Foods", "orders@cascadefoods.example", "Silver"),
    ("Ironclad Security", "buyer@ironcladsecurity.example", "Bronze"),
    ("Vertex Motors", "purchasing@vertexmotors.example", "Gold"),
    ("Bluewave Media", "procurement@bluewavemedia.example", "Silver"),
    ("Summit Construction", "orders@summitconstruction.example", "Bronze"),
    ("Halcyon Energy", "buyer@halcyonenergy.example", "Gold"),
    ("Meridian Health", "purchasing@meridianhealth.example", "Silver"),
    ("Redwood Realty", "procurement@redwoodrealty.example", "Bronze"),
    ("Solstice Airlines", "orders@solsticeair.example", "Gold"),
    ("Anchor Financial", "buyer@anchorfinancial.example", "Silver"),
    ("Pinecrest Education", "purchasing@pinecresteducation.example", "Bronze"),
    ("Lumen Telecom", "procurement@lumentelecom.example", "Gold"),
    ("Coral Reef Hospitality", "orders@coralreefhospitality.example", "Silver"),
    ("Granite Insurance", "buyer@graniteinsurance.example", "Bronze"),
    ("Sable Automotive", "purchasing@sableautomotive.example", "Gold"),
    ("Ember Robotics", "procurement@emberrobotics.example", "Silver"),
    ("Fjord Shipping", "orders@fjordshipping.example", "Bronze"),
    ("Skyline Retailers", "buyer@skylineretailers.example", "Gold"),
    ("Terra Agriculture", "purchasing@terraagriculture.example", "Silver"),
    ("Marble Legal Group", "procurement@marblelegal.example", "Bronze"),
    ("Quartz Mining Co", "orders@quartzmining.example", "Gold"),
    ("Willow Consulting", "buyer@willowconsulting.example", "Silver"),
    ("Ashgrove Manufacturing", "purchasing@ashgrovemfg.example", "Bronze"),
    ("Cobalt Defense Systems", "procurement@cobaltdefense.example", "Gold"),
    ("Driftwood Media House", "orders@driftwoodmedia.example", "Silver"),
    ("Everstone Capital", "buyer@everstonecapital.example", "Bronze"),
]

WAREHOUSES = [
    ("Main Warehouse", "MAIN", Decimal("1.0")),
    ("East Depot", "EAST", Decimal("1.3")),
]

SUBSCRIPTION_PLANS = [
    ("Monthly", Interval.MONTHLY, 1, ProrationPolicy.DAILY_PRORATE, "CREDIT_REMAINING"),
    ("Quarterly", Interval.QUARTERLY, 1, ProrationPolicy.DAILY_PRORATE, "CREDIT_REMAINING"),
    ("Yearly", Interval.YEARLY, 1, ProrationPolicy.FULL_PERIOD, "NO_REFUND"),
]

# (product_sku, suggested_sku, co_purchase_score, min_margin_pct)
PAIRINGS = [
    ("HW-LAP-15", "HW-MOU-WL", Decimal("0.80"), Decimal("20")),
    ("HW-LAP-15", "HW-DOCK-01", Decimal("0.70"), Decimal("20")),
    ("HW-LAP-15", "HW-MON-4K", Decimal("0.60"), Decimal("15")),
    ("HW-CHR-ERG", "HW-DSK-STD", Decimal("0.75"), Decimal("15")),
    ("HW-DSK-STD", "HW-CHR-ERG", Decimal("0.50"), Decimal("15")),
    ("HW-MON-4K", "HW-DOCK-01", Decimal("0.65"), Decimal("15")),
    ("SB-LIC-STD", "SB-SUP-BASIC", Decimal("0.55"), Decimal("10")),
    ("SV-SETUP-01", "SV-ONB-EXT", Decimal("0.60"), Decimal("10")),
    # Every product below previously had zero coverage as an origin -- adding a laptop was
    # the only way to ever see a suggestion. Rounds out the mesh so any seeded product can
    # surface a relevant cross-sell, not just Hardware.
    ("HW-DOCK-01", "HW-MON-4K", Decimal("0.50"), Decimal("15")),
    ("HW-DOCK-01", "HW-MOU-WL", Decimal("0.40"), Decimal("15")),
    ("HW-MOU-WL", "HW-DOCK-01", Decimal("0.40"), Decimal("15")),
    ("SB-LIC-PREM", "SV-SUP-PRI", Decimal("0.65"), Decimal("10")),
    ("SB-SUP-BASIC", "SB-LIC-STD", Decimal("0.45"), Decimal("10")),
    ("SV-ONB-EXT", "SV-SUP-PRI", Decimal("0.55"), Decimal("10")),
    ("SV-SUP-PRI", "SV-ONB-EXT", Decimal("0.40"), Decimal("10")),
]

SYSTEM_SETTINGS = {
    "stalled_deal_day_threshold": 10,
    "anomaly_zscore_threshold": 2.0,
    "currency_symbol": "₹",
    "fulfillment_base_shipment_cost": 10,
    "invoice_due_days": 15,
    "portal_token_expires_days": 14,
    "fulfillment_promise_days": 5,
}

NON_TERMINAL_STATUSES = [
    QuotationStatus.DRAFT,
    QuotationStatus.PENDING_APPROVAL,
    QuotationStatus.APPROVED,
    QuotationStatus.SENT,
    QuotationStatus.UNDER_NEGOTIATION,
    QuotationStatus.FULFILLING,
]
STATUS_POOL = NON_TERMINAL_STATUSES + [
    QuotationStatus.CONFIRMED,
    QuotationStatus.INVOICED,
    QuotationStatus.REJECTED,
    QuotationStatus.CANCELLED,
]


def _resolve_ceilings_for_tier(db, tier, category_by_name: dict[str, Category]) -> dict[uuid.UUID, Decimal]:
    overrides = {
        o.category_id: o.ceiling_pct
        for o in db.query(CategoryTierCeiling).filter(CategoryTierCeiling.tier_id == tier.id).all()
    }
    return {
        cat.id: resolve_ceiling(
            tier_base=tier.base_discount_ceiling_pct,
            category_default=cat.default_discount_ceiling_pct,
            override=overrides.get(cat.id),
        )
        for cat in category_by_name.values()
    }


def _seed_historical_quotations(
    db,
    product_by_sku: dict[str, Product],
    category_by_name: dict[str, Category],
    tier_by_name: dict[str, CustomerTier],
    customer_by_email: dict[str, Customer],
) -> None:
    """Real quotations, priced through the same engine the API uses -- never faked numbers,
    even for demo history. Spread across reps/customers/dates/statuses so the pipeline board,
    the stalled-deal panel, and (later) the anomaly detector all have something to show."""

    random.seed(42)
    reps = db.query(User).filter(User.role == Role.SALES_REP).order_by(User.email).all()
    customers = list(customer_by_email.values())
    products = list(product_by_sku.values())
    ceilings_by_tier = {
        tier.id: _resolve_ceilings_for_tier(db, tier, category_by_name) for tier in tier_by_name.values()
    }

    now = datetime.now(timezone.utc)
    total = 150
    forced_stalled = 15  # guarantees several quotations past the 10-day threshold, in a non-terminal state

    # One rep gets one clearly outlying quote against their own otherwise-normal history --
    # this is what the discount-anomaly detector (Phase 8) needs to have something to flag
    # right after a fresh seed, without waiting for a live demo action to create it. A rep
    # discounting high on *every* quote would just raise their own baseline and never trip a
    # z-score against themselves, so only the last of their quotes is pushed far out.
    outlier_rep_email = "rep3@dealflow360.com"
    outlier_rep_quote_count = sum(1 for i in range(total) if reps[i % len(reps)].email == outlier_rep_email)
    seen_for_outlier_rep = 0

    for i in range(total):
        rep = reps[i % len(reps)]
        is_outlier_rep = rep.email == outlier_rep_email
        if is_outlier_rep:
            seen_for_outlier_rep += 1
        is_outlier_quote = is_outlier_rep and seen_for_outlier_rep == outlier_rep_quote_count

        customer = random.choice(customers)
        ceilings = ceilings_by_tier[customer.tier_id]

        chosen_products = random.sample(products, random.randint(1, 3))
        engine_lines = []
        for product in chosen_products:
            qty = random.randint(1, 8)
            base_ceiling = int(ceilings.get(product.category_id, Decimal("10")))
            if is_outlier_quote:
                discount = Decimal(random.randint(base_ceiling + 20, base_ceiling + 30))
            else:
                discount = Decimal(random.randint(0, base_ceiling + 2))
            engine_lines.append(
                LineInput(
                    product_id=product.id,
                    category_id=product.category_id,
                    line_type="ONE_TIME",
                    qty=qty,
                    unit_price=product.list_price,
                    unit_cost=product.unit_cost,
                    tax_pct=product.tax_pct,
                    discount_pct=discount,
                    product_name=product.name,
                )
            )

        pricing = price_quotation(engine_lines, ceilings)

        if i < forced_stalled:
            status = random.choice(NON_TERMINAL_STATUSES)
            age_days = random.randint(11, 25)
        else:
            status = random.choice(STATUS_POOL)
            age_days = random.randint(0, 20)

        created_at = now - timedelta(days=age_days, hours=random.randint(0, 23))

        quotation = Quotation(
            id=uuid.uuid4(),
            number=f"Q-{db.query(Quotation).count() + 1:04d}",
            customer_id=customer.id,
            owner_user_id=rep.id,
            status=status,
            currency=customer.currency,
            subtotal=pricing.subtotal,
            discount_total=pricing.discount_total,
            tax_total=pricing.tax_total,
            grand_total=pricing.grand_total,
            margin_amount=pricing.margin_amount,
            margin_pct=pricing.margin_pct,
            created_at=created_at,
            updated_at=created_at,
            last_activity_at=created_at,
        )
        db.add(quotation)
        db.flush()

        for line_in, priced in zip(engine_lines, pricing.lines):
            db.add(
                QuotationLine(
                    id=uuid.uuid4(),
                    quotation_id=quotation.id,
                    product_id=line_in.product_id,
                    variant_id=None,
                    line_type=LineType.ONE_TIME,
                    qty=line_in.qty,
                    unit_price=priced.unit_price,
                    unit_cost=priced.unit_cost,
                    discount_pct=line_in.discount_pct,
                    computed={
                        "gross": str(priced.gross),
                        "discount_amount": str(priced.discount_amount),
                        "net": str(priced.net),
                        "tax_amount": str(priced.tax_amount),
                        "cost_total": str(priced.cost_total),
                        "margin_amount": str(priced.margin_amount),
                        "margin_pct": str(priced.margin_pct),
                        "ceiling_pct": str(priced.ceiling_pct),
                        "overage_pct": str(priced.overage_pct),
                        "weight": str(priced.weight),
                    },
                )
            )
        db.flush()


def _seed_billing_demo_data(
    db,
    product_by_sku: dict[str, Product],
    customer_by_email: dict[str, Customer],
) -> None:
    """Confirmed orders with real Orders/BillingSchedules/Invoices/Payments, built through
    the same create_order_and_initial_invoices() the internal 'Confirm Order' button and the
    portal auto-confirm path use -- so demo subscriptions and invoices are structured exactly
    like a live one, not faked numbers. Without this, the Subscriptions and Invoices screens
    are empty on a fresh seed even though the pipeline board has plenty of quotations."""
    random.seed(43)
    reps = db.query(User).filter(User.role == Role.SALES_REP).order_by(User.email).all()
    customers = list(customer_by_email.values())
    plans = db.query(SubscriptionPlan).order_by(SubscriptionPlan.name).all()

    subscription_skus = [sku for sku, p in product_by_sku.items() if p.is_subscription]
    one_time_skus = [sku for sku in product_by_sku if sku not in subscription_skus]

    now = datetime.now(timezone.utc)
    total = 20

    for i in range(total):
        rep = reps[i % len(reps)]
        customer = random.choice(customers)
        plan = plans[i % len(plans)]
        sub_product = product_by_sku[subscription_skus[i % len(subscription_skus)]]
        one_time_product = product_by_sku[random.choice(one_time_skus)]

        engine_lines = [
            LineInput(
                product_id=sub_product.id,
                category_id=sub_product.category_id,
                line_type="RECURRING",
                qty=random.randint(1, 5),
                unit_price=sub_product.list_price,
                unit_cost=sub_product.unit_cost,
                tax_pct=sub_product.tax_pct,
                discount_pct=Decimal(random.randint(0, 5)),
                product_name=sub_product.name,
            ),
            LineInput(
                product_id=one_time_product.id,
                category_id=one_time_product.category_id,
                line_type="ONE_TIME",
                qty=random.randint(1, 3),
                unit_price=one_time_product.list_price,
                unit_cost=one_time_product.unit_cost,
                tax_pct=one_time_product.tax_pct,
                discount_pct=Decimal(random.randint(0, 5)),
                product_name=one_time_product.name,
            ),
        ]
        # These are already-confirmed historical orders, not quotations going through
        # approval, so ceilings are left wide open rather than resolved per tier/category.
        wide_open = {sub_product.category_id: Decimal("100"), one_time_product.category_id: Decimal("100")}
        pricing = price_quotation(engine_lines, wide_open)

        status_choice = random.choice(
            [QuotationStatus.CONFIRMED, QuotationStatus.FULFILLING, QuotationStatus.INVOICED]
        )
        created_at = now - timedelta(days=random.randint(30, 200))

        quotation = Quotation(
            id=uuid.uuid4(),
            number=f"Q-{db.query(Quotation).count() + 1:04d}",
            customer_id=customer.id,
            owner_user_id=rep.id,
            status=status_choice,
            currency=customer.currency,
            subtotal=pricing.subtotal,
            discount_total=pricing.discount_total,
            tax_total=pricing.tax_total,
            grand_total=pricing.grand_total,
            margin_amount=pricing.margin_amount,
            margin_pct=pricing.margin_pct,
            created_at=created_at,
            updated_at=created_at,
            last_activity_at=created_at,
        )
        db.add(quotation)
        db.flush()

        for line_in, priced in zip(engine_lines, pricing.lines):
            db.add(
                QuotationLine(
                    id=uuid.uuid4(),
                    quotation_id=quotation.id,
                    product_id=line_in.product_id,
                    variant_id=None,
                    line_type=LineType.RECURRING if line_in.line_type == "RECURRING" else LineType.ONE_TIME,
                    qty=line_in.qty,
                    unit_price=priced.unit_price,
                    unit_cost=priced.unit_cost,
                    discount_pct=line_in.discount_pct,
                    subscription_plan_id=plan.id if line_in.line_type == "RECURRING" else None,
                    start_date=created_at.date() if line_in.line_type == "RECURRING" else None,
                    computed={
                        "gross": str(priced.gross),
                        "discount_amount": str(priced.discount_amount),
                        "net": str(priced.net),
                        "tax_amount": str(priced.tax_amount),
                        "cost_total": str(priced.cost_total),
                        "margin_amount": str(priced.margin_amount),
                        "margin_pct": str(priced.margin_pct),
                        "ceiling_pct": str(priced.ceiling_pct),
                        "overage_pct": str(priced.overage_pct),
                        "weight": str(priced.weight),
                    },
                )
            )
        db.flush()
        db.refresh(quotation, attribute_names=["lines"])

        # Reuses the real order-confirmation path: creates the Order, a BillingSchedule for
        # the recurring line, and its first recurring Invoice -- identical to what happens
        # when a rep clicks "Confirm Order" on an approved quotation.
        order = create_order_and_initial_invoices(db, quotation, None)

        # The one-time line has no fulfillment shipment event to hang an invoice off in a
        # seed script (unlike the live invoice_shipment() path), so it's invoiced directly.
        one_time_line = next(l for l in quotation.lines if l.line_type == LineType.ONE_TIME)
        amount = Decimal(one_time_line.computed["net"])
        tax = Decimal(one_time_line.computed["tax_amount"])
        invoice = Invoice(
            id=uuid.uuid4(),
            order_id=order.id,
            number=_generate_number(db, Invoice, "INV"),
            type=InvoiceType.ONE_TIME,
            amount=amount,
            tax=tax,
            status=InvoiceStatus.ISSUED,
            issue_date=created_at.date(),
            due_date=created_at.date() + timedelta(days=15),
            created_at=created_at,
        )
        db.add(invoice)
        db.flush()

        # Spread outcomes across paid/partial/credited/unpaid so the Invoices screen shows
        # every status, not a wall of "ISSUED".
        outcome = i % 4
        if outcome == 0:
            invoice.status = InvoiceStatus.PAID
            db.add(
                Payment(
                    id=uuid.uuid4(),
                    invoice_id=invoice.id,
                    amount=invoice.amount + invoice.tax,
                    method="BANK_TRANSFER",
                    reference=f"TXN-{1000 + i}",
                    received_at=created_at + timedelta(days=5),
                )
            )
        elif outcome == 1:
            invoice.status = InvoiceStatus.PARTIAL
            db.add(
                Payment(
                    id=uuid.uuid4(),
                    invoice_id=invoice.id,
                    amount=(invoice.amount + invoice.tax) / 2,
                    method="CARD",
                    reference=f"TXN-{2000 + i}",
                    received_at=created_at + timedelta(days=3),
                )
            )
        elif outcome == 2:
            invoice.status = InvoiceStatus.CREDITED
            db.add(
                CreditNote(
                    id=uuid.uuid4(),
                    invoice_id=invoice.id,
                    amount=invoice.amount,
                    reason="Customer-reported issue, partial credit",
                    created_at=created_at + timedelta(days=10),
                )
            )
        # outcome == 3: left ISSUED / unpaid
        db.flush()


def _seed_delivery_slippage_demo(db) -> None:
    """Backdates 2 fulfillments with an open backorder past the promise window, so the
    Delivery Slippage panel (Phase 8) has something to show without waiting for real time
    to pass. Picks from quotations that already have lines and aren't terminal-lost."""
    candidates = (
        db.query(Quotation)
        .filter(Quotation.status.in_([QuotationStatus.CONFIRMED, QuotationStatus.FULFILLING, QuotationStatus.APPROVED]))
        .order_by(Quotation.created_at)
        .limit(2)
        .all()
    )
    for quotation in candidates:
        if not quotation.lines:
            continue
        line = quotation.lines[0]
        backdated = quotation.created_at
        fulfillment = Fulfillment(
            id=uuid.uuid4(),
            quotation_id=quotation.id,
            status=FulfillmentStatus.PLANNED,
            total_shipments=1,
            estimated_cost=Decimal("10"),
            is_manual_override=False,
            created_at=backdated,
        )
        db.add(fulfillment)
        db.flush()
        db.add(
            FulfillmentAllocation(
                id=uuid.uuid4(),
                fulfillment_id=fulfillment.id,
                quotation_line_id=line.id,
                warehouse_id=None,
                qty=max(1, line.qty // 2),
                is_backorder=True,
            )
        )
    db.flush()


def reset() -> None:
    """Drops every table and recreates the schema, so `seed()` starts from a blank database.
    There is no migration tool in this project (create_all is the only schema manager), so a
    full drop/create is the only reliable way to guarantee demo-ready state on demand."""
    Base.metadata.drop_all(bind=engine)


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Users
        for email, name, role in SEED_USERS:
            if db.query(User).filter(User.email == email).first():
                continue
            db.add(User(id=uuid.uuid4(), email=email, password_hash=hash_password(SEED_PASSWORD), name=name, role=role))
        db.flush()

        # Categories
        category_by_name: dict[str, Category] = {}
        for name, default_ceiling in CATEGORIES:
            category = db.query(Category).filter(Category.name == name).first()
            if category is None:
                category = Category(id=uuid.uuid4(), name=name, default_discount_ceiling_pct=default_ceiling)
                db.add(category)
                db.flush()
            category_by_name[name] = category

        # Tiers
        tier_by_name: dict[str, CustomerTier] = {}
        for name, rank, base_ceiling in TIERS:
            tier = db.query(CustomerTier).filter(CustomerTier.name == name).first()
            if tier is None:
                tier = CustomerTier(id=uuid.uuid4(), name=name, rank=rank, base_discount_ceiling_pct=base_ceiling)
                db.add(tier)
                db.flush()
            tier_by_name[name] = tier

        # Ceiling matrix overrides
        for tier_name, category_name, ceiling_pct in CEILING_MATRIX:
            tier = tier_by_name[tier_name]
            category = category_by_name[category_name]
            existing = (
                db.query(CategoryTierCeiling)
                .filter(CategoryTierCeiling.tier_id == tier.id, CategoryTierCeiling.category_id == category.id)
                .first()
            )
            if existing is None:
                db.add(
                    CategoryTierCeiling(
                        id=uuid.uuid4(), tier_id=tier.id, category_id=category.id, ceiling_pct=ceiling_pct
                    )
                )
        db.flush()

        # Products
        # Any product in the Subscriptions category is subscription-billed -- derived from
        # the category rather than a hardcoded SKU list, so new SKUs added to PRODUCTS don't
        # need a second place updated to be picked up correctly.
        subscription_skus = {sku for _, sku, category_name, *_ in PRODUCTS if category_name == "Subscriptions"}
        product_by_sku: dict[str, Product] = {}
        for name, sku, category_name, unit_cost, list_price, is_promoted in PRODUCTS:
            product = db.query(Product).filter(Product.sku == sku).first()
            if product is None:
                product = Product(
                    id=uuid.uuid4(),
                    name=name,
                    sku=sku,
                    category_id=category_by_name[category_name].id,
                    unit="each",
                    list_price=list_price,
                    unit_cost=unit_cost,
                    tax_pct=Decimal("18"),
                    is_promoted=is_promoted,
                    is_active=True,
                )
                db.add(product)
                db.flush()
            # Idempotent patch for fields added after initial seeding.
            product.is_subscription = sku in subscription_skus
            product.recurring_interval = "MONTHLY" if sku in subscription_skus else None
            product_by_sku[sku] = product

        # Customers -- each gets an owning rep, round-robin, so the account-ownership
        # warning (two reps quoting the same customer) has something real to demo on a
        # fresh seed rather than every customer starting unassigned.
        reps_for_ownership = db.query(User).filter(User.role == Role.SALES_REP).order_by(User.email).all()
        customer_by_email: dict[str, Customer] = {}
        for i, (name, email, tier_name) in enumerate(CUSTOMERS):
            customer = db.query(Customer).filter(Customer.email == email).first()
            owner_id = reps_for_ownership[i % len(reps_for_ownership)].id if reps_for_ownership else None
            if customer is None:
                customer = Customer(
                    id=uuid.uuid4(),
                    name=name,
                    email=email,
                    tier_id=tier_by_name[tier_name].id,
                    currency="INR",
                    owner_user_id=owner_id,
                )
                db.add(customer)
                db.flush()
            elif customer.owner_user_id is None:
                customer.owner_user_id = owner_id
            customer_by_email[email] = customer

        # Warehouses
        warehouse_by_code: dict[str, Warehouse] = {}
        for name, code, weight in WAREHOUSES:
            warehouse = db.query(Warehouse).filter(Warehouse.code == code).first()
            if warehouse is None:
                warehouse = Warehouse(id=uuid.uuid4(), name=name, code=code, shipping_cost_weight=weight)
                db.add(warehouse)
                db.flush()
            warehouse_by_code[code] = warehouse

        # Stock: split Laptop Pro 15 across both warehouses (12 + 8, neither covers a 20-unit order alone);
        # everything else fully stocked in Main only.
        main = warehouse_by_code["MAIN"]
        east = warehouse_by_code["EAST"]

        def upsert_stock(warehouse: Warehouse, sku: str, on_hand: int, reorder_point: int = 5) -> None:
            product = product_by_sku[sku]
            existing = (
                db.query(StockLevel)
                .filter(StockLevel.warehouse_id == warehouse.id, StockLevel.product_id == product.id)
                .first()
            )
            if existing is None:
                db.add(
                    StockLevel(
                        id=uuid.uuid4(),
                        warehouse_id=warehouse.id,
                        product_id=product.id,
                        on_hand=on_hand,
                        reserved=0,
                        reorder_point=reorder_point,
                    )
                )

        upsert_stock(main, "HW-LAP-15", 12)
        upsert_stock(east, "HW-LAP-15", 8)
        for sku in product_by_sku:
            if sku == "HW-LAP-15":
                continue
            upsert_stock(main, sku, 100)
        db.flush()

        # Subscription plans
        for name, interval, interval_count, proration_policy, cancellation_policy in SUBSCRIPTION_PLANS:
            if db.query(SubscriptionPlan).filter(SubscriptionPlan.name == name).first():
                continue
            db.add(
                SubscriptionPlan(
                    id=uuid.uuid4(),
                    name=name,
                    interval=interval,
                    interval_count=interval_count,
                    proration_policy=proration_policy,
                    cancellation_policy=cancellation_policy,
                )
            )
        db.flush()

        # Product pairings
        for product_sku, suggested_sku, score, min_margin in PAIRINGS:
            product = product_by_sku[product_sku]
            suggested = product_by_sku[suggested_sku]
            existing = (
                db.query(ProductPairing)
                .filter(
                    ProductPairing.product_id == product.id,
                    ProductPairing.suggested_product_id == suggested.id,
                )
                .first()
            )
            if existing is None:
                db.add(
                    ProductPairing(
                        id=uuid.uuid4(),
                        product_id=product.id,
                        suggested_product_id=suggested.id,
                        co_purchase_score=score,
                        min_margin_pct=min_margin,
                    )
                )
        db.flush()

        # Approval rules
        if not db.query(ApprovalRule).filter(ApprovalRule.name == "Manager Review").first():
            db.add(
                ApprovalRule(
                    id=uuid.uuid4(),
                    name="Manager Review",
                    level=1,
                    min_blended=Decimal("2"),
                    min_peak=Decimal("5"),
                    min_erosion_amount=None,
                    required_roles=[Role.SALES_MANAGER.value],
                    sequence=1,
                    is_active=True,
                )
            )
        if not db.query(ApprovalRule).filter(ApprovalRule.name == "Finance Review").first():
            db.add(
                ApprovalRule(
                    id=uuid.uuid4(),
                    name="Finance Review",
                    level=2,
                    min_blended=Decimal("5"),
                    min_peak=Decimal("8"),
                    min_erosion_amount=Decimal("50000"),
                    required_roles=[Role.FINANCE.value],
                    sequence=2,
                    is_active=True,
                )
            )
        db.flush()

        # System settings
        for key, value in SYSTEM_SETTINGS.items():
            if db.get(SystemSetting, key) is None:
                db.add(SystemSetting(key=key, value=value))
        db.flush()

        # Historical quotations: only seed once, so re-running never inflates the pipeline.
        if db.query(Quotation).count() == 0:
            _seed_historical_quotations(db, product_by_sku, category_by_name, tier_by_name, customer_by_email)
            db.flush()

        # Confirmed orders with subscriptions/invoices/payments -- separate guard (on Order,
        # not Quotation) so it still backfills on a DB that already had quotations seeded
        # before this demo data existed.
        if db.query(Order).count() == 0:
            _seed_billing_demo_data(db, product_by_sku, customer_by_email)
            db.flush()

        # Independent of the quotation guard above, so it still backfills on a DB that already
        # had quotations seeded before this demo data existed.
        if db.query(Fulfillment).count() == 0:
            _seed_delivery_slippage_demo(db)

        db.commit()
        print("Seed complete. Password for all internal accounts:", SEED_PASSWORD)
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Drop all tables before seeding")
    args = parser.parse_args()
    if args.reset:
        reset()
    seed()
