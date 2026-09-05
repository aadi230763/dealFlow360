import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.audit import log_event
from app.core.deps import get_current_user, get_db
from app.core.events import publish
from app.engine.billing import (
    ProrationResult,
    build_schedule,
    cancel_credit,
    invoice_amount_for_qty,
    prorate,
    subtract_period,
)
from app.models.billing import (
    BillingSchedule,
    BillingScheduleStatus,
    CreditNote,
    Invoice,
    InvoiceStatus,
    InvoiceType,
    Order,
    OrderStatus,
    Payment,
)
from app.models.catalog import Product
from app.models.customer import Customer
from app.models.fulfillment import FulfillmentAllocation
from app.models.quotation import LineType, Quotation, QuotationLine, QuotationStatus
from app.models.setting import SystemSetting
from app.models.subscription_plan import SubscriptionPlan
from app.models.user import User
from app.schemas.billing import (
    InvoiceDetailOut,
    InvoiceListItem,
    OneTimeLineOut,
    PaymentCreate,
    PaymentOut,
    PeriodOccurrenceOut,
    ProrationPreviewOut,
    SubscriptionChangeRequest,
    SubscriptionDetailOut,
    SubscriptionListItem,
)
from app.schemas.quotation import QuotationOut

router = APIRouter(tags=["billing"])


def _setting_int(db: Session, key: str, default: int) -> int:
    setting = db.get(SystemSetting, key)
    return int(setting.value) if setting is not None else default


def _generate_number(db: Session, model, prefix: str) -> str:
    count = db.query(model).count()
    return f"{prefix}-{count + 1:04d}"


def create_order_and_initial_invoices(db: Session, quotation: Quotation, user: User | None) -> Order:
    """Shared by the internal 'Confirm Order' button and the customer portal's auto-confirm
    path (Phase 7) -- both need the exact same Order/recurring-invoice creation, not two
    copies that can drift. Does not touch quotation.status; the caller decides that (the
    portal path sets APPROVED first so `ensure_fulfillment_planned` fires consistently)."""
    order = Order(
        id=uuid.uuid4(),
        quotation_id=quotation.id,
        number=_generate_number(db, Order, "ORD"),
        status=OrderStatus.CONFIRMED,
    )
    db.add(order)
    db.flush()

    due_days = _setting_int(db, "invoice_due_days", 15)
    today = date.today()
    schedules_created = []

    for line in quotation.lines:
        if line.line_type != LineType.RECURRING or line.subscription_plan_id is None:
            continue
        plan = db.get(SubscriptionPlan, line.subscription_plan_id)
        if plan is None:
            continue
        amount = Decimal(line.computed.get("net", "0"))
        tax = Decimal(line.computed.get("tax_amount", "0"))
        start = line.start_date or today
        built = build_schedule(start, plan.interval, plan.interval_count, amount)

        schedule = BillingSchedule(
            id=uuid.uuid4(),
            order_id=order.id,
            quotation_line_id=line.id,
            plan_id=plan.id,
            next_billing_date=built.next_billing_date,
            interval=plan.interval,
            interval_count=plan.interval_count,
            qty=line.qty,
            amount=amount,
            status=BillingScheduleStatus.ACTIVE,
        )
        db.add(schedule)

        db.add(
            Invoice(
                id=uuid.uuid4(),
                order_id=order.id,
                number=_generate_number(db, Invoice, "INV"),
                type=InvoiceType.RECURRING,
                amount=amount,
                tax=tax,
                status=InvoiceStatus.ISSUED,
                issue_date=built.first_period.period_start,
                due_date=built.first_period.period_start + timedelta(days=due_days),
                period_start=built.first_period.period_start,
                period_end=built.first_period.period_end,
            )
        )
        db.flush()
        schedules_created.append(schedule.id)

    log_event(
        db,
        entity_type="order",
        entity_id=str(order.id),
        action="confirm",
        actor=user,
        payload={"quotation_id": str(quotation.id), "schedules_created": [str(s) for s in schedules_created]},
    )
    return order


