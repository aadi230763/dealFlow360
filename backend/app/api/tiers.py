import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.audit import log_event
from app.core.deps import get_current_user, get_db, require_role
from app.models.customer import CustomerTier
from app.models.user import Role, User
from app.schemas.customer import CustomerTierCreate, CustomerTierOut, CustomerTierUpdate

router = APIRouter(prefix="/api/tiers", tags=["tiers"])


@router.get("", response_model=list[CustomerTierOut])
def list_tiers(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[CustomerTier]:
    return db.query(CustomerTier).order_by(CustomerTier.rank).all()


@router.post("", response_model=CustomerTierOut, status_code=status.HTTP_201_CREATED)
def create_tier(
    body: CustomerTierCreate, db: Session = Depends(get_db), user: User = Depends(require_role(Role.ADMIN))
) -> CustomerTier:
    tier = CustomerTier(id=uuid.uuid4(), **body.model_dump())
    db.add(tier)
    db.flush()
    log_event(db, entity_type="customer_tier", entity_id=str(tier.id), action="create", actor=user, payload=body.model_dump(mode="json"))
    db.commit()
    return tier


@router.put("/{tier_id}", response_model=CustomerTierOut)
def update_tier(
    tier_id: uuid.UUID,
    body: CustomerTierUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> CustomerTier:
    tier = db.get(CustomerTier, tier_id)
    if tier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tier not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(tier, field, value)
    db.flush()
    log_event(db, entity_type="customer_tier", entity_id=str(tier.id), action="update", actor=user, payload=body.model_dump(mode="json", exclude_unset=True))
    db.commit()
    return tier


@router.delete("/{tier_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tier(
    tier_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_role(Role.ADMIN))
) -> None:
    tier = db.get(CustomerTier, tier_id)
    if tier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tier not found")
    db.delete(tier)
    log_event(db, entity_type="customer_tier", entity_id=str(tier_id), action="delete", actor=user)
    db.commit()
