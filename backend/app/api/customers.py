import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.audit import log_event
from app.core.deps import get_current_user, get_db, require_role
from app.models.customer import Customer
from app.models.user import Role, User
from app.schemas.customer import CustomerCreate, CustomerOut, CustomerUpdate

router = APIRouter(prefix="/api/customers", tags=["customers"])


def _to_out(db: Session, customer: Customer) -> CustomerOut:
    owner = db.get(User, customer.owner_user_id) if customer.owner_user_id else None
    return CustomerOut(
        id=customer.id,
        name=customer.name,
        email=customer.email,
        tier_id=customer.tier_id,
        currency=customer.currency,
        owner_user_id=customer.owner_user_id,
        owner_name=owner.name if owner else None,
    )


@router.get("", response_model=list[CustomerOut])
def list_customers(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[CustomerOut]:
    customers = db.query(Customer).order_by(Customer.name).all()
    owner_ids = {c.owner_user_id for c in customers if c.owner_user_id}
    owners = {u.id: u for u in db.query(User).filter(User.id.in_(owner_ids)).all()} if owner_ids else {}
    return [
        CustomerOut(
            id=c.id,
            name=c.name,
            email=c.email,
            tier_id=c.tier_id,
            currency=c.currency,
            owner_user_id=c.owner_user_id,
            owner_name=owners[c.owner_user_id].name if c.owner_user_id in owners else None,
        )
        for c in customers
    ]


@router.post("", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
def create_customer(
    body: CustomerCreate, db: Session = Depends(get_db), user: User = Depends(require_role(Role.ADMIN))
) -> CustomerOut:
    customer = Customer(id=uuid.uuid4(), **body.model_dump())
    db.add(customer)
    db.flush()
    log_event(db, entity_type="customer", entity_id=str(customer.id), action="create", actor=user, payload=body.model_dump(mode="json"))
    db.commit()
    return _to_out(db, customer)


@router.put("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: uuid.UUID,
    body: CustomerUpdate,
    db: Session = Depends(get_db),
    # Reassigning the account owner is a management action; everything else about a
    # customer record stays admin-only master data, same as before this field existed.
    user: User = Depends(require_role(Role.ADMIN, Role.SALES_MANAGER)),
) -> CustomerOut:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    body_fields = body.model_dump(exclude_unset=True)
    if user.role == Role.SALES_MANAGER and set(body_fields) - {"owner_user_id"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sales managers can only reassign the account owner, not other customer fields",
        )
    for field, value in body_fields.items():
        setattr(customer, field, value)
    db.flush()
    log_event(
        db,
        entity_type="customer",
        entity_id=str(customer.id),
        action="update",
        actor=user,
        payload=body.model_dump(mode="json", exclude_unset=True),
    )
    db.commit()
    return _to_out(db, customer)


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
