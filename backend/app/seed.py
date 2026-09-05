"""Idempotent seed script. Run with `python -m app.seed`."""

import random
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.core.security import hash_password
from app.engine.ceilings import resolve_ceiling
from app.engine.pricing import LineInput, price_quotation
from app.models.approval_rule import ApprovalRule
from app.models.base import Base, SessionLocal, engine
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

SEED_USERS = [
    ("admin@dealflow360.com", "Ada Admin", Role.ADMIN),
    ("rep@dealflow360.com", "Rita Rep", Role.SALES_REP),
    ("rep2@dealflow360.com", "Raj Rep2", Role.SALES_REP),
    ("rep3@dealflow360.com", "Priya Rep3", Role.SALES_REP),
    ("manager@dealflow360.com", "Marco Manager", Role.SALES_MANAGER),
    ("finance@dealflow360.com", "Fiona Finance", Role.FINANCE),
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
]

CUSTOMERS = [
    ("Acme Corp", "buyer@acmecorp.example", "Gold"),
    ("Beta Industries", "procurement@betaindustries.example", "Silver"),
    ("Gamma Retail", "purchasing@gammaretail.example", "Bronze"),
    ("Delta Manufacturing", "orders@deltamfg.example", "Gold"),
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
    total = 18
    forced_stalled = 4  # guarantees >= 3 quotations past the 10-day threshold, in a non-terminal state

    for i in range(total):
        rep = reps[i % len(reps)]
        # One rep discounts noticeably higher than the others -- useful anomaly-detector fodder in Phase 8.
        is_high_discount_rep = rep.email == "rep3@dealflow360.com"

        customer = random.choice(customers)
        ceilings = ceilings_by_tier[customer.tier_id]

        chosen_products = random.sample(products, random.randint(1, 3))
        engine_lines = []
        for product in chosen_products:
            qty = random.randint(1, 8)
            base_ceiling = int(ceilings.get(product.category_id, Decimal("10")))
            if is_high_discount_rep:
                discount = Decimal(random.randint(base_ceiling + 5, base_ceiling + 15))
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
        subscription_skus = {"SB-LIC-STD", "SB-LIC-PREM", "SB-SUP-BASIC"}
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

        # Customers
        customer_by_email: dict[str, Customer] = {}
        for name, email, tier_name in CUSTOMERS:
            customer = db.query(Customer).filter(Customer.email == email).first()
            if customer is None:
                customer = Customer(
                    id=uuid.uuid4(), name=name, email=email, tier_id=tier_by_name[tier_name].id, currency="INR"
                )
                db.add(customer)
                db.flush()
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

        # Independent of the quotation guard above, so it still backfills on a DB that already
        # had quotations seeded before this demo data existed.
        if db.query(Fulfillment).count() == 0:
            _seed_delivery_slippage_demo(db)

        db.commit()
        print("Seed complete. Password for all internal accounts:", SEED_PASSWORD)
    finally:
        db.close()


if __name__ == "__main__":
    seed()
