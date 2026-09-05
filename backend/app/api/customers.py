import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.audit import log_event
from app.core.deps import get_current_user, get_db, require_role
from app.models.customer import Customer
from app.models.user import Role, User
from app.schemas.customer import CustomerCreate, CustomerOut, CustomerUpdate

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.get("", response_model=list[CustomerOut])
def list_customers(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[Customer]:
    return db.query(Customer).order_by(Customer.name).all()


@router.post("", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
def create_customer(
    body: CustomerCreate, db: Session = Depends(get_db), user: User = Depends(require_role(Role.ADMIN))
) -> Customer:
    customer = Customer(id=uuid.uuid4(), **body.model_dump())
    db.add(customer)
    db.flush()
    log_event(db, entity_type="customer", entity_id=str(customer.id), action="create", actor=user, payload=body.model_dump(mode="json"))
    db.commit()
    return customer


@router.put("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: uuid.UUID,
    body: CustomerUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    db.flush()
    log_event(db, entity_type="customer", entity_id=str(customer.id), action="update", actor=user, payload=body.model_dump(mode="json", exclude_unset=True))
    db.commit()
    return customer


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(
    customer_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_role(Role.ADMIN))
) -> None:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    db.delete(customer)
    log_event(db, entity_type="customer", entity_id=str(customer_id), action="delete", actor=user)
    db.commit()
