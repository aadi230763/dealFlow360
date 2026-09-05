import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.audit import log_event
from app.core.deps import get_current_user, get_db
from app.core.events import publish
from app.models.approval_request import ApprovalRequest, ApprovalRequestStatus
from app.models.customer import Customer, CustomerTier
from app.models.quotation import Quotation, QuotationStatus
from app.models.user import User
from app.schemas.quotation import QuotationOut
from app.schemas.risk import ApprovalActionRequest, ApprovalListItem

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


@router.get("", response_model=list[ApprovalListItem])
def list_approvals(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[ApprovalListItem]:
    """Screen 5: every quotation that ever went through routing, with its stage and
    current assignee. Actionability (who can click Approve) is enforced separately
    at act(), not by filtering rows out of this list."""
    all_requests = db.query(ApprovalRequest).order_by(ApprovalRequest.sequence).all()
    if not all_requests:
        return []

    by_quotation: dict[uuid.UUID, list[ApprovalRequest]] = {}
    for req in all_requests:
        by_quotation.setdefault(req.quotation_id, []).append(req)

    quotation_ids = list(by_quotation.keys())
    quotations = {q.id: q for q in db.query(Quotation).filter(Quotation.id.in_(quotation_ids)).all()}
    customer_ids = {q.customer_id for q in quotations.values()}
    customers = {c.id: c for c in db.query(Customer).filter(Customer.id.in_(customer_ids)).all()}
    tiers = {t.id: t for t in db.query(CustomerTier).all()}

    items = []
    for quotation_id, requests in by_quotation.items():
        q = quotations.get(quotation_id)
        if q is None:
            continue
        customer = customers.get(q.customer_id)
        tier = tiers.get(customer.tier_id) if customer else None

        active_roles = sorted({r.required_role for r in requests if r.status != ApprovalRequestStatus.CANCELLED})
        pending = sorted(
            (r for r in requests if r.status == ApprovalRequestStatus.PENDING), key=lambda r: r.sequence
        )
        has_returned = any(r.status == ApprovalRequestStatus.RETURNED for r in requests)

        if q.status == QuotationStatus.REJECTED:
            overall_status, stage, assigned_to = "REJECTED", "Rejected", "—"
        elif q.status == QuotationStatus.DRAFT and has_returned:
            overall_status, stage, assigned_to = "RETURNED", "Returned for revision", "—"
        elif pending:
            role_label = pending[0].required_role.replace("_", " ").title()
            overall_status, stage, assigned_to = "PENDING", role_label, role_label
        else:
            overall_status, stage, assigned_to = "APPROVED", "Completed", "—"

        items.append(
            ApprovalListItem(
                quotation_id=q.id,
                quotation_number=q.number,
                customer_name=customer.name if customer else "—",
                tier_name=tier.name if tier else "—",
                grand_total=q.grand_total,
                blended_score=q.blended_score,
                peak_overage=q.peak_overage,
                required_roles=active_roles,
                overall_status=overall_status,
                stage=stage,
                assigned_to=assigned_to,
                created_at=min(r.created_at for r in requests),
            )
        )

    return sorted(items, key=lambda i: i.created_at, reverse=True)


@router.post("/{approval_request_id}/act", response_model=QuotationOut)
def act_on_approval(
    approval_request_id: uuid.UUID,
    body: ApprovalActionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Quotation:
    req = db.get(ApprovalRequest, approval_request_id)
    if req is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found")
    quotation = db.get(Quotation, req.quotation_id)
    if quotation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quotation not found")

    if quotation.owner_user_id == user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot act on your own quotation")
    if user.role.value != req.required_role:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role for this approval step")
    if req.status != ApprovalRequestStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This approval step is not pending")

    earlier_pending = (
        db.query(ApprovalRequest)
        .filter(
            ApprovalRequest.quotation_id == req.quotation_id,
            ApprovalRequest.status == ApprovalRequestStatus.PENDING,
            ApprovalRequest.sequence < req.sequence,
        )
        .first()
    )
    if earlier_pending is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An earlier approval step is still pending")

    if body.action in ("reject", "return_for_revision") and not body.comment:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A comment is required for this action")
    if body.action not in ("approve", "reject", "return_for_revision"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid action")

    now = datetime.now(timezone.utc)
    old_status = quotation.status
    req.acted_by_user_id = user.id
    req.acted_at = now
    req.comment = body.comment

    if body.action == "approve":
        req.status = ApprovalRequestStatus.APPROVED
        db.flush()  # autoflush is off on this session; the remaining-count query below must see this change
        remaining = (
            db.query(ApprovalRequest)
            .filter(
                ApprovalRequest.quotation_id == req.quotation_id,
                ApprovalRequest.status == ApprovalRequestStatus.PENDING,
            )
            .count()
        )
        if remaining == 0:
            quotation.status = QuotationStatus.APPROVED
    elif body.action == "reject":
        req.status = ApprovalRequestStatus.REJECTED
        quotation.status = QuotationStatus.REJECTED
        db.query(ApprovalRequest).filter(
            ApprovalRequest.quotation_id == req.quotation_id,
            ApprovalRequest.status == ApprovalRequestStatus.PENDING,
        ).update({"status": ApprovalRequestStatus.CANCELLED})
    else:  # return_for_revision
        req.status = ApprovalRequestStatus.RETURNED
        quotation.status = QuotationStatus.DRAFT
        db.query(ApprovalRequest).filter(
            ApprovalRequest.quotation_id == req.quotation_id,
            ApprovalRequest.status == ApprovalRequestStatus.PENDING,
        ).update({"status": ApprovalRequestStatus.CANCELLED})

    quotation.last_activity_at = now
    db.flush()
    log_event(
        db,
        entity_type="approval_request",
        entity_id=str(req.id),
        action=body.action,
        actor=user,
        payload={
            "quotation_id": str(quotation.id),
            "comment": body.comment,
            "status_from": old_status.value,
            "status_to": quotation.status.value,
        },
    )
    db.commit()
    db.refresh(quotation)
    publish(
        {
            "type": "approval_acted",
            "quotation_id": str(quotation.id),
            "action": body.action,
            "status": quotation.status.value,
        }
    )
    return quotation
