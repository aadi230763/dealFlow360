import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.billing import invoice_shipment
from app.core.audit import log_event
from app.core.deps import get_current_user, get_db, require_role
from app.core.events import publish
from app.engine.fulfillment import (
    LineToFulfill,
    StockSnapshot,
    WarehouseInfo,
    plan_split,
)
from app.models.catalog import Product
from app.models.customer import Customer
from app.models.fulfillment import Fulfillment, FulfillmentAllocation, FulfillmentStatus
from app.models.quotation import Quotation, QuotationLine
from app.models.setting import SystemSetting
from app.models.user import Role, User
from app.models.warehouse import StockLevel, Warehouse
from app.schemas.fulfillment import (
    FulfillmentAllocationOut,
    FulfillmentListItem,
    FulfillmentOut,
    OverrideRequest,
)

router = APIRouter(tags=["fulfillment"])

DEFAULT_BASE_SHIPMENT_COST = Decimal("10")


def _base_shipment_cost(db: Session) -> Decimal:
    setting = db.get(SystemSetting, "fulfillment_base_shipment_cost")
    if setting is None:
        return DEFAULT_BASE_SHIPMENT_COST
    return Decimal(str(setting.value))


def _build_plan_inputs(db: Session, quotation: Quotation) -> tuple[list[LineToFulfill], list[StockSnapshot], list[WarehouseInfo]]:
    product_ids = {ln.product_id for ln in quotation.lines}
    products = {p.id: p for p in db.query(Product).filter(Product.id.in_(product_ids)).all()}
    lines = [
        LineToFulfill(
            quotation_line_id=ln.id,
            product_id=ln.product_id,
            product_name=products[ln.product_id].name if ln.product_id in products else "Unknown product",
            qty=ln.qty,
        )
        for ln in quotation.lines
    ]

    stock_rows = db.query(StockLevel).filter(StockLevel.product_id.in_(product_ids)).all()
    stock = [
        StockSnapshot(warehouse_id=s.warehouse_id, product_id=s.product_id, available=s.on_hand - s.reserved)
        for s in stock_rows
    ]

    warehouses = [
        WarehouseInfo(id=w.id, name=w.name, shipping_cost_weight=w.shipping_cost_weight)
        for w in db.query(Warehouse).filter(Warehouse.is_active.is_(True)).all()
    ]
    return lines, stock, warehouses


def _fulfillment_to_schema(db: Session, fulfillment: Fulfillment, quotation: Quotation) -> FulfillmentOut:
    customer = db.get(Customer, quotation.customer_id)
    line_by_id = {ln.id: ln for ln in quotation.lines}
    product_ids = {ln.product_id for ln in quotation.lines}
    products = {p.id: p for p in db.query(Product).filter(Product.id.in_(product_ids)).all()}
    warehouse_ids = {a.warehouse_id for a in fulfillment.allocations if a.warehouse_id}
    warehouses = {w.id: w for w in db.query(Warehouse).filter(Warehouse.id.in_(warehouse_ids)).all()}

    allocations_out = []
    explanations: list[str] = []
    for line_id, line in line_by_id.items():
        product = products.get(line.product_id)
        product_name = product.name if product else "Unknown product"
        line_allocs = [a for a in fulfillment.allocations if a.quotation_line_id == line_id]
        if not line_allocs:
            continue
        parts = []
        backorder_qty = 0
        for a in line_allocs:
            allocations_out.append(
                FulfillmentAllocationOut(
                    id=a.id,
                    quotation_line_id=a.quotation_line_id,
                    product_id=line.product_id,
                    product_name=product_name,
                    line_qty=line.qty,
                    warehouse_id=a.warehouse_id,
                    warehouse_name=warehouses[a.warehouse_id].name if a.warehouse_id in warehouses else None,
                    qty=a.qty,
                    is_backorder=a.is_backorder,
                    shipped_at=a.shipped_at,
                )
            )
            if a.is_backorder:
                backorder_qty += a.qty
            else:
                parts.append(f"{a.qty} of {line.qty} from {warehouses[a.warehouse_id].name}")
        sentence = ", ".join(parts)
        if backorder_qty:
            sentence = f"{sentence}, {backorder_qty} backordered" if sentence else f"{backorder_qty} of {line.qty} backordered"
        explanations.append(f"{product_name}: {sentence}.")

    return FulfillmentOut(
        id=fulfillment.id,
        quotation_id=quotation.id,
        quotation_number=quotation.number,
        customer_name=customer.name if customer else "—",
        status=fulfillment.status,
        total_shipments=fulfillment.total_shipments,
        estimated_cost=fulfillment.estimated_cost,
        is_manual_override=fulfillment.is_manual_override,
        explanations=explanations,
        allocations=allocations_out,
        created_at=fulfillment.created_at,
    )


