import io
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.audit import log_event
from app.core.deps import get_current_user, get_db, require_role
from app.core.dismissals import dismiss as dismiss_suggestion_for, get_dismissed
from app.core.events import publish
from app.core.notifications import dispatch_event
from app.api.fulfillment import ensure_fulfillment_planned
from app.engine.ceilings import resolve_ceiling
from app.engine.pricing import LineInput, QuotationPricing, price_quotation
from app.engine.risk import RiskResult, compute_risk
from app.engine.routing import ApprovalRuleData, ApprovalStep, determine_chain, explain
from app.engine.upsell import PairingCandidate, suggest as suggest_upsells
from app.models.approval_request import ApprovalRequest, ApprovalRequestStatus
from app.models.approval_rule import ApprovalRule
from app.models.catalog import Category, Product, ProductVariant
from app.models.customer import Customer, CustomerTier
from app.models.fulfillment import Fulfillment, FulfillmentStatus
from app.models.pairing import ProductPairing
from app.models.pricing_config import CategoryTierCeiling
from app.models.quotation import Quotation, QuotationLine, QuotationStatus
from app.models.user import Role, User
from app.schemas.dashboard import NudgeActionOut
from app.schemas.quotation import (
    LinePricingOut,
    QuotationCreate,
    QuotationLineIn,
    QuotationLineOut,
    QuotationLinesUpdate,
    QuotationListItem,
    QuotationOut,
    QuotationPreviewOut,
    QuotationPreviewRequest,
    QuotationPricingOut,
    QuotationStatusUpdate,
)
from app.schemas.risk import ApprovalRequestOut, ApprovalStepOut, LineRiskBreakdownOut, RiskOut
from app.schemas.upsell import SuggestionOut

router = APIRouter(prefix="/api/quotations", tags=["quotations"])


