import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.billing import create_order_and_initial_invoices
from app.api.fulfillment import ensure_fulfillment_planned
from app.api.quotations import _apply_lines, _build_pricing, _risk_for_persisted
from app.core.audit import log_event
from app.core.deps import get_current_user, get_db
from app.core.events import publish
from app.core.portal_auth import generate_portal_token, get_portal_context, hash_portal_token
from app.engine.risk import compute_risk
from app.models.approval_request import ApprovalRequest, ApprovalRequestStatus
from app.models.catalog import Product
from app.models.customer import Customer
from app.models.fulfillment import Fulfillment, FulfillmentStatus
from app.models.portal import NegotiationRequest, NegotiationStatus, NegotiationType, PortalToken
from app.models.quotation import Quotation, QuotationLine, QuotationStatus
from app.models.setting import SystemSetting
from app.models.user import User
from app.schemas.quotation import QuotationLineIn
from app.schemas.portal import (
    NegotiationRequestOut,
    NegotiationRespondRequest,
    PortalConfirmOut,
    PortalLineOut,
    PortalNegotiateRequest,
    PortalQuotationOut,
    SendQuotationOut,
)

router = APIRouter(tags=["portal"])


def _setting_int(db: Session, key: str, default: int) -> int:
    setting = db.get(SystemSetting, key)
    return int(setting.value) if setting is not None else default


_NO_FILTER = object()


def _latest_negotiation(
    db: Session, quotation_id: uuid.UUID, ntype: NegotiationType, line_id: uuid.UUID | None = _NO_FILTER
) -> NegotiationRequest | None:
    q = db.query(NegotiationRequest).filter(
        NegotiationRequest.quotation_id == quotation_id, NegotiationRequest.type == ntype
    )
    if line_id is not _NO_FILTER:
        q = q.filter(NegotiationRequest.line_id == line_id)
    return q.order_by(NegotiationRequest.created_at.desc()).first()


@router.post("/api/quotations/{quotation_id}/send", response_model=SendQuotationOut)
def send_quotation(
    quotation_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> SendQuotationOut:
    quotation = db.get(Quotation, quotation_id)
    if quotation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quotation not found")
    if quotation.status not in (QuotationStatus.APPROVED, QuotationStatus.SENT, QuotationStatus.UNDER_NEGOTIATION):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only an approved quotation can be sent to the customer",
        )

    raw_token = generate_portal_token()
    expires_days = _setting_int(db, "portal_token_expires_days", 14)
    expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)

    db.add(
        PortalToken(
            id=uuid.uuid4(),
            quotation_id=quotation.id,
            customer_id=quotation.customer_id,
            token_hash=hash_portal_token(raw_token),
            expires_at=expires_at,
        )
    )
    if quotation.status == QuotationStatus.APPROVED:
        quotation.status = QuotationStatus.SENT
    quotation.last_activity_at = datetime.now(timezone.utc)
    db.flush()
    log_event(
        db,
        entity_type="quotation",
        entity_id=str(quotation.id),
        action="send_to_customer",
        actor=user,
        payload={"expires_at": expires_at.isoformat()},
    )
    db.commit()
    publish({"type": "quotation_sent", "quotation_id": str(quotation.id), "status": quotation.status.value})
    return SendQuotationOut(url=f"/portal/{raw_token}", expires_at=expires_at)


def _portal_quotation_out(db: Session, quotation: Quotation, portal_token: PortalToken) -> PortalQuotationOut:
    customer = db.get(Customer, quotation.customer_id)
    product_ids = {ln.product_id for ln in quotation.lines}
    products = {p.id: p for p in db.query(Product).filter(Product.id.in_(product_ids)).all()} if product_ids else {}

    lines_out = []
    for ln in quotation.lines:
        comment_row = _latest_negotiation(db, quotation.id, NegotiationType.COMMENT, line_id=ln.id)
        lines_out.append(
            PortalLineOut(
                id=ln.id,
                product_name=products[ln.product_id].name if ln.product_id in products else "—",
                qty=ln.qty,
                unit_price=ln.unit_price,
                discount_pct=ln.discount_pct,
                net=Decimal(ln.computed.get("net", "0")),
                tax_amount=Decimal(ln.computed.get("tax_amount", "0")),
                line_total=Decimal(ln.computed.get("net", "0")) + Decimal(ln.computed.get("tax_amount", "0")),
                comment=comment_row.message if comment_row else None,
            )
        )

    latest_counter = _latest_negotiation(db, quotation.id, NegotiationType.COUNTER_DISCOUNT, line_id=None)
    latest_change = _latest_negotiation(db, quotation.id, NegotiationType.CHANGE_REQUEST, line_id=None)

    return PortalQuotationOut(
        number=quotation.number,
        customer_name=customer.name if customer else "—",
        status=quotation.status.value,
        currency=quotation.currency,
        lines=lines_out,
        subtotal=quotation.subtotal,
        discount_total=quotation.discount_total,
        tax_total=quotation.tax_total,
        grand_total=quotation.grand_total,
        latest_counter_discount_pct=latest_counter.proposed_discount_pct if latest_counter else None,
        latest_requested_delivery_date=latest_change.requested_delivery_date if latest_change else None,
        expires_at=portal_token.expires_at,
    )