def ensure_fulfillment_planned(db: Session, quotation: Quotation, user: User | None) -> Fulfillment | None:
    """Auto-runs the warehouse split the moment a quotation reaches APPROVED. Persists the
    plan (Fulfillment + FulfillmentAllocation rows) but reserves no stock yet -- that only
    happens when a human clicks Accept Suggested Split. No-op if already planned once,
    since recompute can re-enter APPROVED more than once for the same quotation."""
    existing = db.query(Fulfillment).filter(Fulfillment.quotation_id == quotation.id).first()
    if existing is not None:
        return existing
    if not quotation.lines:
        return None

    lines, stock, warehouses = _build_plan_inputs(db, quotation)
    if not lines:
        return None
    plan = plan_split(lines, stock, warehouses, _base_shipment_cost(db))
    if not plan.allocations:
        return None

    fulfillment = Fulfillment(
        id=uuid.uuid4(),
        quotation_id=quotation.id,
        status=FulfillmentStatus.PLANNED,
        total_shipments=plan.total_shipments,
        estimated_cost=plan.estimated_cost,
        is_manual_override=False,
    )
    db.add(fulfillment)
    db.flush()
    for a in plan.allocations:
        db.add(
            FulfillmentAllocation(
                id=uuid.uuid4(),
                fulfillment_id=fulfillment.id,
                quotation_line_id=a.quotation_line_id,
                warehouse_id=a.warehouse_id,
                qty=a.qty,
                is_backorder=a.is_backorder,
            )
        )
    db.flush()
    log_event(
        db,
        entity_type="fulfillment",
        entity_id=str(fulfillment.id),
        action="auto_plan",
        actor=user,
        payload={"quotation_id": str(quotation.id), "explanations": plan.explanations},
    )
    publish({"type": "fulfillment_planned", "quotation_id": str(quotation.id), "fulfillment_id": str(fulfillment.id)})
    return fulfillment


