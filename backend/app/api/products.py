import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.audit import log_event
from app.core.deps import get_current_user, get_db, require_role
from app.models.catalog import Product, ProductVariant
from app.models.user import Role, User
from app.models.warehouse import StockLevel
from app.schemas.catalog import ProductCreate, ProductOut, ProductUpdate

router = APIRouter(prefix="/api/products", tags=["products"])


def _attach_stock(db: Session, products: list[Product]) -> None:
    if not products:
        return
    product_ids = [p.id for p in products]
    totals = dict(
        db.query(StockLevel.product_id, func.sum(StockLevel.on_hand))
        .filter(StockLevel.product_id.in_(product_ids))
        .group_by(StockLevel.product_id)
        .all()
    )
    for p in products:
        p.quantity_on_hand = int(totals.get(p.id, 0))  # type: ignore[attr-defined]


@router.get("", response_model=list[ProductOut])
def list_products(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[Product]:
    products = db.query(Product).options(joinedload(Product.variants)).order_by(Product.name).all()
    _attach_stock(db, products)
    return products


@router.get("/{product_id}", response_model=ProductOut)
def get_product(
    product_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> Product:
    product = (
        db.query(Product).options(joinedload(Product.variants)).filter(Product.id == product_id).first()
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    _attach_stock(db, [product])
    return product


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    body: ProductCreate, db: Session = Depends(get_db), user: User = Depends(require_role(Role.ADMIN))
) -> Product:
    data = body.model_dump(exclude={"variants"})
    product = Product(id=uuid.uuid4(), **data)
    for variant in body.variants:
        product.variants.append(ProductVariant(id=uuid.uuid4(), **variant.model_dump()))
    db.add(product)
    db.flush()
    log_event(db, entity_type="product", entity_id=str(product.id), action="create", actor=user, payload=body.model_dump(mode="json"))
    db.commit()
    db.refresh(product)
    _attach_stock(db, [product])
    return product


@router.put("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: uuid.UUID,
    body: ProductUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.flush()
    log_event(db, entity_type="product", entity_id=str(product.id), action="update", actor=user, payload=body.model_dump(mode="json", exclude_unset=True))
    db.commit()
    db.refresh(product)
    _attach_stock(db, [product])
    return product


@router.post("/{product_id}/variants", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def add_variant(
    product_id: uuid.UUID,
    body: dict,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    variant = ProductVariant(
        id=uuid.uuid4(),
        product_id=product.id,
        attribute_name=body["attribute_name"],
        value=body["value"],
        price_delta=body.get("price_delta", 0),
    )
    db.add(variant)
    db.flush()
    log_event(db, entity_type="product", entity_id=str(product.id), action="add_variant", actor=user, payload=body)
    db.commit()
    db.refresh(product)
    _attach_stock(db, [product])
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_role(Role.ADMIN))
) -> None:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    db.delete(product)
    log_event(db, entity_type="product", entity_id=str(product_id), action="delete", actor=user)
    db.commit()
