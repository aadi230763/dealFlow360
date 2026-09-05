import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.audit import log_event
from app.core.deps import get_current_user, get_db, require_role
from app.models.pairing import ProductPairing
from app.models.user import Role, User
from app.schemas.pairing import ProductPairingCreate, ProductPairingOut, ProductPairingUpdate

router = APIRouter(prefix="/api/pairings", tags=["pairings"])


@router.get("", response_model=list[ProductPairingOut])
def list_pairings(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[ProductPairing]:
    return db.query(ProductPairing).all()


@router.post("", response_model=ProductPairingOut, status_code=status.HTTP_201_CREATED)
def create_pairing(
    body: ProductPairingCreate, db: Session = Depends(get_db), user: User = Depends(require_role(Role.ADMIN))
) -> ProductPairing:
    pairing = ProductPairing(id=uuid.uuid4(), **body.model_dump())
    db.add(pairing)
    db.flush()
    log_event(db, entity_type="product_pairing", entity_id=str(pairing.id), action="create", actor=user, payload=body.model_dump(mode="json"))
    db.commit()
    return pairing


@router.put("/{pairing_id}", response_model=ProductPairingOut)
def update_pairing(
    pairing_id: uuid.UUID,
    body: ProductPairingUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> ProductPairing:
    pairing = db.get(ProductPairing, pairing_id)
    if pairing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pairing not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(pairing, field, value)
    db.flush()
    log_event(db, entity_type="product_pairing", entity_id=str(pairing.id), action="update", actor=user, payload=body.model_dump(mode="json", exclude_unset=True))
    db.commit()
    return pairing


@router.delete("/{pairing_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pairing(
    pairing_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_role(Role.ADMIN))
) -> None:
    pairing = db.get(ProductPairing, pairing_id)
    if pairing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pairing not found")
    db.delete(pairing)
    log_event(db, entity_type="product_pairing", entity_id=str(pairing_id), action="delete", actor=user)
    db.commit()