@router.get("/api/fulfillment", response_model=list[FulfillmentListItem])
def list_fulfillments(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[FulfillmentListItem]:
    fulfillments = db.query(Fulfillment).order_by(Fulfillment.created_at.desc()).all()
    if not fulfillments:
        return []
    quotation_ids = {f.quotation_id for f in fulfillments}
    quotations = {q.id: q for q in db.query(Quotation).filter(Quotation.id.in_(quotation_ids)).all()}
    customer_ids = {q.customer_id for q in quotations.values()}
    customers = {c.id: c for c in db.query(Customer).filter(Customer.id.in_(customer_ids)).all()}
    warehouse_ids = {a.warehouse_id for f in fulfillments for a in f.allocations if a.warehouse_id}
    warehouses = {w.id: w for w in db.query(Warehouse).filter(Warehouse.id.in_(warehouse_ids)).all()}

    items = []
    for f in fulfillments:
        quotation = quotations.get(f.quotation_id)
        if quotation is None:
            continue
        customer = customers.get(quotation.customer_id)
        has_backorder = any(a.is_backorder for a in f.allocations)
        status_label = "Backorder" if has_backorder else ("Accepted" if f.status == FulfillmentStatus.ACCEPTED else "Split Pending")
        wh_names = sorted({warehouses[a.warehouse_id].name for a in f.allocations if a.warehouse_id in warehouses})
        items.append(
            FulfillmentListItem(
                fulfillment_id=f.id,
                quotation_id=quotation.id,
                order_number=quotation.number,
                customer_name=customer.name if customer else "—",
                status_label=status_label,
                warehouse_names=" + ".join(wh_names) if wh_names else "—",
            )
        )
    return items


@router.get("/api/fulfillment/{fulfillment_id}", response_model=FulfillmentOut)
def get_fulfillment(
    fulfillment_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> FulfillmentOut:
    fulfillment = db.get(Fulfillment, fulfillment_id)
    if fulfillment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fulfillment not found")
    quotation = db.get(Quotation, fulfillment.quotation_id)
    if quotation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quotation not found")
    return _fulfillment_to_schema(db, fulfillment, quotation)


@router.post("/api/quotations/{quotation_id}/fulfillment/plan", response_model=FulfillmentOut)
def plan_fulfillment(
    quotation_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> FulfillmentOut:
    """Plan only, no writes -- recomputes the split against current stock without persisting."""
    quotation = db.get(Quotation, quotation_id)
    if quotation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quotation not found")
    lines, stock, warehouses = _build_plan_inputs(db, quotation)
    plan = plan_split(lines, stock, warehouses, _base_shipment_cost(db))

    line_by_id = {ln.quotation_line_id: ln for ln in lines}
    warehouses_by_id = {w.id: w for w in warehouses}
    allocations_out = [
        FulfillmentAllocationOut(
            id=uuid.uuid4(),
            quotation_line_id=a.quotation_line_id,
            product_id=line_by_id[a.quotation_line_id].product_id,
            product_name=line_by_id[a.quotation_line_id].product_name,
            line_qty=line_by_id[a.quotation_line_id].qty,
            warehouse_id=a.warehouse_id,
            warehouse_name=warehouses_by_id[a.warehouse_id].name if a.warehouse_id else None,
            qty=a.qty,
            is_backorder=a.is_backorder,
            shipped_at=None,
        )
        for a in plan.allocations
    ]
    customer = db.get(Customer, quotation.customer_id)
    return FulfillmentOut(
        id=uuid.uuid4(),
        quotation_id=quotation.id,
        quotation_number=quotation.number,
        customer_name=customer.name if customer else "—",
        status=FulfillmentStatus.PLANNED,
        total_shipments=plan.total_shipments,
        estimated_cost=plan.estimated_cost,
        is_manual_override=False,
        explanations=plan.explanations,
        allocations=allocations_out,
        created_at=datetime.now(timezone.utc),
    )


@router.post("/api/quotations/{quotation_id}/fulfillment/accept", response_model=FulfillmentOut)
def accept_fulfillment(
    quotation_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> FulfillmentOut:
    quotation = db.get(Quotation, quotation_id)
    if quotation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quotation not found")
    fulfillment = db.query(Fulfillment).filter(Fulfillment.quotation_id == quotation_id).first()
    if fulfillment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No fulfillment plan exists for this quotation")
    if fulfillment.status == FulfillmentStatus.ACCEPTED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This split is already accepted")

    for a in fulfillment.allocations:
        if a.is_backorder or a.warehouse_id is None:
            continue
        stock = (
            db.query(StockLevel)
            .filter(StockLevel.warehouse_id == a.warehouse_id, StockLevel.product_id == _line_product_id(db, a))
            .first()
        )
        if stock is not None:
            stock.reserved += a.qty

    fulfillment.status = FulfillmentStatus.ACCEPTED
    db.flush()
    log_event(
        db,
        entity_type="fulfillment",
        entity_id=str(fulfillment.id),
        action="accept",
        actor=user,
        payload={"quotation_id": str(quotation.id)},
    )
    db.commit()
    db.refresh(fulfillment)
    publish({"type": "fulfillment_accepted", "quotation_id": str(quotation.id), "fulfillment_id": str(fulfillment.id)})
    return _fulfillment_to_schema(db, fulfillment, quotation)


def _line_product_id(db: Session, allocation: FulfillmentAllocation) -> uuid.UUID:
    line = db.get(QuotationLine, allocation.quotation_line_id)
    return line.product_id


@router.post("/api/fulfillment/{fulfillment_id}/override", response_model=FulfillmentOut)
def override_fulfillment(
    fulfillment_id: uuid.UUID,
    body: OverrideRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.SALES_MANAGER)),
) -> FulfillmentOut:
    fulfillment = db.get(Fulfillment, fulfillment_id)
    if fulfillment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fulfillment not found")
    if fulfillment.status != FulfillmentStatus.PLANNED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only a not-yet-accepted split can be manually overridden",
        )
    quotation = db.get(Quotation, fulfillment.quotation_id)
    if quotation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quotation not found")

    lines_by_id = {ln.id: ln for ln in quotation.lines}
    products = {p.id: p for p in db.query(Product).filter(Product.id.in_({ln.product_id for ln in quotation.lines})).all()}

    by_line: dict[uuid.UUID, list] = {}
    for entry in body.allocations:
        if entry.quotation_line_id not in lines_by_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown quotation line in override")
        by_line.setdefault(entry.quotation_line_id, []).append(entry)

    warehouse_ids = {e.warehouse_id for e in body.allocations}
    warehouses = {w.id: w for w in db.query(Warehouse).filter(Warehouse.id.in_(warehouse_ids)).all()}

    new_allocations: list[FulfillmentAllocation] = []
    for line_id, line in lines_by_id.items():
        entries = by_line.get(line_id, [])
        assigned_total = sum(e.qty for e in entries)
        if assigned_total > line.qty:
            product_name = products[line.product_id].name if line.product_id in products else "this product"
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Assigned quantity for {product_name} ({assigned_total}) exceeds the ordered quantity ({line.qty}).",
            )
        for entry in entries:
            if entry.qty <= 0:
                continue
            warehouse = warehouses.get(entry.warehouse_id)
            if warehouse is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown warehouse in override")
            stock = (
                db.query(StockLevel)
                .filter(StockLevel.warehouse_id == entry.warehouse_id, StockLevel.product_id == line.product_id)
                .first()
            )
            available_qty = (stock.on_hand - stock.reserved) if stock else 0
            if entry.qty > available_qty:
                product_name = products[line.product_id].name if line.product_id in products else "this product"
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Only {available_qty} available at {warehouse.name} for {product_name}, cannot allocate {entry.qty}.",
                )
            new_allocations.append(
                FulfillmentAllocation(
                    id=uuid.uuid4(),
                    fulfillment_id=fulfillment.id,
                    quotation_line_id=line_id,
                    warehouse_id=entry.warehouse_id,
                    qty=entry.qty,
                    is_backorder=False,
                )
            )
        shortfall = line.qty - assigned_total
        if shortfall > 0:
            new_allocations.append(
                FulfillmentAllocation(
                    id=uuid.uuid4(),
                    fulfillment_id=fulfillment.id,
                    quotation_line_id=line_id,
                    warehouse_id=None,
                    qty=shortfall,
                    is_backorder=True,
                )
            )

    fulfillment.allocations.clear()
    db.flush()
    for a in new_allocations:
        db.add(a)
    db.flush()

    used_warehouses = {a.warehouse_id for a in new_allocations if not a.is_backorder}
    base_cost = _base_shipment_cost(db)
    fulfillment.total_shipments = len(used_warehouses)
    fulfillment.estimated_cost = sum(
        (warehouses[wid].shipping_cost_weight * base_cost for wid in used_warehouses if wid in warehouses),
        Decimal("0"),
    )
    fulfillment.is_manual_override = True
    db.flush()
    log_event(
        db,
        entity_type="fulfillment",
        entity_id=str(fulfillment.id),
        action="override",
        actor=user,
        payload={"quotation_id": str(quotation.id), "allocations": [e.model_dump(mode="json") for e in body.allocations]},
    )
    db.commit()
    db.refresh(fulfillment)
    publish({"type": "fulfillment_overridden", "quotation_id": str(quotation.id), "fulfillment_id": str(fulfillment.id)})
    return _fulfillment_to_schema(db, fulfillment, quotation)