@router.get("/api/portal/quotation", response_model=PortalQuotationOut)
def get_portal_quotation(
    context: tuple[PortalToken, Quotation] = Depends(get_portal_context), db: Session = Depends(get_db)
) -> PortalQuotationOut:
    portal_token, quotation = context
    return _portal_quotation_out(db, quotation, portal_token)


@router.post("/api/portal/negotiate", response_model=PortalQuotationOut)
def negotiate(
    body: PortalNegotiateRequest,
    context: tuple[PortalToken, Quotation] = Depends(get_portal_context),
    db: Session = Depends(get_db),
) -> PortalQuotationOut:
    portal_token, quotation = context
    if portal_token.used_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This quotation has already been confirmed")
    if quotation.status not in (QuotationStatus.SENT, QuotationStatus.UNDER_NEGOTIATION):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This quotation isn't open for negotiation")

    line_ids = {ln.id for ln in quotation.lines}
    created = 0
    for line_id, comment in body.line_comments.items():
        if line_id not in line_ids or not comment.strip():
            continue
        db.add(
            NegotiationRequest(
                id=uuid.uuid4(),
                quotation_id=quotation.id,
                line_id=line_id,
                type=NegotiationType.COMMENT,
                message=comment.strip(),
            )
        )
        created += 1

    if body.proposed_discount_pct is not None:
        db.add(
            NegotiationRequest(
                id=uuid.uuid4(),
                quotation_id=quotation.id,
                line_id=None,
                type=NegotiationType.COUNTER_DISCOUNT,
                message=f"Customer requests {body.proposed_discount_pct}% off.",
                proposed_discount_pct=body.proposed_discount_pct,
            )
        )
        created += 1

    if body.requested_delivery_date is not None:
        db.add(
            NegotiationRequest(
                id=uuid.uuid4(),
                quotation_id=quotation.id,
                line_id=None,
                type=NegotiationType.CHANGE_REQUEST,
                message="Customer requests a different delivery date.",
                requested_delivery_date=body.requested_delivery_date,
            )
        )
        created += 1

    if created == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nothing to submit")

    quotation.status = QuotationStatus.UNDER_NEGOTIATION
    quotation.last_activity_at = datetime.now(timezone.utc)
    db.flush()
    log_event(
        db,
        entity_type="quotation",
        entity_id=str(quotation.id),
        action="portal_negotiate",
        actor=None,
        payload={"requests_created": created},
    )
    db.commit()
    db.refresh(quotation)
    publish({"type": "negotiation_created", "quotation_id": str(quotation.id), "status": quotation.status.value})
    return _portal_quotation_out(db, quotation, portal_token)


@router.post("/api/portal/confirm", response_model=PortalConfirmOut)
def confirm_from_portal(
    context: tuple[PortalToken, Quotation] = Depends(get_portal_context), db: Session = Depends(get_db)
) -> PortalConfirmOut:
    portal_token, quotation = context
    if portal_token.used_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This quotation has already been confirmed")
    if quotation.status not in (QuotationStatus.SENT, QuotationStatus.UNDER_NEGOTIATION):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This quotation can't be confirmed right now")

    # The automatic re-entry rule: re-price and re-run risk against final agreed terms,
    # exactly like an internal recompute -- final terms already live on quotation.lines
    # (a rep's accepted counter wrote them there via /negotiations/{id}/respond).
    _pricing, risk, chain = _risk_for_persisted(db, quotation)
    quotation.blended_score = risk.blended
    quotation.peak_overage = risk.peak
    quotation.erosion_amount = risk.erosion
    quotation.last_activity_at = datetime.now(timezone.utc)

    if chain:
        quotation.status = QuotationStatus.PENDING_APPROVAL
        for step in chain:
            db.add(
                ApprovalRequest(
                    id=uuid.uuid4(),
                    quotation_id=quotation.id,
                    level=step.level,
                    required_role=step.required_role,
                    status=ApprovalRequestStatus.PENDING,
                    sequence=step.sequence,
                    snapshot={
                        "blended": str(risk.blended),
                        "peak": str(risk.peak),
                        "erosion": str(risk.erosion),
                        "rule_name": step.rule_name,
                        "reason": step.reason,
                        "source": "portal_confirm",
                    },
                )
            )
        db.flush()
        log_event(
            db,
            entity_type="quotation",
            entity_id=str(quotation.id),
            action="portal_confirm_reentered_approval",
            actor=None,
            payload={"blended": str(risk.blended), "peak": str(risk.peak), "chain": [s.required_role for s in chain]},
        )
        db.commit()
        publish({"type": "quotation_reentered_approval", "quotation_id": str(quotation.id), "status": quotation.status.value})
        return PortalConfirmOut(
            status=quotation.status.value,
            message="Final terms exceeded a discount threshold, so this quotation was sent for internal review.",
        )

    quotation.status = QuotationStatus.APPROVED
    db.flush()
    ensure_fulfillment_planned(db, quotation, None)
    order = create_order_and_initial_invoices(db, quotation, None)
    quotation.status = QuotationStatus.CONFIRMED
    portal_token.used_at = datetime.now(timezone.utc)
    db.flush()
    log_event(
        db,
        entity_type="quotation",
        entity_id=str(quotation.id),
        action="portal_confirm",
        actor=None,
        payload={"order_id": str(order.id)},
    )
    db.commit()
    publish({"type": "quotation_confirmed", "quotation_id": str(quotation.id), "order_id": str(order.id)})
    return PortalConfirmOut(status=quotation.status.value, message="Quotation confirmed. Fulfillment planning has started.")


