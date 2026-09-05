import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.audit import log_event
from app.core.deps import get_current_user, get_db, require_role
from app.models.subscription_plan import SubscriptionPlan
from app.models.user import Role, User
from app.schemas.subscription_plan import (
    SubscriptionPlanCreate,
    SubscriptionPlanOut,
    SubscriptionPlanUpdate,
)

router = APIRouter(prefix="/api/subscription-plans", tags=["subscription-plans"])


@router.get("", response_model=list[SubscriptionPlanOut])
def list_plans(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[SubscriptionPlan]:
    return db.query(SubscriptionPlan).order_by(SubscriptionPlan.name).all()


@router.post("", response_model=SubscriptionPlanOut, status_code=status.HTTP_201_CREATED)
def create_plan(
    body: SubscriptionPlanCreate, db: Session = Depends(get_db), user: User = Depends(require_role(Role.ADMIN))
) -> SubscriptionPlan:
    plan = SubscriptionPlan(id=uuid.uuid4(), **body.model_dump())
    db.add(plan)
    db.flush()
    log_event(db, entity_type="subscription_plan", entity_id=str(plan.id), action="create", actor=user, payload=body.model_dump(mode="json"))
    db.commit()
    return plan


@router.put("/{plan_id}", response_model=SubscriptionPlanOut)
def update_plan(
    plan_id: uuid.UUID,
    body: SubscriptionPlanUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> SubscriptionPlan:
    plan = db.get(SubscriptionPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)
    db.flush()
    log_event(db, entity_type="subscription_plan", entity_id=str(plan.id), action="update", actor=user, payload=body.model_dump(mode="json", exclude_unset=True))
    db.commit()
    return plan


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(
    plan_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_role(Role.ADMIN))
) -> None:
    plan = db.get(SubscriptionPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    db.delete(plan)
    log_event(db, entity_type="subscription_plan", entity_id=str(plan_id), action="delete", actor=user)
    db.commit()