@router.post("/api/fulfillment/{fulfillment_id}/consolidate", response_model=FulfillmentOut)
def consolidate_fulfillment(
    fulfillment_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> FulfillmentOut:
    fulfillment = db.get(Fulfillment, fulfillment_id)
    if fulfillment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fulfillment not found")
    quotation = db.get(Quotation, fulfillment.quotation_id)
    if quotation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quotation not found")

    backorder_rows = [a for a in fulfillment.allocations if a.is_backorder]
    if not backorder_rows:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nothing is backordered on this fulfillment")

    lines_by_id = {ln.id: ln for ln in quotation.lines}
    products = {p.id: p for p in db.query(Product).filter(Product.id.in_({ln.product_id for ln in quotation.lines})).all()}
    backorder_lines = [
        LineToFulfill(
            quotation_line_id=a.quotation_line_id,
            product_id=lines_by_id[a.quotation_line_id].product_id,
            product_name=products[lines_by_id[a.quotation_line_id].product_id].name,
            qty=a.qty,
        )
        for a in backorder_rows
    ]
    _, stock, warehouses = _build_plan_inputs(db, quotation)
    resolved = plan_split(backorder_lines, stock, warehouses, _base_shipment_cost(db))

    newly_resolved = [a for a in resolved.allocations if not a.is_backorder]
    if not newly_resolved:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Stock hasn't arrived yet -- nothing can be consolidated.")

    warehouses_by_id = {w.id: w for w in warehouses}
    for a in newly_resolved:
        db.add(
            FulfillmentAllocation(
                id=uuid.uuid4(),
                fulfillment_id=fulfillment.id,
                quotation_line_id=a.quotation_line_id,
                warehouse_id=a.warehouse_id,
                qty=a.qty,
                is_backorder=False,
            )
        )
        row = next(r for r in backorder_rows if r.quotation_line_id == a.quotation_line_id)
        row.qty -= a.qty
        if fulfillment.status == FulfillmentStatus.ACCEPTED:
            stock = (
                db.query(StockLevel)
                .filter(StockLevel.warehouse_id == a.warehouse_id, StockLevel.product_id == lines_by_id[a.quotation_line_id].product_id)
                .first()
            )
            if stock is not None:
                stock.reserved += a.qty

    for row in backorder_rows:
        if row.qty <= 0:
            db.delete(row)
    db.flush()

    remaining_allocations = (
        db.query(FulfillmentAllocation).filter(FulfillmentAllocation.fulfillment_id == fulfillment.id).all()
    )
    used_warehouses = {a.warehouse_id for a in remaining_allocations if not a.is_backorder}
    base_cost = _base_shipment_cost(db)
    fulfillment.total_shipments = len(used_warehouses)
    fulfillment.estimated_cost = sum(
        (warehouses_by_id[wid].shipping_cost_weight * base_cost for wid in used_warehouses if wid in warehouses_by_id),
        Decimal("0"),
    )
    db.flush()
    log_event(
        db,
        entity_type="fulfillment",
        entity_id=str(fulfillment.id),
        action="consolidate",
        actor=user,
        payload={"quotation_id": str(quotation.id), "explanations": resolved.explanations},
    )
    db.commit()
    db.refresh(fulfillment)
    publish({"type": "fulfillment_consolidated", "quotation_id": str(quotation.id), "fulfillment_id": str(fulfillment.id)})
    return _fulfillment_to_schema(db, fulfillment, quotation)


@router.post("/api/fulfillment/allocations/{allocation_id}/ship", response_model=FulfillmentOut)
def ship_allocation(
    allocation_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> FulfillmentOut:
    allocation = db.get(FulfillmentAllocation, allocation_id)
    if allocation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allocation not found")
    if allocation.is_backorder or allocation.warehouse_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A backordered allocation cannot be shipped")
    if allocation.shipped_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This allocation has already shipped")

    fulfillment = db.get(Fulfillment, allocation.fulfillment_id)
    quotation = db.get(Quotation, fulfillment.quotation_id)
    line = db.get(QuotationLine, allocation.quotation_line_id)

    stock = (
        db.query(StockLevel)
        .filter(StockLevel.warehouse_id == allocation.warehouse_id, StockLevel.product_id == line.product_id)
        .first()
    )
    if stock is not None:
        stock.on_hand = max(0, stock.on_hand - allocation.qty)
        stock.reserved = max(0, stock.reserved - allocation.qty)

    allocation.shipped_at = datetime.now(timezone.utc)
    db.flush()
    invoice_shipment(db, allocation, user)
    log_event(
        db,
        entity_type="fulfillment_allocation",
        entity_id=str(allocation.id),
        action="ship",
        actor=user,
        payload={"quotation_id": str(quotation.id), "qty": allocation.qty},
    )
    db.commit()
    db.refresh(fulfillment)
    publish({"type": "allocation_shipped", "quotation_id": str(quotation.id), "allocation_id": str(allocation.id)})
    return _fulfillment_to_schema(db, fulfillment, quotation)