def _negotiation_to_schema(db: Session, req: NegotiationRequest) -> NegotiationRequestOut:
    line_product_name = None
    if req.line_id is not None:
        line = db.get(QuotationLine, req.line_id)
        if line is not None:
            product = db.get(Product, line.product_id)
            line_product_name = product.name if product else None
    responder_name = None
    if req.responder_user_id is not None:
        responder = db.get(User, req.responder_user_id)
        responder_name = responder.name if responder else None
    return NegotiationRequestOut(
        id=req.id,
        quotation_id=req.quotation_id,
        line_id=req.line_id,
        line_product_name=line_product_name,
        type=req.type,
        message=req.message,
        proposed_discount_pct=req.proposed_discount_pct,
        requested_delivery_date=req.requested_delivery_date,
        status=req.status,
        created_at=req.created_at,
        responded_at=req.responded_at,
        responder_name=responder_name,
        response_message=req.response_message,
    )


@router.get("/api/quotations/{quotation_id}/negotiations", response_model=list[NegotiationRequestOut])
def list_negotiations(
    quotation_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> list[NegotiationRequestOut]:
    quotation = db.get(Quotation, quotation_id)
    if quotation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quotation not found")
    requests = (
        db.query(NegotiationRequest)
        .filter(NegotiationRequest.quotation_id == quotation_id)
        .order_by(NegotiationRequest.created_at.desc())
        .all()
    )
    return [_negotiation_to_schema(db, r) for r in requests]


@router.post("/api/negotiations/{negotiation_id}/respond", response_model=NegotiationRequestOut)
def respond_to_negotiation(
    negotiation_id: uuid.UUID,
    body: NegotiationRespondRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NegotiationRequestOut:
    req = db.get(NegotiationRequest, negotiation_id)
    if req is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Negotiation request not found")
    if req.status != NegotiationStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This request was already responded to")
    if body.action not in ("accept", "counter", "decline"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid action")
    if body.action in ("counter", "decline") and not body.response_message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A response message is required for this action")

    quotation = db.get(Quotation, req.quotation_id)
    if quotation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quotation not found")

    if body.action == "accept":
        req.status = NegotiationStatus.ACCEPTED
        if req.type == NegotiationType.COUNTER_DISCOUNT and req.proposed_discount_pct is not None:
            # `_apply_lines` deletes and recreates QuotationLine rows (new ids), which
            # conflicts with any Fulfillment that was auto-planned back when this
            # quotation first reached APPROVED. A PLANNED (not yet Accepted) plan hasn't
            # reserved any stock, so it's safe to drop -- portal confirm regenerates a
            # fresh one against the final lines via ensure_fulfillment_planned.
            stale_plan = (
                db.query(Fulfillment)
                .filter(Fulfillment.quotation_id == quotation.id, Fulfillment.status == FulfillmentStatus.PLANNED)
                .first()
            )
            if stale_plan is not None:
                db.delete(stale_plan)
                db.flush()
            # Accepting an order-wide counter re-prices every line at the new discount --
            # the same "apply to all lines" semantics the builder already uses.
            lines_in = [
                QuotationLineIn(
                    product_id=ln.product_id,
                    variant_id=ln.variant_id,
                    line_type=ln.line_type,
                    qty=ln.qty,
                    discount_pct=req.proposed_discount_pct,
                    subscription_plan_id=ln.subscription_plan_id,
                    start_date=ln.start_date,
                )
                for ln in quotation.lines
            ]
            pricing, _customer = _build_pricing(db, quotation.customer_id, lines_in)
            _apply_lines(db, quotation, lines_in, pricing)
            risk = compute_risk(pricing)
            quotation.blended_score = risk.blended
            quotation.peak_overage = risk.peak
            quotation.erosion_amount = risk.erosion
    elif body.action == "counter":
        req.status = NegotiationStatus.COUNTERED
    else:
        req.status = NegotiationStatus.DECLINED

    req.responded_at = datetime.now(timezone.utc)
    req.responder_user_id = user.id
    req.response_message = body.response_message
    quotation.last_activity_at = datetime.now(timezone.utc)
    db.flush()
    log_event(
        db,
        entity_type="negotiation_request",
        entity_id=str(req.id),
        action=body.action,
        actor=user,
        payload={"quotation_id": str(quotation.id), "response_message": body.response_message},
    )
    db.commit()
    db.refresh(req)
    publish({"type": "negotiation_responded", "quotation_id": str(quotation.id), "action": body.action})
    return _negotiation_to_schema(db, req)
