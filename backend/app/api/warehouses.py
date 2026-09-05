import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.audit import log_event
from app.core.deps import get_current_user, get_db, require_role
from app.models.warehouse import StockLevel, Warehouse
from app.models.user import Role, User
from app.schemas.warehouse import (
    StockLevelOut,
    StockLevelUpsert,
    WarehouseCreate,
    WarehouseOut,
    WarehouseUpdate,
)

router = APIRouter(prefix="/api/warehouses", tags=["warehouses"])


@router.get("", response_model=list[WarehouseOut])
def list_warehouses(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[Warehouse]:
    return db.query(Warehouse).order_by(Warehouse.name).all()


@router.post("", response_model=WarehouseOut, status_code=status.HTTP_201_CREATED)
def create_warehouse(
    body: WarehouseCreate, db: Session = Depends(get_db), user: User = Depends(require_role(Role.ADMIN))
) -> Warehouse:
    warehouse = Warehouse(id=uuid.uuid4(), **body.model_dump())
    db.add(warehouse)
    db.flush()
    log_event(db, entity_type="warehouse", entity_id=str(warehouse.id), action="create", actor=user, payload=body.model_dump(mode="json"))
    db.commit()
    return warehouse


@router.put("/{warehouse_id}", response_model=WarehouseOut)
def update_warehouse(
    warehouse_id: uuid.UUID,
    body: WarehouseUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> Warehouse:
    warehouse = db.get(Warehouse, warehouse_id)
    if warehouse is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(warehouse, field, value)
    db.flush()
    log_event(db, entity_type="warehouse", entity_id=str(warehouse.id), action="update", actor=user, payload=body.model_dump(mode="json", exclude_unset=True))
    db.commit()
    return warehouse


@router.get("/stock", response_model=list[StockLevelOut])
def list_stock(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[StockLevel]:
    return db.query(StockLevel).all()


@router.put("/{warehouse_id}/stock/{product_id}", response_model=StockLevelOut)
def upsert_stock(
    warehouse_id: uuid.UUID,
    product_id: uuid.UUID,
    body: StockLevelUpsert,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> StockLevel:
    stock = (
        db.query(StockLevel)
        .filter(StockLevel.warehouse_id == warehouse_id, StockLevel.product_id == product_id)
        .first()
    )
    if stock is None:
        stock = StockLevel(
            id=uuid.uuid4(),
            warehouse_id=warehouse_id,
            product_id=product_id,
            on_hand=body.on_hand,
            reorder_point=body.reorder_point,
        )
        db.add(stock)
    else:
        stock.on_hand = body.on_hand
        stock.reorder_point = body.reorder_point
    db.flush()
    log_event(
        db,
        entity_type="stock_level",
        entity_id=f"{warehouse_id}:{product_id}",
        action="update",
        actor=user,
        payload=body.model_dump(mode="json"),
    )
    db.commit()
    return stock
