import csv
import io
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.engine.anomaly import (
    FulfillmentBackorderSample,
    QuotationActivitySample,
    QuotationDiscountSample,
    find_delivery_slippage,
    find_discount_anomalies,
    find_stalled_deals,
)
from app.models.approval_request import ApprovalRequest, ApprovalRequestStatus
from app.models.audit import AuditEvent
from app.models.catalog import Product
from app.models.customer import Customer
from app.models.fulfillment import Fulfillment, FulfillmentAllocation
from app.models.pairing import ProductPairing
from app.models.quotation import Quotation, QuotationLine, QuotationStatus
from app.models.setting import SystemSetting
from app.models.user import User
from app.schemas.dashboard import (
    DashboardHealthOut,
    DashboardMetricsOut,
    DeliverySlippageOut,
    DiscountAnomalyOut,
    MarginTrendPoint,
    RepDiscountPoint,
    ReportOut,
    StalledDealOut,
)

router = APIRouter(tags=["dashboard"])

TERMINAL_STATUSES = [
    QuotationStatus.CONFIRMED,
    QuotationStatus.INVOICED,
    QuotationStatus.REJECTED,
    QuotationStatus.CANCELLED,
]
CLOSED_WON_STATUSES = [QuotationStatus.CONFIRMED, QuotationStatus.INVOICED]
CLOSED_LOST_STATUSES = [QuotationStatus.REJECTED, QuotationStatus.CANCELLED]

ACTION_LABELS = {"nudge": "Nudge sent", "escalate": "Escalated to Manager"}


def _setting(db: Session, key: str, default):
    setting = db.get(SystemSetting, key)
    return setting.value if setting is not None else default


def _last_actions(db: Session, quotation_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not quotation_ids:
        return {}
    events = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.entity_type == "quotation",
            AuditEvent.entity_id.in_([str(qid) for qid in quotation_ids]),
            AuditEvent.action.in_(["nudge", "escalate"]),
        )
        .order_by(AuditEvent.created_at.desc())
        .all()
    )
    out: dict[uuid.UUID, str] = {}
    for e in events:
        qid = uuid.UUID(e.entity_id)
        if qid not in out:
            out[qid] = ACTION_LABELS.get(e.action, e.action)
    return out


def _discount_samples(db: Session) -> list[QuotationDiscountSample]:
    rows = (
        db.query(Quotation, User)
        .join(User, User.id == Quotation.owner_user_id)
        .filter(Quotation.subtotal > 0)
        .all()
    )
    customer_ids = {q.customer_id for q, _ in rows}
    customers = {c.id: c for c in db.query(Customer).filter(Customer.id.in_(customer_ids)).all()}
    samples = []
    for q, owner in rows:
        discount_pct = (q.discount_total / q.subtotal * Decimal("100")).quantize(Decimal("0.01"))
        samples.append(
            QuotationDiscountSample(
                quotation_id=q.id,
                number=q.number,
                customer_name=customers[q.customer_id].name if q.customer_id in customers else "—",
                rep_id=owner.id,
                rep_name=owner.name,
                discount_pct=discount_pct,
                created_at=q.created_at,
            )
        )
    return samples