@router.post("/api/quotations/{quotation_id}/confirm", response_model=QuotationOut)
def confirm_quotation(
    quotation_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Quotation:
    quotation = db.get(Quotation, quotation_id)
    if quotation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quotation not found")
    if quotation.status != QuotationStatus.APPROVED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only an approved quotation can be confirmed")

    order = create_order_and_initial_invoices(db, quotation, user)

    quotation.status = QuotationStatus.CONFIRMED
    quotation.last_activity_at = datetime.now(timezone.utc)
    db.flush()
    db.commit()
    db.refresh(quotation)
    publish({"type": "quotation_confirmed", "quotation_id": str(quotation.id), "order_id": str(order.id)})
    return quotation


def invoice_shipment(db: Session, allocation: FulfillmentAllocation, user: User | None) -> Invoice | None:
    """Called from the ship endpoint (Phase 5's `ship_allocation`). No-op if the quotation
    hasn't been confirmed yet -- an Order is required before anything can be invoiced."""
    line = db.get(QuotationLine, allocation.quotation_line_id)
    if line is None:
        return None
    quotation = db.get(Quotation, line.quotation_id)
    if quotation is None:
        return None
    order = db.query(Order).filter(Order.quotation_id == quotation.id).first()
    if order is None:
        return None
    if line.line_type != LineType.ONE_TIME:
        return None

    line_net = Decimal(line.computed.get("net", "0"))
    line_tax = Decimal(line.computed.get("tax_amount", "0"))
    amount, tax = invoice_amount_for_qty(line_net, line_tax, line.qty, allocation.qty)
    if amount <= 0:
        return None

    due_days = _setting_int(db, "invoice_due_days", 15)
    today = date.today()
    invoice = Invoice(
        id=uuid.uuid4(),
        order_id=order.id,
        number=_generate_number(db, Invoice, "INV"),
        type=InvoiceType.ONE_TIME,
        amount=amount,
        tax=tax,
        status=InvoiceStatus.ISSUED,
        issue_date=today,
        due_date=today + timedelta(days=due_days),
    )
    db.add(invoice)
    db.flush()
    log_event(
        db,
        entity_type="invoice",
        entity_id=str(invoice.id),
        action="invoice_shipment",
        actor=user,
        payload={"order_id": str(order.id), "allocation_id": str(allocation.id), "qty": allocation.qty, "amount": str(amount)},
    )
    publish({"type": "invoice_issued", "invoice_id": str(invoice.id), "order_id": str(order.id)})
    return invoice


@router.get("/api/subscriptions", response_model=list[SubscriptionListItem])
def list_subscriptions(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[SubscriptionListItem]:
    schedules = db.query(BillingSchedule).order_by(BillingSchedule.next_billing_date).all()
    if not schedules:
        return []
    order_ids = {s.order_id for s in schedules}
    orders = {o.id: o for o in db.query(Order).filter(Order.id.in_(order_ids)).all()}
    quotation_ids = {o.quotation_id for o in orders.values()}
    quotations = {q.id: q for q in db.query(Quotation).filter(Quotation.id.in_(quotation_ids)).all()}
    customer_ids = {q.customer_id for q in quotations.values()}
    customers = {c.id: c for c in db.query(Customer).filter(Customer.id.in_(customer_ids)).all()}
    plan_ids = {s.plan_id for s in schedules}
    plans = {p.id: p for p in db.query(SubscriptionPlan).filter(SubscriptionPlan.id.in_(plan_ids)).all()}

    items = []
    for s in schedules:
        order = orders.get(s.order_id)
        quotation = quotations.get(order.quotation_id) if order else None
        customer = customers.get(quotation.customer_id) if quotation else None
        plan = plans.get(s.plan_id)
        items.append(
            SubscriptionListItem(
                schedule_id=s.id,
                customer_name=customer.name if customer else "—",
                plan_name=plan.name if plan else "—",
                interval=plan.interval if plan else s.interval,
                next_billing_date=s.next_billing_date,
                status=s.status,
            )
        )
    return items


def _schedule_or_404(db: Session, schedule_id: uuid.UUID) -> BillingSchedule:
    schedule = db.get(BillingSchedule, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return schedule


@router.get("/api/subscriptions/{schedule_id}", response_model=SubscriptionDetailOut)
def get_subscription(
    schedule_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> SubscriptionDetailOut:
    schedule = _schedule_or_404(db, schedule_id)
    order = db.get(Order, schedule.order_id)
    quotation = db.get(Quotation, order.quotation_id)
    customer = db.get(Customer, quotation.customer_id)
    plan = db.get(SubscriptionPlan, schedule.plan_id)

    one_time_lines = []
    for line in quotation.lines:
        if line.line_type != LineType.ONE_TIME:
            continue
        product = db.get(Product, line.product_id)
        one_time_lines.append(
            OneTimeLineOut(
                product_name=product.name if product else "Unknown product",
                qty=line.qty,
                amount=Decimal(line.computed.get("net", "0")),
            )
        )

    built = build_schedule(schedule.next_billing_date, schedule.interval, schedule.interval_count, schedule.amount)
    upcoming = [PeriodOccurrenceOut(period_start=o.period_start, period_end=o.period_end, amount=o.amount) for o in built.upcoming]

    return SubscriptionDetailOut(
        schedule_id=schedule.id,
        order_id=order.id,
        order_number=order.number,
        customer_name=customer.name if customer else "—",
        plan_name=plan.name if plan else "—",
        interval=schedule.interval,
        interval_count=schedule.interval_count,
        qty=schedule.qty,
        amount=schedule.amount,
        next_billing_date=schedule.next_billing_date,
        status=schedule.status,
        proration_policy=plan.proration_policy.value if plan else "NONE",
        cancellation_policy=plan.cancellation_policy if plan else "NONE",
        one_time_lines=one_time_lines,
        upcoming=upcoming,
    )


@router.post("/api/subscriptions/{schedule_id}/change", response_model=ProrationPreviewOut)
def change_subscription(
    schedule_id: uuid.UUID,
    body: SubscriptionChangeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProrationPreviewOut:
    schedule = _schedule_or_404(db, schedule_id)
    if schedule.status != BillingScheduleStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only an active subscription can be modified")
    plan = db.get(SubscriptionPlan, schedule.plan_id)
    if body.new_qty <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Quantity must be positive")

    unit_rate = schedule.amount / schedule.qty if schedule.qty else Decimal("0")
    today = date.today()
    period_start = _previous_period_start(schedule)
    result: ProrationResult = prorate(
        unit_rate, schedule.qty, body.new_qty, today, period_start, schedule.next_billing_date, plan.proration_policy
    )

    direction = "credit" if result.is_credit else "charge"
    summary = (
        f"{'Increasing' if body.new_qty > schedule.qty else 'Decreasing'} {schedule.qty} -> {body.new_qty} units "
        f"with {result.days_remaining} of {result.days_in_period} days remaining: "
        f"{'credit' if result.is_credit else 'charge'} {result.delta_amount} now, "
        f"then {result.new_period_amount} per period."
    )

    if body.preview:
        return ProrationPreviewOut(
            old_qty=schedule.qty,
            new_qty=body.new_qty,
            delta_amount=result.delta_amount,
            is_credit=result.is_credit,
            days_remaining=result.days_remaining,
            days_in_period=result.days_in_period,
            new_period_amount=result.new_period_amount,
            summary=summary,
        )

    old_qty = schedule.qty
    schedule.qty = body.new_qty
    schedule.amount = result.new_period_amount

    if result.delta_amount > 0:
        due_days = _setting_int(db, "invoice_due_days", 15)
        if result.is_credit:
            db.add(
                CreditNote(
                    id=uuid.uuid4(),
                    invoice_id=None,
                    amount=result.delta_amount,
                    reason=f"Mid-cycle decrease {old_qty} -> {body.new_qty} units on subscription {schedule.id}",
                )
            )
        else:
            db.add(
                Invoice(
                    id=uuid.uuid4(),
                    order_id=schedule.order_id,
                    number=_generate_number(db, Invoice, "INV"),
                    type=InvoiceType.RECURRING,
                    amount=result.delta_amount,
                    tax=Decimal("0"),
                    status=InvoiceStatus.ISSUED,
                    issue_date=today,
                    due_date=today + timedelta(days=due_days),
                    period_start=today,
                    period_end=schedule.next_billing_date,
                )
            )

    db.flush()
    log_event(
        db,
        entity_type="billing_schedule",
        entity_id=str(schedule.id),
        action="change",
        actor=user,
        payload={"old_qty": old_qty, "new_qty": body.new_qty, "delta_amount": str(result.delta_amount), "is_credit": result.is_credit},
    )
    db.commit()
    publish({"type": "subscription_changed", "schedule_id": str(schedule.id)})

    return ProrationPreviewOut(
        old_qty=old_qty,
        new_qty=body.new_qty,
        delta_amount=result.delta_amount,
        is_credit=result.is_credit,
        days_remaining=result.days_remaining,
        days_in_period=result.days_in_period,
        new_period_amount=result.new_period_amount,
        summary=summary,
    )


def _previous_period_start(schedule: BillingSchedule) -> date:
    return subtract_period(schedule.next_billing_date, schedule.interval, schedule.interval_count)


@router.post("/api/subscriptions/{schedule_id}/cancel", response_model=SubscriptionDetailOut)
def cancel_subscription(
    schedule_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> SubscriptionDetailOut:
    schedule = _schedule_or_404(db, schedule_id)
    if schedule.status == BillingScheduleStatus.CANCELLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already cancelled")
    plan = db.get(SubscriptionPlan, schedule.plan_id)

    today = date.today()
    period_start = _previous_period_start(schedule)
    unit_rate = schedule.amount / schedule.qty if schedule.qty else Decimal("0")
    credit_amount = cancel_credit(unit_rate, schedule.qty, today, period_start, schedule.next_billing_date, plan.cancellation_policy if plan else "NONE")

    schedule.status = BillingScheduleStatus.CANCELLED
    if credit_amount > 0:
        db.add(
            CreditNote(
                id=uuid.uuid4(),
                invoice_id=None,
                amount=credit_amount,
                reason=f"Cancellation credit for remaining period on subscription {schedule.id}",
            )
        )
    db.flush()
    log_event(
        db,
        entity_type="billing_schedule",
        entity_id=str(schedule.id),
        action="cancel",
        actor=user,
        payload={"credit_amount": str(credit_amount)},
    )
    db.commit()
    publish({"type": "subscription_cancelled", "schedule_id": str(schedule.id)})
    return get_subscription(schedule_id, db, user)


@router.get("/api/invoices", response_model=list[InvoiceListItem])
def list_invoices(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[InvoiceListItem]:
    invoices = db.query(Invoice).order_by(Invoice.issue_date.desc()).all()
    if not invoices:
        return []
    order_ids = {i.order_id for i in invoices}
    orders = {o.id: o for o in db.query(Order).filter(Order.id.in_(order_ids)).all()}
    quotation_ids = {o.quotation_id for o in orders.values()}
    quotations = {q.id: q for q in db.query(Quotation).filter(Quotation.id.in_(quotation_ids)).all()}
    customer_ids = {q.customer_id for q in quotations.values()}
    customers = {c.id: c for c in db.query(Customer).filter(Customer.id.in_(customer_ids)).all()}

    items = []
    for inv in invoices:
        order = orders.get(inv.order_id)
        quotation = quotations.get(order.quotation_id) if order else None
        customer = customers.get(quotation.customer_id) if quotation else None
        items.append(
            InvoiceListItem(
                id=inv.id,
                number=inv.number,
                customer_name=customer.name if customer else "—",
                amount=inv.amount,
                tax=inv.tax,
                status=inv.status,
                type=inv.type,
                due_date=inv.due_date,
            )
        )
    return items


@router.get("/api/invoices/{invoice_id}", response_model=InvoiceDetailOut)
def get_invoice(invoice_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> InvoiceDetailOut:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    order = db.get(Order, invoice.order_id)
    quotation = db.get(Quotation, order.quotation_id)
    customer = db.get(Customer, quotation.customer_id)
    payments = db.query(Payment).filter(Payment.invoice_id == invoice.id).order_by(Payment.received_at).all()

    has_shipment = (
        db.query(FulfillmentAllocation)
        .join(QuotationLine, FulfillmentAllocation.quotation_line_id == QuotationLine.id)
        .filter(QuotationLine.quotation_id == quotation.id, FulfillmentAllocation.shipped_at.isnot(None))
        .first()
        is not None
    )
    if invoice.status == InvoiceStatus.PAID:
        stage = "Paid"
    elif invoice.status in (InvoiceStatus.ISSUED, InvoiceStatus.PARTIAL, InvoiceStatus.CREDITED):
        stage = "Invoiced"
    elif has_shipment:
        stage = "Shipped"
    else:
        stage = "Order Confirmed"

    return InvoiceDetailOut(
        id=invoice.id,
        number=invoice.number,
        order_id=order.id,
        order_number=order.number,
        customer_name=customer.name if customer else "—",
        type=invoice.type,
        amount=invoice.amount,
        tax=invoice.tax,
        status=invoice.status,
        issue_date=invoice.issue_date,
        due_date=invoice.due_date,
        period_start=invoice.period_start,
        period_end=invoice.period_end,
        payments=[PaymentOut.model_validate(p) for p in payments],
        stage=stage,
    )


@router.post("/api/invoices/{invoice_id}/payments", response_model=InvoiceDetailOut)
def record_payment(
    invoice_id: uuid.UUID, body: PaymentCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> InvoiceDetailOut:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    if body.amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment amount must be positive")

    db.add(
        Payment(
            id=uuid.uuid4(),
            invoice_id=invoice.id,
            amount=body.amount,
            method=body.method,
            reference=body.reference,
        )
    )
    db.flush()

    total_paid = sum((p.amount for p in db.query(Payment).filter(Payment.invoice_id == invoice.id).all()), Decimal("0"))
    total_due = invoice.amount + invoice.tax
    invoice.status = InvoiceStatus.PAID if total_paid >= total_due else InvoiceStatus.PARTIAL
    db.flush()
    log_event(
        db,
        entity_type="invoice",
        entity_id=str(invoice.id),
        action="record_payment",
        actor=user,
        payload={"amount": str(body.amount), "method": body.method, "status": invoice.status.value},
    )
    db.commit()
    publish({"type": "payment_recorded", "invoice_id": str(invoice.id), "status": invoice.status.value})
    return get_invoice(invoice_id, db, user)