def _build_pricing(db: Session, customer_id: uuid.UUID, lines_in: list) -> tuple[QuotationPricing, Customer]:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    tier = db.get(CustomerTier, customer.tier_id)

    product_ids = {ln.product_id for ln in lines_in}
    products = {p.id: p for p in db.query(Product).filter(Product.id.in_(product_ids)).all()}
    if len(products) != len(product_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more products not found")

    variant_ids = {ln.variant_id for ln in lines_in if ln.variant_id}
    variants = {}
    if variant_ids:
        variants = {v.id: v for v in db.query(ProductVariant).filter(ProductVariant.id.in_(variant_ids)).all()}

    category_ids = {p.category_id for p in products.values()}
    categories = {c.id: c for c in db.query(Category).filter(Category.id.in_(category_ids)).all()}
    overrides = {
        (o.tier_id, o.category_id): o.ceiling_pct
        for o in db.query(CategoryTierCeiling)
        .filter(CategoryTierCeiling.tier_id == tier.id, CategoryTierCeiling.category_id.in_(category_ids))
        .all()
    }
    ceilings = {
        cat_id: resolve_ceiling(
            tier_base=tier.base_discount_ceiling_pct,
            category_default=categories[cat_id].default_discount_ceiling_pct,
            override=overrides.get((tier.id, cat_id)),
        )
        for cat_id in category_ids
    }

    engine_lines = []
    for ln in lines_in:
        product = products[ln.product_id]
        variant = variants.get(ln.variant_id) if ln.variant_id else None
        unit_price = product.list_price + (variant.price_delta if variant else 0)
        engine_lines.append(
            LineInput(
                product_id=product.id,
                category_id=product.category_id,
                line_type=ln.line_type.value if hasattr(ln.line_type, "value") else ln.line_type,
                qty=ln.qty,
                unit_price=unit_price,
                unit_cost=product.unit_cost,
                tax_pct=product.tax_pct,
                discount_pct=ln.discount_pct,
                variant_id=ln.variant_id,
                subscription_plan_id=ln.subscription_plan_id,
                product_name=product.name,
            )
        )

    pricing = price_quotation(engine_lines, ceilings)
    return pricing, customer


def _pricing_to_schema(pricing: QuotationPricing) -> QuotationPricingOut:
    return QuotationPricingOut(
        lines=[LinePricingOut(**vars(p)) for p in pricing.lines],
        subtotal=pricing.subtotal,
        discount_total=pricing.discount_total,
        tax_total=pricing.tax_total,
        net_total=pricing.net_total,
        grand_total=pricing.grand_total,
        margin_amount=pricing.margin_amount,
        margin_pct=pricing.margin_pct,
        explanations=pricing.explanations,
    )


def _load_active_rules(db: Session) -> list[ApprovalRuleData]:
    rules = db.query(ApprovalRule).filter(ApprovalRule.is_active.is_(True)).all()
    return [
        ApprovalRuleData(
            id=str(r.id),
            name=r.name,
            level=r.level,
            min_blended=r.min_blended,
            min_peak=r.min_peak,
            min_erosion_amount=r.min_erosion_amount,
            required_roles=list(r.required_roles),
            sequence=r.sequence,
            is_active=r.is_active,
        )
        for r in rules
    ]


def _risk_to_schema(risk: RiskResult, chain: list[ApprovalStep]) -> RiskOut:
    return RiskOut(
        blended=risk.blended,
        peak=risk.peak,
        erosion=risk.erosion,
        breakdown=[LineRiskBreakdownOut(**vars(b)) for b in risk.per_line_breakdown],
        chain=[ApprovalStepOut(**vars(s)) for s in chain],
        chain_explanations=explain(chain),
    )


def _generate_number(db: Session) -> str:
    count = db.query(Quotation).count()
    return f"Q-{count + 1:04d}"


def _apply_lines(db: Session, quotation: Quotation, lines_in: list, pricing: QuotationPricing) -> None:
    quotation.lines.clear()
    db.flush()
    for line_in, priced in zip(lines_in, pricing.lines):
        db.add(
            QuotationLine(
                id=uuid.uuid4(),
                quotation_id=quotation.id,
                product_id=line_in.product_id,
                variant_id=line_in.variant_id,
                line_type=line_in.line_type,
                qty=line_in.qty,
                unit_price=priced.unit_price,
                unit_cost=priced.unit_cost,
                discount_pct=line_in.discount_pct,
                subscription_plan_id=line_in.subscription_plan_id,
                start_date=line_in.start_date,
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
    quotation.subtotal = pricing.subtotal
    quotation.discount_total = pricing.discount_total
    quotation.tax_total = pricing.tax_total
    quotation.grand_total = pricing.grand_total
    quotation.margin_amount = pricing.margin_amount
    quotation.margin_pct = pricing.margin_pct
    quotation.last_activity_at = datetime.now(timezone.utc)
    # New lines were added via db.add(...), not quotation.lines.append(...), so the
    # in-memory relationship (emptied by .clear() above) doesn't pick them up on its own --
    # any caller reading quotation.lines right after this (e.g. ensure_fulfillment_planned)
    # would otherwise see a stale empty list and silently no-op.
    db.flush()
    db.refresh(quotation, attribute_names=["lines"])


@router.post("/preview", response_model=QuotationPreviewOut)
def preview_quotation(
    body: QuotationPreviewRequest, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> QuotationPreviewOut:
    pricing, _customer = _build_pricing(db, body.customer_id, body.lines)
    risk = compute_risk(pricing)
    chain = determine_chain(risk, _load_active_rules(db))
    pricing_schema = _pricing_to_schema(pricing)
    return QuotationPreviewOut(**pricing_schema.model_dump(), risk=_risk_to_schema(risk, chain))


@router.get("", response_model=list[QuotationListItem])
def list_quotations(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    status_filter: QuotationStatus | None = Query(None, alias="status"),
    owner_user_id: uuid.UUID | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
) -> list[QuotationListItem]:
    q = db.query(Quotation)
    if status_filter is not None:
        q = q.filter(Quotation.status == status_filter)
    if owner_user_id is not None:
        q = q.filter(Quotation.owner_user_id == owner_user_id)
    if date_from is not None:
        q = q.filter(Quotation.created_at >= date_from)
    if date_to is not None:
        q = q.filter(Quotation.created_at <= date_to)
    quotations = q.order_by(Quotation.created_at.desc()).all()

    customer_ids = {qt.customer_id for qt in quotations}
    owner_ids = {qt.owner_user_id for qt in quotations}
    customers = {c.id: c for c in db.query(Customer).filter(Customer.id.in_(customer_ids)).all()}
    tiers = {t.id: t for t in db.query(CustomerTier).all()}
    owners = {u.id: u for u in db.query(User).filter(User.id.in_(owner_ids)).all()}

    quotation_ids = [qt.id for qt in quotations]
    active_requests = (
        db.query(ApprovalRequest)
        .filter(ApprovalRequest.quotation_id.in_(quotation_ids), ApprovalRequest.status != ApprovalRequestStatus.CANCELLED)
        .all()
        if quotation_ids
        else []
    )
    roles_by_quotation: dict[uuid.UUID, set[str]] = {}
    for req in active_requests:
        roles_by_quotation.setdefault(req.quotation_id, set()).add(req.required_role)

    items = []
    for qt in quotations:
        customer = customers.get(qt.customer_id)
        owner = owners.get(qt.owner_user_id)
        tier = tiers.get(customer.tier_id) if customer else None
        items.append(
            QuotationListItem(
                id=qt.id,
                number=qt.number,
                customer_id=qt.customer_id,
                customer_name=customer.name if customer else "—",
                tier_name=tier.name if tier else "—",
                owner_user_id=qt.owner_user_id,
                owner_name=owner.name if owner else "—",
                status=qt.status,
                grand_total=qt.grand_total,
                margin_pct=qt.margin_pct,
                blended_score=qt.blended_score,
                peak_overage=qt.peak_overage,
                required_roles=sorted(roles_by_quotation.get(qt.id, set())),
                created_at=qt.created_at,
                last_activity_at=qt.last_activity_at,
            )
        )
    return items


@router.get("/{quotation_id}", response_model=QuotationOut)
def get_quotation(
    quotation_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> Quotation:
    quotation = db.get(Quotation, quotation_id)
    if quotation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quotation not found")
    return quotation


@router.post("", response_model=QuotationOut, status_code=status.HTTP_201_CREATED)
def create_quotation(
    body: QuotationCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Quotation:
    pricing, _customer = _build_pricing(db, body.customer_id, body.lines)
    quotation = Quotation(
        id=uuid.uuid4(),
        number=_generate_number(db),
        customer_id=body.customer_id,
        owner_user_id=user.id,
        status=QuotationStatus.DRAFT,
        currency=_customer.currency,
    )
    db.add(quotation)
    db.flush()
    _apply_lines(db, quotation, body.lines, pricing)
    db.flush()
    log_event(db, entity_type="quotation", entity_id=str(quotation.id), action="create", actor=user, payload={"number": quotation.number})
    db.commit()
    db.refresh(quotation)
    return quotation


@router.put("/{quotation_id}/lines", response_model=QuotationOut)
def update_quotation_lines(
    quotation_id: uuid.UUID,
    body: QuotationLinesUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Quotation:
    quotation = db.get(Quotation, quotation_id)
    if quotation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quotation not found")
    pricing, _customer = _build_pricing(db, quotation.customer_id, body.lines)
    _apply_lines(db, quotation, body.lines, pricing)
    db.flush()
    log_event(db, entity_type="quotation", entity_id=str(quotation.id), action="update_lines", actor=user, payload={"line_count": len(body.lines)})
    db.commit()
    db.refresh(quotation)
    return quotation


@router.put("/{quotation_id}/status", response_model=QuotationOut)
def update_status(
    quotation_id: uuid.UUID,
    body: QuotationStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Quotation:
    quotation = db.get(Quotation, quotation_id)
    if quotation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quotation not found")
    old_status = quotation.status
    quotation.status = body.status
    quotation.last_activity_at = datetime.now(timezone.utc)
    db.flush()
    log_event(
        db,
        entity_type="quotation",
        entity_id=str(quotation.id),
        action="status_change",
        actor=user,
        payload={"from": old_status.value, "to": body.status.value},
    )
    db.commit()
    db.refresh(quotation)
    return quotation


@router.delete("/{quotation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_quotation(
    quotation_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> None:
    quotation = db.get(Quotation, quotation_id)
    if quotation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quotation not found")
    db.delete(quotation)
    log_event(db, entity_type="quotation", entity_id=str(quotation_id), action="delete", actor=user)
    db.commit()


def _risk_for_persisted(db: Session, quotation: Quotation) -> tuple[QuotationPricing, RiskResult, list[ApprovalStep]]:
    """Reprices and re-routes a persisted quotation against CURRENT config -- the only
    way risk numbers are ever produced for a saved quotation, so preview/submit/recompute
    can never disagree with each other."""
    pricing, _customer = _build_pricing(db, quotation.customer_id, quotation.lines)
    risk = compute_risk(pricing)
    chain = determine_chain(risk, _load_active_rules(db))
    return pricing, risk, chain


@router.get("/{quotation_id}/risk", response_model=RiskOut)
def get_quotation_risk(
    quotation_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> RiskOut:
    quotation = db.get(Quotation, quotation_id)
    if quotation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quotation not found")
    _pricing, risk, chain = _risk_for_persisted(db, quotation)
    return _risk_to_schema(risk, chain)


@router.get("/{quotation_id}/approvals", response_model=list[ApprovalRequestOut])
def list_quotation_approvals(
    quotation_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> list[ApprovalRequestOut]:
    quotation = db.get(Quotation, quotation_id)
    if quotation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quotation not found")
    requests = (
        db.query(ApprovalRequest)
        .filter(ApprovalRequest.quotation_id == quotation_id)
        .order_by(ApprovalRequest.sequence, ApprovalRequest.created_at)
        .all()
    )
    actor_ids = {r.acted_by_user_id for r in requests if r.acted_by_user_id}
    actors = {u.id: u for u in db.query(User).filter(User.id.in_(actor_ids)).all()} if actor_ids else {}
    return [
        ApprovalRequestOut(
            id=r.id,
            quotation_id=r.quotation_id,
            level=r.level,
            required_role=r.required_role,
            status=r.status,
            sequence=r.sequence,
            acted_by_user_id=r.acted_by_user_id,
            acted_by_name=actors[r.acted_by_user_id].name if r.acted_by_user_id in actors else None,
            acted_at=r.acted_at,
            comment=r.comment,
            snapshot=r.snapshot,
            created_at=r.created_at,
        )
        for r in requests
    ]


@router.post("/{quotation_id}/submit", response_model=QuotationOut)
def submit_quotation(
    quotation_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Quotation:
    quotation = db.get(Quotation, quotation_id)
    if quotation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quotation not found")
    if quotation.status != QuotationStatus.DRAFT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only a draft quotation can be submitted")
    if not quotation.lines:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Quotation has no lines")

    _pricing, risk, chain = _risk_for_persisted(db, quotation)
    quotation.blended_score = risk.blended
    quotation.peak_overage = risk.peak
    quotation.erosion_amount = risk.erosion

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
                    },
                )
            )
    else:
        quotation.status = QuotationStatus.APPROVED

    quotation.last_activity_at = datetime.now(timezone.utc)
    db.flush()
    if quotation.status == QuotationStatus.APPROVED:
        ensure_fulfillment_planned(db, quotation, user)
    log_event(
        db,
        entity_type="quotation",
        entity_id=str(quotation.id),
        action="submit",
        actor=user,
        payload={
            "blended": str(risk.blended),
            "peak": str(risk.peak),
            "erosion": str(risk.erosion),
            "chain": [s.required_role for s in chain],
            "new_status": quotation.status.value,
        },
    )
    if chain:
        dispatch_event(
            db,
            "quotation_submitted_for_approval",
            {"number": quotation.number, "role": chain[0].required_role},
            quotation.id,
        )
    else:
        dispatch_event(
            db,
            "quotation_auto_approved",
            {"number": quotation.number, "owner_user_id": quotation.owner_user_id},
            quotation.id,
        )
    db.commit()
    db.refresh(quotation)
    publish({"type": "quotation_submitted", "quotation_id": str(quotation.id), "status": quotation.status.value})
    return quotation


@router.post("/{quotation_id}/recompute", response_model=QuotationOut)
def recompute_quotation(
    quotation_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Quotation:
    quotation = db.get(Quotation, quotation_id)
    if quotation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quotation not found")

    old_blended, old_peak, old_erosion = quotation.blended_score, quotation.peak_overage, quotation.erosion_amount
    old_status = quotation.status

    pricing, risk, chain = _risk_for_persisted(db, quotation)

    # Reprice against current config (product prices/costs may have changed too) without
    # losing the rep's chosen quantities/discounts.
    lines_in = [
        QuotationLineIn(
            product_id=ln.product_id,
            variant_id=ln.variant_id,
            line_type=ln.line_type,
            qty=ln.qty,
            discount_pct=ln.discount_pct,
            subscription_plan_id=ln.subscription_plan_id,
            start_date=ln.start_date,
        )
        for ln in quotation.lines
    ]
    # `_apply_lines` deletes and recreates QuotationLine rows (new ids). If this quotation
    # already has a Fulfillment (auto-planned when it first reached APPROVED), the old
    # lines are still referenced by fulfillment_allocations and the delete hits a hard FK
    # violation. A still-PLANNED plan hasn't reserved any stock, so it's safe to drop --
    # ensure_fulfillment_planned below regenerates a fresh one against the final lines if
    # this recompute lands back on APPROVED. (Same fix already applied to the portal's
    # counter-discount-accept path, which hits the identical root cause.)
    stale_plan = (
        db.query(Fulfillment)
        .filter(Fulfillment.quotation_id == quotation.id, Fulfillment.status == FulfillmentStatus.PLANNED)
        .first()
    )
    if stale_plan is not None:
        db.delete(stale_plan)
        db.flush()
    _apply_lines(db, quotation, lines_in, pricing)

    quotation.blended_score = risk.blended
    quotation.peak_overage = risk.peak
    quotation.erosion_amount = risk.erosion

    new_status = QuotationStatus.APPROVED if not chain else QuotationStatus.PENDING_APPROVAL
    chain_changed = True
    if old_status == QuotationStatus.APPROVED and new_status == QuotationStatus.APPROVED:
        chain_changed = False

    if chain_changed:
        db.query(ApprovalRequest).filter(
            ApprovalRequest.quotation_id == quotation.id,
            ApprovalRequest.status == ApprovalRequestStatus.PENDING,
        ).update({"status": ApprovalRequestStatus.CANCELLED})
        quotation.status = new_status
        if chain:
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
                        },
                    )
                )

    quotation.last_activity_at = datetime.now(timezone.utc)
    db.flush()
    if quotation.status == QuotationStatus.APPROVED:
        ensure_fulfillment_planned(db, quotation, user)
    log_event(
        db,
        entity_type="quotation",
        entity_id=str(quotation.id),
        action="recompute",
        actor=user,
        payload={
            "old": {"blended": str(old_blended), "peak": str(old_peak), "erosion": str(old_erosion)},
            "new": {"blended": str(risk.blended), "peak": str(risk.peak), "erosion": str(risk.erosion)},
            "status_from": old_status.value,
            "status_to": quotation.status.value,
            "chain_changed": chain_changed,
        },
    )
    if chain_changed and quotation.status == QuotationStatus.PENDING_APPROVAL:
        dispatch_event(
            db,
            "quotation_recomputed_reentered_approval",
            {"number": quotation.number, "owner_user_id": quotation.owner_user_id},
            quotation.id,
        )
    db.commit()
    db.refresh(quotation)
    publish({"type": "quotation_recomputed", "quotation_id": str(quotation.id), "status": quotation.status.value})
    return quotation


@router.get("/{quotation_id}/suggestions", response_model=list[SuggestionOut])
def get_suggestions(
    quotation_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> list[SuggestionOut]:
    quotation = db.get(Quotation, quotation_id)
    if quotation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quotation not found")

    current_product_ids = {ln.product_id for ln in quotation.lines}
    if not current_product_ids:
        return []

    baseline_pricing, _customer = _build_pricing(db, quotation.customer_id, quotation.lines)

    pairings = (
        db.query(ProductPairing).filter(ProductPairing.product_id.in_(current_product_ids)).all()
    )
    dismissed = get_dismissed(quotation_id)

    seen: set[uuid.UUID] = set()
    candidates: list[PairingCandidate] = []
    for pairing in pairings:
        sp_id = pairing.suggested_product_id
        if sp_id in current_product_ids or sp_id in seen or sp_id in dismissed:
            continue
        seen.add(sp_id)

        suggested_product = db.get(Product, sp_id)
        if suggested_product is None or not suggested_product.is_active:
            continue
        origin_product = db.get(Product, pairing.product_id)

        hypothetical_lines_in = list(quotation.lines) + [
            QuotationLineIn(product_id=sp_id, qty=1, discount_pct=Decimal("0"))
        ]
        hypo_pricing, _ = _build_pricing(db, quotation.customer_id, hypothetical_lines_in)
        new_line_pricing = hypo_pricing.lines[-1]
        margin_delta = hypo_pricing.margin_amount - baseline_pricing.margin_amount

        candidates.append(
            PairingCandidate(
                suggested_product_id=sp_id,
                product_name=suggested_product.name,
                is_promoted=suggested_product.is_promoted,
                co_purchase_score=pairing.co_purchase_score,
                min_margin_pct=pairing.min_margin_pct,
                suggested_line_margin_pct=new_line_pricing.margin_pct,
                margin_delta=margin_delta,
                new_grand_total=hypo_pricing.grand_total,
                reason=f"Often bought with {origin_product.name if origin_product else 'items on this order'}.",
            )
        )

    results = suggest_upsells(candidates, dismissed)
    return [SuggestionOut(**vars(r)) for r in results]


@router.post("/{quotation_id}/suggestions/{product_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
def dismiss_suggestion(
    quotation_id: uuid.UUID,
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> None:
    quotation = db.get(Quotation, quotation_id)
    if quotation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quotation not found")
    dismiss_suggestion_for(quotation_id, product_id)


def _nudge_or_escalate(quotation_id: uuid.UUID, action: str, db: Session, user: User) -> NudgeActionOut:
    quotation = db.get(Quotation, quotation_id)
    if quotation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quotation not found")
    log_event(db, entity_type="quotation", entity_id=str(quotation.id), action=action, actor=user)
    db.commit()
    publish({"type": f"quotation_{action}d" if action == "nudge" else "quotation_escalated", "quotation_id": str(quotation.id)})
    return NudgeActionOut(quotation_id=quotation.id, action=action)


@router.post("/{quotation_id}/nudge", response_model=NudgeActionOut)
def nudge_quotation(
    quotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.SALES_MANAGER, Role.FINANCE, Role.ADMIN)),
) -> NudgeActionOut:
    return _nudge_or_escalate(quotation_id, "nudge", db, user)


@router.post("/{quotation_id}/escalate", response_model=NudgeActionOut)
def escalate_quotation(
    quotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    # Admin excluded deliberately: escalation means raising a deal to whoever is above the
    # acting role, and nobody is above Admin, so the action is meaningless for that role.
    user: User = Depends(require_role(Role.SALES_MANAGER, Role.FINANCE)),
) -> NudgeActionOut:
    return _nudge_or_escalate(quotation_id, "escalate", db, user)


@router.get("/{quotation_id}/pdf")
def export_quotation_pdf(
    quotation_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> StreamingResponse:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    quotation = db.get(Quotation, quotation_id)
    if quotation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quotation not found")
    customer = db.get(Customer, quotation.customer_id)
    product_ids = {ln.product_id for ln in quotation.lines}
    products = {p.id: p for p in db.query(Product).filter(Product.id.in_(product_ids)).all()}

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    left = 20 * mm
    y = height - 25 * mm

    c.setFont("Helvetica-Bold", 18)
    c.drawString(left, y, "DealFlow360")
    c.setFont("Helvetica", 10)
    c.drawRightString(width - left, y, f"Quotation {quotation.number}")
    y -= 8 * mm
    c.setFont("Helvetica", 10)
    c.drawString(left, y, f"Customer: {customer.name if customer else '—'}")
    c.drawRightString(width - left, y, f"Date: {quotation.created_at.strftime('%Y-%m-%d')}")
    y -= 6 * mm
    c.drawString(left, y, f"Status: {quotation.status.value}")
    y -= 12 * mm

    c.setFont("Helvetica-Bold", 9)
    headers = ["Product", "Qty", "Unit Price", "Discount %", "Net"]
    col_x = [left, left + 80 * mm, left + 100 * mm, left + 130 * mm, left + 160 * mm]
    for text, x in zip(headers, col_x):
        c.drawString(x, y, text)
    y -= 3 * mm
    c.line(left, y, width - left, y)
    y -= 6 * mm

    c.setFont("Helvetica", 9)
    for line in quotation.lines:
        product = products.get(line.product_id)
        net = Decimal(str(line.computed.get("net", "0")))
        row = [
            product.name if product else "—",
            str(line.qty),
            f"{line.unit_price}",
            f"{line.discount_pct}%",
            f"{net}",
        ]
        for text, x in zip(row, col_x):
            c.drawString(x, y, text)
        y -= 6 * mm
        if y < 30 * mm:
            c.showPage()
            y = height - 25 * mm

    y -= 4 * mm
    c.line(left, y, width - left, y)
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 10)
    for label, value in [
        ("Subtotal", quotation.subtotal),
        ("Discount", quotation.discount_total),
        ("Tax", quotation.tax_total),
        ("Grand Total", quotation.grand_total),
    ]:
        c.drawString(left + 100 * mm, y, label)
        c.drawRightString(width - left, y, str(value))
        y -= 6 * mm

    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(colors.grey)
    c.drawString(left, 15 * mm, "Generated by DealFlow360 — rules stored as data, priced by one shared engine.")
    c.showPage()
    c.save()
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={quotation.number}.pdf"},
    )