@router.get("/api/dashboard/health", response_model=DashboardHealthOut)
def dashboard_health(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> DashboardHealthOut:
    now = datetime.now(timezone.utc)

    # Stalled deals
    stalled_threshold = int(_setting(db, "stalled_deal_day_threshold", 10))
    open_quotations = (
        db.query(Quotation, User)
        .join(User, User.id == Quotation.owner_user_id)
        .filter(~Quotation.status.in_(TERMINAL_STATUSES))
        .all()
    )
    customer_ids = {q.customer_id for q, _ in open_quotations}
    customers = {c.id: c for c in db.query(Customer).filter(Customer.id.in_(customer_ids)).all()}
    activity_samples = [
        QuotationActivitySample(
            quotation_id=q.id,
            number=q.number,
            customer_name=customers[q.customer_id].name if q.customer_id in customers else "—",
            owner_name=owner.name,
            grand_total=q.grand_total,
            last_activity_at=q.last_activity_at,
        )
        for q, owner in open_quotations
    ]
    stalled = find_stalled_deals(activity_samples, stalled_threshold, now)

    # Discount anomalies
    z_threshold = Decimal(str(_setting(db, "anomaly_zscore_threshold", 2.0)))
    anomalies = find_discount_anomalies(_discount_samples(db), z_threshold)

    # Delivery slippage
    promise_days = int(_setting(db, "fulfillment_promise_days", 5))
    backorder_rows = (
        db.query(
            Fulfillment.id,
            Fulfillment.quotation_id,
            Fulfillment.created_at,
            FulfillmentAllocation.qty,
        )
        .join(FulfillmentAllocation, FulfillmentAllocation.fulfillment_id == Fulfillment.id)
        .filter(FulfillmentAllocation.is_backorder.is_(True))
        .all()
    )
    grouped: dict[uuid.UUID, dict] = {}
    for fid, qid, created_at, qty in backorder_rows:
        bucket = grouped.setdefault(fid, {"quotation_id": qid, "created_at": created_at, "qty": 0})
        bucket["qty"] += qty
    quotation_ids = {b["quotation_id"] for b in grouped.values()}
    quotations_by_id = {q.id: q for q in db.query(Quotation).filter(Quotation.id.in_(quotation_ids)).all()}
    slip_customer_ids = {q.customer_id for q in quotations_by_id.values()}
    slip_customers = {c.id: c for c in db.query(Customer).filter(Customer.id.in_(slip_customer_ids)).all()}
    backorder_samples = [
        FulfillmentBackorderSample(
            fulfillment_id=fid,
            quotation_id=b["quotation_id"],
            number=quotations_by_id[b["quotation_id"]].number if b["quotation_id"] in quotations_by_id else "—",
            customer_name=(
                slip_customers[quotations_by_id[b["quotation_id"]].customer_id].name
                if b["quotation_id"] in quotations_by_id
                and quotations_by_id[b["quotation_id"]].customer_id in slip_customers
                else "—"
            ),
            created_at=b["created_at"],
            backorder_qty=b["qty"],
        )
        for fid, b in grouped.items()
    ]
    slippage = find_delivery_slippage(backorder_samples, promise_days, now)

    actioned_ids = [d.quotation_id for d in stalled] + [a.quotation_id for a in anomalies] + [s.quotation_id for s in slippage]
    last_actions = _last_actions(db, actioned_ids)

    return DashboardHealthOut(
        stalled=[
            StalledDealOut(**vars(d), last_action=last_actions.get(d.quotation_id)) for d in stalled
        ],
        anomalies=[
            DiscountAnomalyOut(**vars(a), last_action=last_actions.get(a.quotation_id)) for a in anomalies
        ],
        slippage=[
            DeliverySlippageOut(**vars(s), last_action=last_actions.get(s.quotation_id)) for s in slippage
        ],
    )


@router.get("/api/dashboard/metrics", response_model=DashboardMetricsOut)
def dashboard_metrics(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> DashboardMetricsOut:
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    quotes_created = db.query(Quotation).filter(Quotation.created_at >= month_start).count()

    approved_steps = (
        db.query(ApprovalRequest)
        .filter(ApprovalRequest.status == ApprovalRequestStatus.APPROVED, ApprovalRequest.acted_at.isnot(None))
        .all()
    )
    if approved_steps:
        total_hours = sum(
            ((s.acted_at - s.created_at).total_seconds() / 3600 for s in approved_steps), 0.0
        )
        avg_approval_time_hours = Decimal(str(round(total_hours / len(approved_steps), 1)))
    else:
        avg_approval_time_hours = None

    # Top upsold product: products that are a pairing suggestion target and appear in quotation
    # lines, ranked by how often they show up.
    suggested_ids = {r[0] for r in db.query(ProductPairing.suggested_product_id).distinct().all()}
    top_upsold_product = None
    if suggested_ids:
        counts = (
            db.query(QuotationLine.product_id, Product.name)
            .join(Product, Product.id == QuotationLine.product_id)
            .filter(QuotationLine.product_id.in_(suggested_ids))
            .all()
        )
        if counts:
            tally = Counter(name for _pid, name in counts)
            top_upsold_product = tally.most_common(1)[0][0]

    won = db.query(Quotation).filter(Quotation.status.in_(CLOSED_WON_STATUSES)).count()
    lost = db.query(Quotation).filter(Quotation.status.in_(CLOSED_LOST_STATUSES)).count()
    win_rate_pct = Decimal(str(round(won / (won + lost) * 100, 1))) if (won + lost) > 0 else Decimal("0")

    discount_samples = _discount_samples(db)
    anomalies = find_discount_anomalies(discount_samples, Decimal(str(_setting(db, "anomaly_zscore_threshold", 2.0))))
    outlier_quotation_ids = {a.quotation_id for a in anomalies}
    by_rep: dict[str, list[Decimal]] = {}
    outlier_reps: set[str] = set()
    for s in discount_samples:
        by_rep.setdefault(s.rep_name, []).append(s.discount_pct)
        if s.quotation_id in outlier_quotation_ids:
            outlier_reps.add(s.rep_name)
    discount_by_rep = [
        RepDiscountPoint(
            rep_name=rep,
            discount_pct=(sum(vals) / len(vals)).quantize(Decimal("0.01")),
            is_outlier=rep in outlier_reps,
        )
        for rep, vals in sorted(by_rep.items())
    ]

    cutoff = now - timedelta(days=180)
    recent = db.query(Quotation).filter(Quotation.created_at >= cutoff, Quotation.subtotal > 0).all()
    by_month: dict[str, list[Decimal]] = {}
    for q in recent:
        key = q.created_at.strftime("%Y-%m")
        by_month.setdefault(key, []).append(q.margin_pct)
    margin_trend = [
        MarginTrendPoint(period=month, margin_pct=(sum(vals) / len(vals)).quantize(Decimal("0.01")))
        for month, vals in sorted(by_month.items())
    ]

    return DashboardMetricsOut(
        quotes_created=quotes_created,
        avg_approval_time_hours=avg_approval_time_hours,
        top_upsold_product=top_upsold_product,
        win_rate_pct=win_rate_pct,
        discount_by_rep=discount_by_rep,
        margin_trend=margin_trend,
    )


def _filtered_quotations(
    db: Session,
    period_days: int | None,
    owner_user_id: uuid.UUID | None,
    approval_status: str | None,
    product_id: uuid.UUID | None,
):
    q = db.query(Quotation)
    if period_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)
        q = q.filter(Quotation.created_at >= cutoff)
    if owner_user_id is not None:
        q = q.filter(Quotation.owner_user_id == owner_user_id)
    if approval_status is not None:
        q = q.filter(Quotation.status == approval_status)
    if product_id is not None:
        line_quotation_ids = db.query(QuotationLine.quotation_id).filter(QuotationLine.product_id == product_id)
        q = q.filter(Quotation.id.in_(line_quotation_ids))
    return q


@router.get("/api/reports", response_model=ReportOut)
def get_report(
    period_days: int | None = Query(None),
    owner_user_id: uuid.UUID | None = Query(None),
    approval_status: str | None = Query(None),
    product_id: uuid.UUID | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ReportOut:
    quotations = _filtered_quotations(db, period_days, owner_user_id, approval_status, product_id).all()
    quotation_ids = [q.id for q in quotations]

    approved_steps = (
        db.query(ApprovalRequest)
        .filter(
            ApprovalRequest.quotation_id.in_(quotation_ids),
            ApprovalRequest.status == ApprovalRequestStatus.APPROVED,
            ApprovalRequest.acted_at.isnot(None),
        )
        .all()
        if quotation_ids
        else []
    )
    if approved_steps:
        total_hours = sum(((s.acted_at - s.created_at).total_seconds() / 3600 for s in approved_steps), 0.0)
        avg_approval_time_hours = Decimal(str(round(total_hours / len(approved_steps), 1)))
    else:
        avg_approval_time_hours = None

    top_upsold_product = None
    if quotation_ids:
        suggested_ids = {r[0] for r in db.query(ProductPairing.suggested_product_id).distinct().all()}
        if suggested_ids:
            counts = (
                db.query(Product.name)
                .join(QuotationLine, QuotationLine.product_id == Product.id)
                .filter(QuotationLine.quotation_id.in_(quotation_ids), Product.id.in_(suggested_ids))
                .all()
            )
            if counts:
                tally = Counter(name for (name,) in counts)
                top_upsold_product = tally.most_common(1)[0][0]

    total_pipeline_value = sum((q.grand_total for q in quotations), Decimal("0"))

    return ReportOut(
        quotes_created=len(quotations),
        avg_approval_time_hours=avg_approval_time_hours,
        top_upsold_product=top_upsold_product,
        total_pipeline_value=total_pipeline_value,
    )


@router.get("/api/reports/export.csv")
def export_report_csv(
    period_days: int | None = Query(None),
    owner_user_id: uuid.UUID | None = Query(None),
    approval_status: str | None = Query(None),
    product_id: uuid.UUID | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> StreamingResponse:
    quotations = (
        _filtered_quotations(db, period_days, owner_user_id, approval_status, product_id)
        .order_by(Quotation.created_at.desc())
        .all()
    )
    owner_ids = {q.owner_user_id for q in quotations}
    customer_ids = {q.customer_id for q in quotations}
    owners = {u.id: u for u in db.query(User).filter(User.id.in_(owner_ids)).all()} if owner_ids else {}
    customers = {c.id: c for c in db.query(Customer).filter(Customer.id.in_(customer_ids)).all()} if customer_ids else {}

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Number", "Customer", "Owner", "Status", "Grand Total", "Margin %", "Created At"])
    for q in quotations:
        writer.writerow(
            [
                q.number,
                customers[q.customer_id].name if q.customer_id in customers else "",
                owners[q.owner_user_id].name if q.owner_user_id in owners else "",
                q.status.value,
                str(q.grand_total),
                str(q.margin_pct),
                q.created_at.isoformat(),
            ]
        )
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=report.csv"},
    )
